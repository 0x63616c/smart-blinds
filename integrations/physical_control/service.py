"""Explicit physical control service: one coordinator and one owner per device.

HTTP callers copy state or enqueue a bounded intent. Only the coordinator opens
and reserves the durable ledger; only each actor performs native network I/O.
"""
from copy import deepcopy
import hmac
import math
import re
import threading
import time

from integrations.physical_bridge.service import Pairing
from integrations.thread_bridge.ledger import Ledger, LedgerError
from integrations.thread_bridge.group import Group
from integrations.thread_bridge.worker import now_us
from integrations.home_assistant.coordinator import Envelope, Phase
from .actor import Actor, ActorWorker


class PhysicalControl:
    def __init__(self, bridge_id, pairings, selections, ledger_path, library, *, period_s=15):
        if type(bridge_id) is not str or re.fullmatch(r'[A-Za-z0-9_-]{1,64}',bridge_id) is None:
            raise ValueError('Invalid bridge identity')
        if not 1<=len(pairings)<=8 or len({p.device_id for p in pairings})!=len(pairings):
            raise ValueError('Select one to eight unique paired devices')
        for p in pairings:
            p.validate()
            if p.device_id == 'room': raise ValueError('Device identity is reserved for the group')
        if len({p.endpoint() for p in pairings})!=len(pairings):raise ValueError('Duplicate endpoint owner')
        self.pairings={p.device_id:p for p in pairings}
        if len({s.device_id for s in selections})!=len(selections):raise ValueError('Duplicate selection')
        for s in selections:
            s.validate();p=self.pairings.get(s.device_id)
            if (p is None or Pairing(s.device_id,p.name,s.host,s.port,s.identity,s.key,s.boot).endpoint()!=p.endpoint()
                or s.boot!=p.boot or s.identity!=p.identity or not hmac.compare_digest(s.key,p.key)):
                raise ValueError('Selection must match the explicit pairing')
        self.bridge_id,self.library,self.ledger_path=bridge_id,library,ledger_path
        self.selections={s.device_id:s for s in selections};self.period_s=period_s
        self.lock=threading.Lock();self.changed=threading.Event();self.halt=threading.Event();self.started=threading.Event()
        self.pending=None;self.inflight=None;self.active=None;self.actors={};self.configured={};self.failure=None
        self.last_operation=None
        self.stop_generation=0;self.next_intent=0;self.phase='idle';self.reason='';self.last_intent=0
        self.thread=threading.Thread(target=self._run,name='physical-coordinator');self.thread.start()
        if not self.started.wait(3):self.close();raise RuntimeError('Coordinator startup deadline')
        if self.failure:self.close();raise RuntimeError(self.failure)

    def move(self,target,position,*,align=False):
        if (target!='room' and target not in self.pairings) or type(align) is not bool or (align and target!='room'):
            raise ValueError('Invalid target or alignment operation')
        if type(position) not in (int,float) or not math.isfinite(position) or not 0<=position<=100:
            raise ValueError('Invalid percentage')
        with self.lock:
            members=list(self.pairings) if target=='room' else [target]
            if self.failure or self.halt.is_set() or any(n not in self.configured or self.actors[n].failed for n in members):
                raise RuntimeError('Explicit commissioning/enrollment or live owner unavailable')
            if self.inflight is not None:raise RuntimeError('One operation is already owned')
            self.next_intent+=1
            self.inflight=self.next_intent;self.phase='queued';self.reason=''
            self.pending=(self.next_intent,target,position,align,self.stop_generation,now_us())
            value={'accepted':True,'queued':True,'intent':self.next_intent}
        self.changed.set();return value

    def stop(self):
        # Source stamp is captured at receipt, including preflight. Never retime
        # the STOP after waiting for a blocked ordinary exchange.
        sent=now_us()//1000
        with self.lock:
            self.stop_generation+=1
            if self.pending is not None:
                self.pending=None;self.inflight=None;self.phase='aborted'

            active=self.active
            if active:
                for name,w in active.workers.items():
                    r=active.reservations[name]
                    w.submit(Envelope(name,'stop',{'boot_nonce':r.boot,'sequence':r.command,'sent_ms':sent}))
            self.reason='Explicit STOP requested'
        self.changed.set();return {'accepted':True,'queued':True}

    def _factory(self,selected,reservation,library,events,**kwargs):
        return ActorWorker(self.actors[selected.device_id],selected,reservation,library,events,**kwargs)

    def _run(self):
        ledger=None
        try:
            try:ledger=Ledger(self.ledger_path) if self.ledger_path is not None else None
            except LedgerError:pass # Telemetry remains usable, no auto-enrollment/recovery.
            for name,p in self.pairings.items():
                selected=self.selections.get(name);floor=None
                if selected and ledger:
                    try:floor=ledger.floor(selected)
                    except LedgerError:selected=None
                else:selected=None
                actor=Actor(p,self.library,selected,floor,period_s=self.period_s)
                self.actors[name]=actor
                if selected:self.configured[name]=selected
            self.started.set()
            while not self.halt.is_set():
                with self.lock:intent,self.pending=self.pending,None
                if intent:
                    ident,target,position,align,generation,received=intent
                    group=None
                    try:
                        with self.lock:
                            if generation!=self.stop_generation:continue
                            if now_us()-received>1000000:raise RuntimeError('Queued intent expired')
                        selected=list(self.configured.values()) if target=='room' else [self.configured[target]]
                        group=Group(selected,ledger,self.library,worker_factory=self._factory)
                        with self.lock:
                            if generation!=self.stop_generation:continue
                            self.active=group;self.last_operation=group;self.phase='preflight';self.reason='';self.last_intent=ident
                        group.start(position,align=align)
                        while not self.halt.is_set():
                            # STOP publishes immediately to owners, and this short
                            # non-I/O gate prevents a concurrent ordinary dispatch.
                            with self.lock:
                                if generation!=self.stop_generation: group.abort('Explicit STOP requested')
                                phase=group.step()
                                self.phase=phase.value;self.reason=group.job.reason
                            if phase in (Phase.COMPLETE,Phase.ABORTED):break
                            self.changed.wait(.002);self.changed.clear()
                    except Exception:
                        with self.lock:self.phase='aborted';self.reason='Physical preflight or execution failed'
                    finally:
                        if group:group.close()
                        with self.lock:
                            self.active=None
                            if self.inflight==ident:self.inflight=None
                self.changed.wait(.01);self.changed.clear()
        except Exception:
            with self.lock:self.failure='Coordinator ownership failed';self.reason=self.failure
        finally:
            self.started.set()
            for actor in self.actors.values():
                try:actor.close()
                except Exception:
                    with self.lock:self.failure='Owner closure failed'
            if ledger:ledger.close()

    def state(self):
        # No network, reservation, clock qualification or control side effect.
        with self.lock:
            phase,reason,active,configured=self.phase,self.reason,self.active,dict(self.configured)
            workers={} if active is None else dict(active.workers)
            intent=self.last_intent
        devices=[];heights=[]
        for name,actor in self.actors.items():
            d=actor.state();s=configured.get(name)
            with actor.lock:last,last_report=actor.last_position,actor.last_report
            w=workers.get(name);report=None if w is None else w.snapshot()[0]
            now=now_us()  # after both owner copies, preserving their source times
            height=source=age=None
            # Current reference loss wins over an older retained coordinate.
            # A failed/refused preflight also remains authoritative after its
            # facade leaves active ownership; it cannot resurrect an old OFF.
            if report is not None:
                if report.reference_valid and report.height_mm is not None:
                    height=report.height_mm;source=report.sampled_us;age=max(0,(now-report.sample_host_earliest_us+999)//1000)
            elif (last and last.reference_valid and last.height_mm is not None and
                  not (last_report and last_report.sampled_us >= last.sampled_us and
                       (not last_report.reference_valid or last_report.height_mm is None))):
                height=last.height_mm;source=last.sampled_us;age=max(0,(now-last.earliest_host_us+999)//1000)
            # Retained coordinates are labelled by original age; never readiness.
            referenced=height is not None and age is not None and age<=1800000 and not actor.failed
            if not referenced:height=None
            position=None if height is None or s is None else 100*(height-s.low_um/1000)/((s.high_um-s.low_um)/1000)
            if position is not None and not 0<=position<=100:position=None;referenced=False
            movement='stopped'
            if referenced and report and report.phase=='moving' and active and active.job:
                movement='opening' if active.job.target_height_mm>report.height_mm else 'closing'
            d.update(control_configured=s is not None,position=position,height_mm=height,position_age_ms=age,
                     position_sample_us=None if source is None else f'{source:016x}',referenced=referenced,state=movement)
            devices.append(d)
            if referenced:heights.append(height)
        all_configured=len(configured)==len(self.pairings)
        low=max((s.low_um/1000 for s in configured.values()),default=0)
        high=min((s.high_um/1000 for s in configured.values()),default=0)
        spread=max(heights)-min(heights) if len(heights)==len(devices) else None
        aligned=spread is not None and spread<=5
        pos=(sum(heights)/len(heights)-low)*100/(high-low) if aligned and all_configured and high>low else None
        if pos is not None and not 0<=pos<=100:pos=None
        group={'id':'room','name':'Room blinds','available':all_configured and all(d['available'] for d in devices),
               'control_configured':all_configured,'position':pos,'state':next((d['state'] for d in devices if d['state']!='stopped'),'stopped'),
               'aligned':aligned,'spread_mm':spread,'phase':phase,'reason':reason,'low_mm':low if all_configured else None,
               'high_mm':high if all_configured else None,'intent':intent}
        return {'schema_version':3,'mode':'physical_control','bridge_id':self.bridge_id,'devices':devices,'group':group}

    def close(self):
        self.stop();self.halt.set();self.changed.set();self.thread.join(10)
        if self.thread.is_alive():raise RuntimeError('Coordinator did not close')
