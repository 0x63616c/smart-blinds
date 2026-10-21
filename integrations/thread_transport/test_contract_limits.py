"""Fixture-boundary controls, real DTLS; no executor or physical qualification."""
import json
import os
import secrets
import unittest
from .client import TransportError
from .contract_fixture import ContractPeer,wait
from .test_contract_peer import connect,frame,raw


class LimitsAndEvidence(unittest.TestCase):
    def setUp(self):self.peers=[]
    def peer(self,**kwargs):
        p=ContractPeer(**kwargs);self.peers.append(p);self.addCleanup(p.close);return p
    def tearDown(self):
        if dest:=os.environ.get('SB_CONTRACT_EVIDENCE'):
            with open(dest,'a') as f:f.write(json.dumps(dict(test=self.id(),evidence_kind='synthetic_application_contract',
                hardware_qualified=False,peers=[dict(phase=p.phase,trace=p.trace,decoded_requests=p.decoded_requests,
                    first_fault=p.diagnostic) for p in self.peers]))+'\n')

    def test_decoded_hook_only_copies_authenticated_accepted_packets(self):
        p=self.peer(qualified=True)
        with p.session(key=secrets.token_bytes(32),timeout_ms=100) as wrong:
            with self.assertRaises(TransportError):wrong.status()
        self.assertEqual(p.decoded_requests,[])
        with p.session() as s:
            connect(s);body=frame(s)
            self.assertEqual(raw(s,5,body[:-1])[0],128)
            self.assertEqual(raw(s,5,frame(s,boot=100))[0],163)
            self.assertEqual(p.decoded_requests,[])
            self.assertEqual(raw(s,5,body)[0],68)
            accepted=p.decoded_requests;self.assertEqual(len(accepted),1)
            r=accepted[0]
            self.assertEqual((r['connection'],r['boot'],r['kind'],r['message'],r['command']),(1,99,1,1,1))
            self.assertEqual((r['origin_um'],r['target_um'],r['speed_um_s'],r['accel_um_s2']),(50000,55000,20000,40000))
            self.assertEqual(raw(s,5,body)[0],163)
            self.assertEqual(p.decoded_requests,accepted)
            wait(lambda:p.phase=='preparing')
            self.assertEqual(p.decoded_requests,accepted)
            self.assertIsNone(p.diagnostic)

    def test_native_limits_independently_reject_outside_target_speed_or_acceleration(self):
        for violation in ({'target_um':70001},{'speed_um_s':10001},{'accel_um_s2':20001}):
            with self.subTest(violation=violation):
                p=self.peer(qualified=True,limits=(30000,70000,10000,20000))
                with p.session() as s:
                    connect(s)
                    values=dict(target_um=52000,speed_um_s=10000,accel_um_s2=20000);values.update(violation)
                    self.assertEqual(raw(s,5,frame(s,**values))[0],68)
                    wait(lambda:p.phase=='fault')
                    self.assertEqual(s.motion_status().result,'invalid')
                    self.assertFalse(p.script(1,'ready'));self.assertFalse(p.script(1,'synthetic_terminal',52000))
                    self.assertEqual(p.diagnostic['reason'],'invalid')
                    first=p.diagnostic.copy()
                    self.assertEqual(len(p.decoded_requests),1)
                    self.assertEqual(p.diagnostic,first)
                    self.assertFalse(any(t['event']=='scheduled_start' for t in p.trace))

if __name__=='__main__':unittest.main()
