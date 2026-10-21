"""Real DTLS and real deadlines around a separately named scripted fixture.

No motion executor, PWM, physical observation or virtual time is used.
"""
import json
import os
import secrets
import struct
import time
import unittest
from .client import ProtocolError,TransportError,_now_us
from .motion import encode
from .contract_fixture import ContractPeer,wait


def raw(s,kind,body=b''):
    with s._lock:return s._exchange(kind,body)


def connect(s):
    state=s.status()
    if not state.awake:s.wake(state.boot,state.last_wake+1)
    readiness=s.readiness();s.qualify_clock(state.boot,readiness.last_probe+1)
    return s.motion_status()


def frame(s,*,sent=None,**change):
    now=_now_us();value=dict(boot=s.expected_boot,message=1,command=1,sent_us=now if sent is None else sent,
        calibration=7,probe=s._clock_probe,start_us=now+3000000,origin_um=50000,target_um=55000,speed_um_s=20000,accel_um_s2=40000)
    value.update(change);return encode(1,**value)


class ContractTests(unittest.TestCase):
    def setUp(self):self.peers=[]
    def peer(self,**kwargs):
        p=ContractPeer(**kwargs);self.peers.append(p);self.addCleanup(p.close);return p
    def tearDown(self):
        if dest:=os.environ.get('SB_CONTRACT_EVIDENCE'):
            with open(dest,'a') as f:f.write(json.dumps(dict(test=self.id(),evidence_kind='synthetic_application_contract',
                hardware_qualified=False,peers=[dict(phase=p.phase,trace=p.trace) for p in self.peers]))+'\n')
    def test_empty_qualification_and_wrong_identity_remain_closed(self):
        p=self.peer()
        with p.session() as s:
            self.assertFalse(s.status().io_qualified)
            r=connect(s);self.assertFalse(r.io_qualified);self.assertFalse(r.reference_valid)
            with self.assertRaises(ProtocolError):
                s.prepare(message=1,command=1,sent_us=_now_us(),start_us=_now_us()+3000000,
                    origin_um=50000,target_um=55000,speed_um_s=20000,accel_um_s2=40000)
            self.assertFalse(p.script(1,'ready'));self.assertFalse(p.script(1,'synthetic_off'))
        with p.session(key=secrets.token_bytes(32),timeout_ms=100) as s:
            with self.assertRaises(TransportError):s.status()
        self.assertFalse(any(t['event']=='queued' for t in p.trace))
        self.assertEqual(len([t for t in p.trace if t['event']=='connected']),1)

    def test_shared_decoder_boot_and_replay_precede_script(self):
        p=self.peer(qualified=True)
        with p.session() as s:
            connect(s);body=frame(s)
            for malformed in (body[:-1],bytes([2])+body[1:],body[:2]+b'\1'+body[3:]):
                self.assertEqual(raw(s,5,malformed)[0],128)
            self.assertEqual(raw(s,5,frame(s,boot=100))[0],163)
            self.assertEqual(raw(s,5,body)[0],68)
            self.assertEqual(raw(s,5,body)[0],163)
            wait(lambda:p.phase=='preparing')
            self.assertFalse(p.script(2,'ready'));self.assertFalse(p.script(1,'synthetic_off'))
            self.assertEqual(s.motion_status().phase,'preparing')
            self.assertTrue(p.script(1,'ready'));wait(lambda:s.motion_status().ready)
            self.assertFalse(p.script(1,'ready'))
            self.assertFalse(p.script(1,'synthetic_terminal',55000))

    def test_old_and_future_source_packets_never_become_ready(self):
        for delta in (-200000,200000):
            with self.subTest(delta=delta):
                p=self.peer(qualified=True)
                with p.session() as s:
                    connect(s);self.assertEqual(raw(s,5,frame(s,sent=_now_us()+delta))[0],68)
                    wait(lambda:p.phase=='fault')
                    r=s.motion_status();self.assertEqual(r.result,'stale');self.assertFalse(r.ready)
                    self.assertFalse(p.script(1,'ready'))
                    self.assertFalse(any(t['event']=='script_ready' for t in p.trace))

    def test_wrong_probe_cannot_borrow_clock_qualification(self):
        p=self.peer(qualified=True)
        with p.session() as s:
            connect(s);self.assertEqual(raw(s,5,frame(s,probe=s._clock_probe+1))[0],68)
            wait(lambda:p.phase=='fault');self.assertEqual(s.motion_status().result,'stale')

    def test_original_source_lease_expires_without_scripted_readiness(self):
        for age in (0,80000):
            with self.subTest(original_source_age_us=age):
                p=self.peer(qualified=True)
                with p.session() as s:
                    connect(s);sent=_now_us()-age;self.assertEqual(raw(s,5,frame(s,sent=sent))[0],68)
                    wait(lambda:p.phase=='preparing')
                    # No READY script and no lease sender: waiting cannot cause readiness.
                    wait(lambda:p.phase=='fault')
                    r=s.motion_status();self.assertEqual(r.result,'deadline')
                    fault=next(t for t in p.trace if t['event']=='fault')
                    queued=next(t for t in p.trace if t['event']=='queued')
                    # Both trace stamps are DEVICE monotonic time. Python and
                    # C++ clocks can have different epochs on macOS; production
                    # exchanges already use the real qualified Projection.
                    self.assertLessEqual(fault['at_us']-queued['at_us'],300000-age)
                    self.assertFalse(p.script(1,'ready'));self.assertFalse(p.script(1,'synthetic_off'))
                    self.assertFalse(any(t['event']=='scheduled_start' for t in p.trace))

    def test_oversized_frame_rejected_locally_without_peer_control(self):
        p=self.peer(qualified=True)
        with p.session() as s:
            connect(s)
            with self.assertRaises(TransportError):raw(s,5,frame(s)+b'\0')
            self.assertTrue(s._failed)
            self.assertFalse(any(t['event']=='queued' for t in p.trace))

    def test_authenticated_stop_bypasses_clock_but_never_fabricates_off(self):
        p=self.peer(qualified=True)
        with p.session() as s:
            connect(s);self.assertEqual(raw(s,5,frame(s))[0],68);wait(lambda:p.phase=='preparing')
            # Production STOP semantics: authentic new message/boot, even an old
            # source time stops. It cannot renew lease or establish physical OFF.
            self.assertTrue(s.stop(message=4096,command=1,sent_us=1))
            wait(lambda:p.phase=='settling')
            r=s.motion_status();self.assertEqual(r.result,'stopped');self.assertFalse(r.ready)
            self.assertFalse(p.script(1,'ready'));self.assertFalse(p.script(2,'synthetic_off'))
            self.assertTrue(p.script(1,'synthetic_off'))
            self.assertEqual(p.phase,'idle')
            self.assertFalse(p.script(1,'synthetic_off'))
            self.assertEqual(raw(s,5,frame(s,message=4095))[0],163)

    def test_reconnect_preserves_floor_and_revokes_active_script(self):
        p=self.peer(qualified=True)
        with p.session() as first:
            connect(first);body=frame(first);self.assertEqual(raw(first,5,body)[0],68)
            wait(lambda:p.phase=='preparing')
            with p.session() as second:
                second.status();wait(lambda:p.phase=='fault')
                self.assertEqual(raw(second,5,body)[0],163)
                self.assertFalse(p.script(1,'ready'));self.assertFalse(p.script(1,'synthetic_off'))
        self.assertEqual(len([t for t in p.trace if t['event']=='connected']),2)

if __name__=='__main__':unittest.main()
