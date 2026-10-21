"""Seven real DTLS peers; synthetic application observations, no motor evidence."""
import json
import os
from pathlib import Path
import tempfile
import threading

from homeassistant.helpers import entity_registry as er
from homeassistant.exceptions import HomeAssistantError
from pytest_homeassistant_custom_component.common import MockConfigEntry
import pytest

from integrations.physical_bridge.service import Pairing
from integrations.physical_control.service import PhysicalControl
from integrations.physical_control.server import ControlServer
from integrations.thread_bridge.ledger import Ledger
from integrations.thread_bridge.selection import Selection
from integrations.thread_transport.contract_fixture import ContractPeer,wait
from custom_components.smart_blinds.api import validate_control_state

TOKEN='disposable-seven-scripted-application-token-00000000'
# Independent synthetic commissioning inputs, NOT physical qualification records.
# Intersection [30,70]mm; group55% must be52mm. Own-travel55% would disagree.
LIMITS=[(5000*i,100000-5000*i,30000-3000*i if i<6 else 10000,60000-5000*i if i<6 else 20000) for i in range(7)]
TARGET=52000


class Harness:
    def __init__(self,qualified):
        self.folder=tempfile.TemporaryDirectory();self.path=Path(self.folder.name)/'ledger'
        self.peers={};self.selections=[];self.service=None;self.server=None;self.http=None
        self.qualified=qualified;self.initial={};self.closed=False;self.floors={}
        try:
            pairs=[]
            for i,limits in enumerate(LIMITS):
                name=f'blind{i}';p=ContractPeer(qualified=qualified,boot=100+i,limits=limits);self.peers[name]=p
                self.selections.append(Selection(name,'::1',p.port,'fixture',p.key,p.boot,7,*limits,
                                                f'synthetic-range-{i}',True))
                pairs.append(Pairing(name,f'Scripted blind {i}','::1',p.port,'fixture',p.key,p.boot))
            with Ledger(self.path,create=True) as ledger:
                if qualified:
                    for i,s in enumerate(self.selections):ledger.enroll(s,command_floor=i*10,message_floor=i*4096)
            self.service=PhysicalControl('seven-contract-fixture',pairs,self.selections if qualified else [],
                                         self.path,Path(os.environ['SB_THREAD_LIBRARY']))
            wait(lambda:len(self.service.state()['devices'])==7 and all(x['available'] for x in self.service.state()['devices']))
            self.initial={n:a.observation.received_us for n,a in self.service.actors.items()}
            self.server=ControlServer(TOKEN,self.service,port=0)
            self.http=threading.Thread(target=self.server.serve_forever);self.http.start()
        except BaseException:
            self.close();raise

    def phases(self):return {n:p.phase for n,p in self.peers.items()}
    def commands(self):return {n:r.command for n,r in self.service.last_operation.reservations.items()}
    def evidence(self,stage,passed):
        group=self.service.last_operation
        return dict(evidence_kind='synthetic_application_contract',hardware_qualified=False,stage=stage,passed=passed,
            configured_limits=LIMITS,expected_group_target_um=TARGET,application=self.service.state(),
            peers={n:dict(phase=p.phase,trace=p.trace,decoded_requests=p.decoded_requests,first_fault=p.diagnostic) for n,p in self.peers.items()},
            workers={} if group is None else {n:dict(failure=w.failure,reusable=w.reusable,calls=list(w.calls),
                stop_sent=w.stop_sent,completion=None if w.completion() is None else vars(w.completion())) for n,w in group.workers.items()})
    def close(self):
        if self.closed:return
        self.closed=True
        try:
            if self.server:
                if self.http:self.server.shutdown()
                self.server.server_close()
                if self.http:
                    self.http.join(2)
                    assert not self.http.is_alive(),'HTTP test owner did not close'
            elif self.service:self.service.close()
            if self.qualified and self.service:
                with Ledger(self.path) as ledger:self.floors={s.device_id:ledger.floor(s) for s in self.selections}
        finally:
            for p in self.peers.values():p.close()
            self.folder.cleanup()


def assert_decoded_plan(h):
    actual=[]
    for i,(name,p) in enumerate(h.peers.items()):
        requests=p.decoded_requests
        prepares=[r for r in requests if r['kind']==1]
        assert len(prepares)==1,(name,prepares)
        r=prepares[0];actual.append(r)
        assert r['connection']==1 and r['boot']==100+i and r['calibration']==7 and r['probe']>0
        assert r['command']==i*10+1 and r['message']==i*4096+1
        assert (r['origin_um'],r['target_um'],r['speed_um_s'],r['accel_um_s2'])==(50000,TARGET,10000,20000)
        assert LIMITS[i][0]<=r['target_um']<=LIMITS[i][1]
        # The observation hook is passive: a second read copies the same prefix.
        assert p.decoded_requests[:len(requests)]==requests
    assert len({r['start_us'] for r in actual})==1
    assert len({r['sent_us'] for r in actual})==1
    assert actual[0]['start_us']-actual[0]['sent_us']==3000000
    own_fraction=[lo+(hi-lo)*.55 for lo,hi,*_ in LIMITS]
    assert len(set(own_fraction))==7 and any(v!=TARGET for v in own_fraction)


def script_all(h,event,*,wrong_terminal=False,skip=None):
    commands=h.commands()
    for name,p in h.peers.items():
        if name==skip:continue
        height=60000 if wrong_terminal and name=='blind6' else TARGET
        assert not p.script(commands[name]+1000,event,height)
        assert p.script(commands[name],event,height),(name,event,p.phase)


@pytest.mark.parametrize('scenario',['unqualified','complete','missing_ready','wrong_terminal'])
async def test_seven_peer_ha_group_application(hass,socket_enabled,scenario):
    h=await hass.async_add_executor_job(Harness,scenario!='unqualified')
    entry=MockConfigEntry(domain='smart_blinds',unique_id='seven-contract-fixture',data={
        'base_url':f'http://127.0.0.1:{h.server.server_port}','access_token':TOKEN,'mode':'physical_control'})
    entry.add_to_hass(hass);stage='ha-setup';passed=False
    try:
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        cover=er.async_get(hass).async_get_entity_id('cover','smart_blinds','seven-contract-fixture:room:cover')
        assert cover is not None
        if scenario=='unqualified':
            assert hass.states.get(cover).state=='unavailable'
            with pytest.raises(HomeAssistantError):await entry.runtime_data.move('room',55)
            assert h.service.last_operation is None
            for p in h.peers.values():
                assert p.decoded_requests==[] and not p.script(1,'ready')
        else:
            stage='ha-move'
            await hass.services.async_call('cover','set_cover_position',{'entity_id':cover,'position':55},blocking=True)
            await hass.async_add_executor_job(wait,lambda:all(p.phase=='preparing' for p in h.peers.values()) or any(p.phase=='fault' for p in h.peers.values()))
            assert set(h.phases().values())=={'preparing'},h.phases()
            assert_decoded_plan(h)
            assert not h.service.last_operation.job.prepared
            stage='script-ready'
            script_all(h,'ready',skip='blind6' if scenario=='missing_ready' else None)
            if scenario=='missing_ready':
                await hass.async_add_executor_job(wait,lambda:h.service.phase=='aborted')
                assert h.service.reason=='member missing at prepare deadline',h.service.reason
                await hass.async_add_executor_job(wait,lambda:all(p.phase=='settling' for p in h.peers.values()) or any(p.phase=='fault' for p in h.peers.values()))
                assert set(h.phases().values())=={'settling'},h.phases()
                assert h.service.last_operation.job.prepared=={f'blind{i}' for i in range(6)}
                for i,(name,p) in enumerate(h.peers.items()):
                    assert not any(r['kind']==2 for r in p.decoded_requests)
                    assert not any(t['event']=='scheduled_start' for t in p.trace)
                    stops=[r for r in p.decoded_requests if r['kind']==4]
                    assert len(stops)==1 and stops[0]['message']==(i+1)*4096
                    assert any(r['kind']==3 for r in p.decoded_requests) # queued peers stay leased, never implicitly READY
                stage='script-stopped-off';script_all(h,'synthetic_off')
            else:
                await hass.async_add_executor_job(wait,lambda:all(p.phase=='moving' for p in h.peers.values()) or any(p.phase=='fault' for p in h.peers.values()))
                assert set(h.phases().values())=={'moving'},h.phases()
                for p in h.peers.values():
                    assert len([r for r in p.decoded_requests if r['kind']==2])==1
                    assert len([t for t in p.trace if t['event']=='scheduled_start'])==1
                stage='script-terminal';script_all(h,'synthetic_terminal',wrong_terminal=scenario=='wrong_terminal')
                await hass.async_add_executor_job(wait,lambda:all(w.terminal for w in h.service.last_operation.workers.values()))
                assert h.service.phase!='complete'
                assert all(w.completion() is None for w in h.service.last_operation.workers.values())
                stage='script-off';script_all(h,'synthetic_off')
            await hass.async_add_executor_job(wait,lambda:h.service.inflight is None)
            expected='complete' if scenario=='complete' else 'aborted'
            assert h.service.phase==expected,(h.service.phase,h.service.reason)
            await hass.async_add_executor_job(wait,lambda:all(a.observation.received_us>h.initial[n] for n,a in h.service.actors.items()))
            state=h.service.state();validate_control_state(state)
            if scenario=='complete':
                assert state['group']['aligned'] and state['group']['spread_mm']==0
                assert state['group']['position']==55
                assert {d['height_mm'] for d in state['devices']}=={52}
                assert len({round(d['position'],5) for d in state['devices']})==7
                assert len(h.service.last_operation.job.completed)==7
                await entry.runtime_data.async_refresh()
                assert hass.states.get(cover).attributes['current_position']==55
            elif scenario=='wrong_terminal':
                assert h.service.reason=='blind6: stopped before target',h.service.reason
                assert not state['group']['aligned'] and state['group']['position'] is None
                assert state['group']['spread_mm']==8
                assert h.service.last_operation.workers['blind6'].completion().height_mm==60
                assert len(h.service.last_operation.job.completed)<7
            for w in h.service.last_operation.workers.values():
                assert w.failure is None and w.reusable
                assert w.completion().settled_off
        for name,p in h.peers.items():
            assert len([t for t in p.trace if t['event']=='connected'])==1
            session=h.service.actors[name].session
            assert (session if h.qualified else session._handle).handshakes==1
        assert await hass.config_entries.async_unload(entry.entry_id)
        passed=True
    finally:
        evidence=h.evidence(stage,passed)
        await hass.async_add_executor_job(h.close)
        evidence['durable_floors_after_close']=h.floors
        if dest:=os.environ.get('SB_CONTRACT_EVIDENCE'):
            with open(dest,'a') as f:f.write(json.dumps(evidence,sort_keys=True)+'\n')
        if passed and scenario!='unqualified':
            assert h.floors=={f'blind{i}':(i*10+1,(i+1)*4096) for i in range(7)}


def test_evidence_owns_call_history_without_transport():
    """Cleanup may append calls after capture; retained evidence must not change."""
    from types import SimpleNamespace
    calls=[('qualify_clock',7321),('motion_status',240)]
    worker=SimpleNamespace(failure=None,reusable=False,calls=calls,stop_sent=False,completion=lambda:None)
    h=Harness.__new__(Harness)
    h.peers={}
    h.service=SimpleNamespace(last_operation=SimpleNamespace(workers={'blind3':worker}),state=lambda:{'phase':'armed'})
    captured=h.evidence('before-close',False)
    before=json.dumps(captured,sort_keys=True)
    assert captured['workers']['blind3']['calls'] is not calls
    calls.append(('stop',40000))
    assert json.dumps(captured,sort_keys=True)==before
    calls.clear()
    assert captured['workers']['blind3']['calls']==[('qualify_clock',7321),('motion_status',240)]
    assert json.dumps(captured,sort_keys=True)==before
