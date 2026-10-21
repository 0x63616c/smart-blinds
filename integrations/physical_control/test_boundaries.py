"""Deterministic ownership boundaries, independent of scheduler/RF timing."""
import threading
import unittest
from dataclasses import replace
from unittest.mock import patch
from integrations.home_assistant.coordinator import Envelope
from integrations.thread_bridge.worker import Mailbox
from integrations.thread_bridge.ledger import Reservation
from integrations.thread_transport.client import ProtocolError
from .session import ActorSession
from .test_handoff import read

class Boundaries(unittest.TestCase):
    def session(self):
        s=ActorSession.__new__(ActorSession)
        s._lock=threading.Lock();s._handle=None;s._failed=False
        s.expected_boot=99;s.command_floor=0;s._message=0;s.reservation=None;s.last_handoff=None
        return s
    def test_duplicate_stop_preserves_first_source_and_cannot_add_wire_attempt(self):
        q=Mailbox();q.put(Envelope('x','prepare',{}));q.put(Envelope('x','lease',{'sent_ms':100}))
        self.assertTrue(q.put(Envelope('x','stop',{'sent_ms':101})))
        self.assertTrue(q.put(Envelope('x','stop',{'sent_ms':999})))
        self.assertEqual(q.stop_source_ms,101)
        self.assertFalse(q.put(Envelope('x','lease',{'sent_ms':1000})))
        self.assertFalse(q.commands);self.assertIsNone(q.lease)
        r=Reservation('x',99,1,0,4096,1)
        self.assertEqual(r.take_stop(),4096)
        with self.assertRaises(RuntimeError):r.take_stop()
    def test_no_floor_lowering_used_range_or_failed_handle(self):
        s=self.session();first=Reservation('x',99,1,0,4096,1);s.reserve(first)
        for r in (first,Reservation('x',99,2,0,4096,2),Reservation('x',99,2,4096,8192,4097,True),
                  Reservation('x',100,2,4096,8192,4097),Reservation('x',99,2,4096,8191,4097)):
            with self.subTest(r=r),self.assertRaises(ProtocolError):s.reserve(r)
        s._failed=True
        with self.assertRaises(ProtocolError):s.reserve(Reservation('x',99,2,4096,8192,4097))
    def test_sent_attempt_requires_same_terminal_and_received_floor_off_proof(self):
        s=self.session();s.reserve(Reservation('x',99,7,0,4096,1));s._message=4096
        next=Reservation('x',99,8,4096,8192,4097)
        h=read()
        s.last_handoff=h
        with patch('integrations.physical_control.session._now_us',return_value=h.receipt_us),self.assertRaises(ProtocolError):
            s.reserve(Reservation('x',99,8,0,4096,1))
        for value in (None,replace(h,command=6),replace(h,received_message=4095),replace(h,settled_off=False)):
            s.last_handoff=value
            with patch('integrations.physical_control.session._now_us',return_value=h.receipt_us),self.assertRaises(ProtocolError):s.reserve(next)
        s.last_handoff=h
        with patch('integrations.physical_control.session._now_us',return_value=h.earliest_host_us+30001),self.assertRaises(ProtocolError):s.reserve(next)
        with patch('integrations.physical_control.session._now_us',return_value=h.receipt_us):s.reserve(next)
        self.assertEqual(s.consumed_message,4096)
        self.assertIsNone(s._clock);self.assertFalse(s._qualified_clock)
        self.assertEqual(s._command,0)
    def test_settling_terminal_does_not_replace_live_power_or_clock_evidence(self):
        from types import SimpleNamespace
        import queue
        from integrations.thread_bridge.test_bridge import selection
        from .actor import ActorWorker
        w=ActorWorker(SimpleNamespace(session=None),selection(),Reservation('a',99,7,0,4096,1),None,queue.Queue())
        w.active=True;w.last_clock=123
        h=replace(read(),phase='settling',settled_off=False)
        self.assertFalse(w._completion(h))
        self.assertTrue(w.terminal)
        self.assertIsNone(w.completion())
        self.assertEqual(w.last_clock,123)
        self.assertFalse(w.shutdown.is_set())

    def test_preflight_refusal_burns_unused_range_without_fabricated_terminal(self):
        s=self.session();s.reserve(Reservation('x',99,1,0,4096,1))
        s.reserve(Reservation('x',99,2,4096,8192,4097))
        self.assertEqual((s.command_floor,s.consumed_message),(2,4096))
        self.assertIsNone(s.last_handoff)

if __name__=='__main__':unittest.main()
