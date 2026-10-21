import ctypes as C
import json
import importlib.util
import subprocess
import sys
import threading
import urllib.request
from .server import ControlServer
from contextlib import ExitStack
from dataclasses import replace
from unittest.mock import patch
from integrations.thread_transport.wire_fixture import WireFixture
from .actor import ActorWorker
from pathlib import Path
import tempfile
import time
import unittest
from integrations.thread_transport.test_motion import MotionPeer
from integrations.thread_transport.test_transport import LIBRARY
from integrations.thread_bridge.selection import Selection
from integrations.thread_bridge.ledger import Ledger
from integrations.physical_bridge.service import Pairing
from .service import PhysicalControl



def control_schema():
    # Load the actual HA validator without running its HA package entrypoint.
    path=Path(__file__).resolve().parents[1]/'home_assistant/custom_components/smart_blinds/api.py'
    spec=importlib.util.spec_from_file_location('smart_blinds_schema_check',path)
    api=importlib.util.module_from_spec(spec);spec.loader.exec_module(api)
    return api


def selection(peer,name='blind'):
    return Selection(name,'::1',peer.port,'disposable',peer.key,peer.boot,7,0,100000,30000,60000,'fixture-only',True)

def pairing(peer,name='blind'):
    return Pairing(name,name,'::1',peer.port,'disposable',peer.key,peer.boot)

def wait(predicate,timeout=8):
    deadline=time.monotonic()+timeout
    while time.monotonic()<deadline:
        value=predicate()
        if value:return value
        time.sleep(.005)
    raise AssertionError('Bounded fixture wait expired')

class ActorTests(unittest.TestCase):
    def test_control_schema_without_home_assistant_or_aiohttp(self):
        # A clean child cannot accidentally rely on the HA test job's packages.
        # No library/peer is instantiated; the state is the existing pure fixture.
        code="""
import importlib.abc, sys
class NoHA(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname.split('.')[0] in ('homeassistant','aiohttp'):
            raise ModuleNotFoundError('Unexpected framework dependency: '+fullname)
sys.meta_path.insert(0,NoHA())
from copy import deepcopy
from integrations.physical_control.test_actor import control_schema
from integrations.physical_control.test_publication_boundaries import service,PresentationTests
api=control_schema()
s,_=service();state=PresentationTests().state(s)
assert api.validate_control_state(state) is state
for edit in (lambda v:v.update(mode='simulation'),
             lambda v:v['devices'][0].update(charging=True),
             lambda v:v['devices'][0].update(position_age_ms=1800001)):
    bad=deepcopy(state);edit(bad)
    try:api.validate_control_state(bad)
    except api.BridgeError:pass
    else:raise AssertionError('Malformed control state was accepted')
assert not any(n.split('.')[0] in ('homeassistant','aiohttp') for n in sys.modules)
print('actual schema: valid accepted; mode, charge and source-age violations rejected')
"""
        result=subprocess.run([sys.executable,'-S','-c',code],cwd=Path(__file__).resolve().parents[2],
                              capture_output=True,text=True,timeout=10)
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)

    def test_two_jobs_one_owner(self):
        with tempfile.TemporaryDirectory() as tmp, MotionPeer() as peer:
            s=selection(peer);path=Path(tmp)/'ledger'
            with Ledger(path,create=True) as l:l.enroll(s,command_floor=0,message_floor=0)
            service=PhysicalControl('fixture',[pairing(peer)],[s],path,LIBRARY)
            try:
                wait(lambda:service.state()['devices'][0]['available'])
                for target in (55,45):
                    service.move('room',target)
                    wait(lambda:service.phase in ('complete','aborted') and service.active is None)
                    self.assertEqual(service.phase,'complete',(service.reason,peer.diagnostics,
                        [(a.failed, a.current.failure if a.current else None) for a in service.actors.values()]))
                    self.assertTrue(peer.off)
                fn=peer.library.sb_motion_peer_connections;fn.argtypes=[C.c_void_p];fn.restype=C.c_uint
                self.assertEqual(fn(peer.handle),1)
            finally:service.close()
            with Ledger(path) as l:self.assertEqual(l.floor(s),(2,8192))

    def fixtures(self,stack,n=2):
        peers=[stack.enter_context(MotionPeer(boot=99+i,geometry=(-5*i,140+10*i,1400+120*i))) for i in range(n)]
        selected=[replace(selection(p,str(i)),low_um=-5000*i,high_um=140000+10000*i) for i,p in enumerate(peers)]
        folder=stack.enter_context(tempfile.TemporaryDirectory());path=Path(folder)/'ledger'
        with Ledger(path,create=True) as l:
            for s in selected:l.enroll(s,command_floor=0,message_floor=0)
        return peers,selected,path

    def finish(self,service):
        wait(lambda:service.inflight is None and service.phase in ('complete','aborted'),10)
        g=service.last_operation
        return service.phase,(service.reason,g.job.reason if g.job else None,
            [(n,w.failure,w.reusable) for n,w in g.workers.items()])

    def test_seven_persistent_peers_same_physical_height(self):
        with ExitStack() as stack:
            peers,selected,path=self.fixtures(stack,7)
            service=PhysicalControl('seven',[pairing(p,str(i)) for i,p in enumerate(peers)],selected,path,LIBRARY)
            stack.callback(service.close)
            wait(lambda:all(d['available'] for d in service.state()['devices']))
            # Complete HTTP -> service -> Group -> same seven DTLS owners -> OFF.
            server=ControlServer('f'*40,service,port=0)
            http=threading.Thread(target=server.serve_forever);http.start()
            def close_http(): server.shutdown();server.server_close();http.join(1)
            stack.callback(close_http)
            def request(path,body=None):
                req=urllib.request.Request(f'http://127.0.0.1:{server.server_port}'+path,
                    data=None if body is None else json.dumps(body).encode(),
                    headers={'Authorization':'Bearer '+'f'*40,'Content-Type':'application/json'})
                with urllib.request.urlopen(req,timeout=3) as response:return json.load(response)
            initial=[a.observation.received_us for a in service.actors.values()]
            began=time.monotonic()
            receipt=request('/v3/move',{'target':'room','position':50,'align':False})
            self.assertEqual(receipt,{'accepted':True,'queued':True,'intent':1})
            phase,why=self.finish(service)
            self.assertEqual(phase,'complete',(why,[p.diagnostics for p in peers]))
            self.assertEqual(service.last_operation.job.target_height_mm,70)
            heights=list(service.last_operation.job.completed.values())
            self.assertLess(max(heights)-min(heights),1)
            self.assertTrue(all(p.off for p in peers))
            wait(lambda:all(a.observation.received_us>old for a,old in zip(service.actors.values(),initial)))
            state=control_schema().validate_control_state(request('/v3/state'))
            self.assertTrue(state['group']['aligned'])
            self.assertAlmostEqual(state['group']['position'],50,places=1)
            for a in service.actors.values():self.assertEqual(a.session.handshakes,1)
            print('PERSISTENT_LOOPBACK',{'seconds':round(time.monotonic()-began,3),
                'application_bytes':sum(p.body_bytes for p in peers),'requests':sum(p.requests for p in peers),
                'spread_mm':max(heights)-min(heights)})

    def test_no_selection_or_no_enrollment_never_prepares(self):
        for selected_present in (False,True):
            with tempfile.TemporaryDirectory() as tmp,MotionPeer() as peer:
                s=selection(peer);path=Path(tmp)/'ledger'
                with Ledger(path,create=True):pass
                service=PhysicalControl('unconfigured',[pairing(peer)],[s] if selected_present else [],path,LIBRARY)
                try:
                    wait(lambda:service.state()['devices'][0]['available'])
                    before=peer.requests
                    with self.assertRaises(RuntimeError):service.move('room',50)
                    self.assertEqual(peer.requests,before)
                    self.assertFalse(service.state()['devices'][0]['control_configured'])
                    self.assertTrue(peer.off)
                finally:service.close()

    def test_unqualified_preflight_burns_range_then_explicit_retry(self):
        with ExitStack() as stack:
            peers,selected,path=self.fixtures(stack,1);p=peers[0];p.mode(8)
            service=PhysicalControl('fixture',[pairing(p,'0')],selected,path,LIBRARY);stack.callback(service.close)
            wait(lambda:service.state()['devices'][0]['available'])
            service.move('room',50);phase,why=self.finish(service)
            self.assertEqual(phase,'aborted',why)
            self.assertFalse(service.last_operation.workers['0'].active)
            self.assertFalse(service.actors['0'].failed)
            p.mode(0)
            service.move('room',50);phase,why=self.finish(service)
            self.assertEqual(phase,'complete',(why,[p.diagnostics for p in peers]))
            self.assertEqual(service.last_operation.reservations['0'].floor,4096)

    def test_stop_during_motion_and_next_explicit_job(self):
        with ExitStack() as stack:
            peers,selected,path=self.fixtures(stack,2)
            service=PhysicalControl('fixture',[pairing(p,str(i)) for i,p in enumerate(peers)],selected,path,LIBRARY);stack.callback(service.close)
            wait(lambda:all(d['available'] for d in service.state()['devices']))
            service.move('room',90)
            wait(lambda:service.phase in ('moving','aborted'))
            self.assertEqual(service.phase,'moving',(self.finish(service),[p.diagnostics for p in peers]) if service.phase=='aborted' else None)
            service.stop();phase,why=self.finish(service)
            self.assertEqual(phase,'aborted',why)
            self.assertTrue(all(p.off for p in peers))
            self.assertTrue(all(w.reservation.stopped for w in service.last_operation.workers.values()))
            self.assertTrue(all(not a.failed for a in service.actors.values()),why)
            service.move('room',50,align=True);phase,why=self.finish(service)
            self.assertEqual(phase,'complete',(why,[p.diagnostics for p in peers]))

    def test_cooldown_refusal_is_not_queued_for_automatic_later_motion(self):
        with ExitStack() as stack:
            peers,selected,path=self.fixtures(stack,1);p=peers[0];p.mode(16)
            service=PhysicalControl('fixture',[pairing(p,'0')],selected,path,LIBRARY)
            stack.callback(service.close)
            wait(lambda:service.state()['devices'][0]['available'])
            service.move('room',55);phase,why=self.finish(service)
            self.assertEqual(phase,'aborted',why)
            worker=service.last_operation.workers['0']
            self.assertFalse(worker.active)
            self.assertEqual([n for n,_ in worker.calls].count('wake'),1)
            p.mode(0);time.sleep(.05)
            self.assertEqual(service.phase,'aborted')
            self.assertIsNone(service.inflight)
            self.assertTrue(p.off)
            self.assertFalse(service.actors['0'].failed)

    def test_stop_while_initial_telemetry_is_blocked_never_starts_preflight(self):
        from .session import ActorSession
        entered=threading.Event();release=threading.Event();original=ActorSession.poll
        def poll(session):
            entered.set()
            if not release.wait(1):raise AssertionError('Fixture barrier timeout')
            return original(session)
        with ExitStack() as stack:
            peers,selected,path=self.fixtures(stack,1)
            with patch.object(ActorSession,'poll',poll):
                service=PhysicalControl('fixture',[pairing(peers[0],'0')],selected,path,LIBRARY)
                stack.callback(service.close)
                self.assertTrue(entered.wait(1))
                service.move('room',55);wait(lambda:service.active is not None)
                service.stop();release.set()
                phase,why=self.finish(service)
            self.assertEqual(phase,'aborted',why)
            worker=service.last_operation.workers['0']
            self.assertFalse(worker.active)
            self.assertFalse(any(name in ('wake','prepare','commit') for name,_ in worker.calls))
            self.assertFalse(service.actors['0'].failed)
            self.assertTrue(peers[0].off)

    def test_stop_between_status_and_wake_is_observed_before_wake(self):
        entered=threading.Event();release=threading.Event();original=ActorWorker._call
        def call(worker,name,**kw):
            result=original(worker,name,**kw)
            if name=='status':
                entered.set()
                if not release.wait(1):raise AssertionError('Fixture barrier timeout')
            return result
        with ExitStack() as stack:
            peers,selected,path=self.fixtures(stack,1)
            service=PhysicalControl('fixture',[pairing(peers[0],'0')],selected,path,LIBRARY)
            stack.callback(service.close)
            wait(lambda:service.state()['devices'][0]['available'])
            with patch.object(ActorWorker,'_call',call):
                service.move('room',55);self.assertTrue(entered.wait(1))
                service.stop();release.set();phase,why=self.finish(service)
            self.assertEqual(phase,'aborted',why)
            worker=service.last_operation.workers['0']
            self.assertFalse(worker.active)
            self.assertFalse(any(name in ('wake','prepare','commit') for name,_ in worker.calls))
            self.assertFalse(service.actors['0'].failed)
            self.assertTrue(peers[0].off)

    def test_fault_propagates_and_no_reconnect(self):
        with ExitStack() as stack:
            peers,selected,path=self.fixtures(stack,2)
            service=PhysicalControl('fixture',[pairing(p,str(i)) for i,p in enumerate(peers)],selected,path,LIBRARY);stack.callback(service.close)
            wait(lambda:all(d['available'] for d in service.state()['devices']))
            service.move('room',90)
            wait(lambda:service.phase in ('moving','aborted'))
            self.assertEqual(service.phase,'moving',(self.finish(service),[p.diagnostics for p in peers]) if service.phase=='aborted' else None)
            peers[0].mode(2)
            phase,why=self.finish(service);self.assertEqual(phase,'aborted',why)
            self.assertTrue(all(p.off for p in peers))
            self.assertTrue(service.actors['0'].failed)
            with self.assertRaises(RuntimeError):service.move('room',50)

    def test_uncertain_commit_no_retry_and_stop_floor_burned(self):
        with ExitStack() as stack:
            peers,selected,path=self.fixtures(stack,1);p=peers[0]
            wire=stack.enter_context(WireFixture(p.port));s=replace(selected[0],port=wire.port)
            pair=replace(pairing(p,'0'),port=wire.port)
            attempted=[];original=ActorWorker._call
            def call(w,name,**kw):
                if name=='commit':attempted.append(kw['message']);wire.delay(reverse_ms=150)
                return original(w,name,**kw)
            service=PhysicalControl('fixture',[pair],[s],path,LIBRARY);stack.callback(service.close)
            wait(lambda:service.state()['devices'][0]['available'])
            with patch.object(ActorWorker,'_call',call):
                service.move('room',90);phase,why=self.finish(service)
            self.assertEqual(phase,'aborted',why);self.assertEqual(len(attempted),1)
            self.assertTrue(service.actors['0'].failed)
            self.assertEqual(service.last_operation.workers['0'].reservation.cursor,4097)
            wire.delay();time.sleep(.35);self.assertTrue(p.off)
            with self.assertRaises(RuntimeError):service.move('room',50)
