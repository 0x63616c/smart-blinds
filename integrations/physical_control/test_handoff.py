import json
import unittest
from dataclasses import replace
from .handoff import decode, History
from integrations.thread_transport.client import ProtocolError

def body(**change):
    v=dict(version=1,boot=f'{99:016x}',nonce=f'{1:016x}',sampled_us=f'{1000000:016x}',
        responded_us=f'{1005000:016x}',command=f'{7:016x}',received_message=f'{4096:016x}',
        phase='idle',result='finished',reference_valid=True,height_mm=50.0,settled_off=True)
    v.update(change);return json.dumps(v).encode()

def read(payload=None):
    return decode(payload or body(),boot=99,nonce=1,sent_host_us=2000000,received_us=2002000)

class HandoffTests(unittest.TestCase):
    def test_original_source_interval_and_age_boundary(self):
        r=read()
        self.assertEqual(r.earliest_host_us,2000000-7071)
        self.assertEqual(r.latest_host_us,2002000-2970)
        self.assertTrue(r.current(r.earliest_host_us+30000))
        self.assertFalse(r.current(r.earliest_host_us+30001))
        self.assertFalse(r.current(r.receipt_us-1))
        self.assertFalse(replace(r,settled_off=False).current(r.receipt_us))
    def test_delayed_packet_is_not_fresh_completion(self):
        r=decode(body(),boot=99,nonce=1,sent_host_us=2000000,received_us=2050000)
        self.assertFalse(r.current(r.receipt_us))
    def test_empty_default_is_absent_not_off(self):
        r=read(body(sampled_us='0000000000000000',phase='unreferenced',result='none',
            command='0000000000000000',received_message='0000000000000000',reference_valid=False,
            height_mm=None,settled_off=False))
        self.assertFalse(r.current(r.receipt_us))
    def test_strict_binding_history_and_shape(self):
        for kw in [dict(boot=f'{100:016x}'),dict(nonce=f'{2:016x}'),dict(version=True),dict(extra=1),
                   dict(sampled_us=f'{1006000:016x}'),dict(height_mm=float('nan')),
                   dict(reference_valid=False),dict(phase='moving'),dict(result='accepted')]:
            with self.subTest(kw=kw),self.assertRaises(ProtocolError):read(body(**kw))
        with self.assertRaises(ProtocolError):
            decode(body(),boot=99,nonce=1,sent_host_us=3,received_us=2)
    def test_old_nonce_source_message_and_conflicting_terminal(self):
        first=read();h=History();h.accept(first)
        for r in [first,replace(first,nonce=2,sampled_us=first.sampled_us-1),
                  replace(first,nonce=2,received_message=4095),replace(first,nonce=2,command=6),
                  replace(first,nonce=2,height_mm=49),replace(first,nonce=2,result='stopped')]:
            with self.subTest(r=r),self.assertRaises(ProtocolError):h.accept(r)
        h.accept(replace(first,nonce=2,settled_off=False))
        h.accept(replace(first,nonce=3,sampled_us=first.sampled_us+1,command=8,received_message=8192))
    def test_guard_rounding_encloses_slow_and_fast_source_clocks(self):
        for delta in (0,1,999,1000,1999,2000,9999,27000,30000):
            r=read(body(responded_us=f'{1000000+delta:016x}'))
            for factor in (.99,1,1.01):
                for error in (-2000,0,2000):
                    age=max(0,delta+error)/factor
                    for network in (0,2000):
                        source=2002000-network-age
                        self.assertLessEqual(r.earliest_host_us,source)
                        self.assertGreaterEqual(r.latest_host_us,source)

if __name__=='__main__':unittest.main()
