import dataclasses
import json
import os
from pathlib import Path
import queue
import secrets
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch
from integrations.home_assistant.coordinator import Envelope, Phase
from integrations.thread_transport.motion import Report
from .group import Group
from .ledger import Ledger, LedgerError
from .mapping import micrometres, source_stamp, normalize_plan
from .selection import Selection
from .worker import Mailbox, Worker


def selection(name='a', **changes):
    return dataclasses.replace(Selection(name,'::1',55555,'disposable',secrets.token_bytes(32),99,7,
        0,140000,20000,40000,'synthetic-test-only',True),**changes)


class LedgerTests(unittest.TestCase):
    def test_explicit_selection_and_create(self):
        with tempfile.TemporaryDirectory() as folder:
            p=Path(folder)/'ledger.db'
            with self.assertRaises(LedgerError): Ledger(p)
            with Ledger(p,create=True) as ledger:
                with self.assertRaises(ValueError): ledger.enroll(selection(commissioned=False),command_floor=0,message_floor=0)
                with self.assertRaises(LedgerError): ledger.reserve([selection()])
                self.assertEqual(p.stat().st_mode&0o777,0o600)
                self.assertEqual(ledger.db.execute('PRAGMA synchronous').fetchone(),(3,))

    def test_atomic_ranges_stop_highest_and_restart_burns_unused(self):
        with tempfile.TemporaryDirectory() as folder:
            p=Path(folder)/'ledger.db'; a,b=selection(),selection('b')
            with Ledger(p,create=True) as ledger:
                ledger.enroll(a,command_floor=1,message_floor=5)
                with self.assertRaises(LedgerError): ledger.reserve([a,b])
                ledger.enroll(b,command_floor=20,message_floor=30)
                r=ledger.reserve([a,b],count=10)
                self.assertEqual((r['a'].command,r['a'].take(),r['a'].take_stop()),(2,6,15))
                with self.assertRaises(LedgerError): r['a'].take()
                with self.assertRaises(LedgerError): r['a'].take_stop()
            with Ledger(p) as ledger:
                r=ledger.reserve([a,b],count=10)
                self.assertEqual((r['a'].command,r['a'].floor,r['b'].floor),(3,15,40))
                with self.assertRaises(LedgerError): ledger.reserve([dataclasses.replace(a,calibration=8)])
                with self.assertRaises(LedgerError): ledger.enroll(a,command_floor=0,message_floor=0)

    def test_no_write_no_reservation_and_changed_boot_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            p=Path(folder)/'ledger.db';a=selection()
            with Ledger(p,create=True) as ledger:
                ledger.enroll(a,command_floor=0,message_floor=0)
                ledger.db.execute('PRAGMA query_only=ON')
                with self.assertRaises(LedgerError): ledger.reserve([a])
                ledger.db.execute('PRAGMA query_only=OFF')
                with self.assertRaises(LedgerError): ledger.reserve([dataclasses.replace(a,boot=100)])
                self.assertEqual(ledger.reserve([a])['a'].command,1)
            with self.assertRaises(LedgerError): ledger.reserve([a])

    def test_crash_after_committed_reservation_burns_it(self):
        with tempfile.TemporaryDirectory() as folder:
            p=Path(folder)/'ledger.db'; a=selection()
            with Ledger(p,create=True) as ledger: ledger.enroll(a,command_floor=0,message_floor=0)
            # Key is intentionally not part of the durable binding or child args.
            source='''import os,sys\nfrom pathlib import Path\nfrom integrations.thread_bridge.test_bridge import selection\nfrom integrations.thread_bridge.ledger import Ledger\nl=Ledger(Path(sys.argv[1])); l.reserve([selection()],count=100); os._exit(0)'''
            subprocess.run([sys.executable,'-c',source,str(p)],check=True)
            with Ledger(p) as ledger:
                r=ledger.reserve([a])['a']
                self.assertEqual((r.command,r.floor),(2,100))
            self.assertNotIn(a.key,p.read_bytes())

    def test_exclusive_corruption_and_uint64(self):
        with tempfile.TemporaryDirectory() as folder:
            p=Path(folder)/'ledger.db'; a=selection()
            with Ledger(p,create=True) as ledger:
                with self.assertRaises(LedgerError): Ledger(p)
                ledger.enroll(a,command_floor=2**63,message_floor=2**64-5)
                r=ledger.reserve([a],count=4)['a']
                self.assertEqual((r.command,r.take_stop()),(2**63+1,2**64-1))
                with self.assertRaises(LedgerError): ledger.reserve([a])
            p.write_bytes(b'broken database')
            with self.assertRaises(LedgerError): Ledger(p)


class MappingQueueTests(unittest.TestCase):
    def test_units_reject_lossy_values(self):
        self.assertEqual(micrometres(-123.456),-123456)
        for value in (True,float('nan'),1.00001,1e9):
            with self.assertRaises(ValueError): micrometres(value)

    def test_fractional_mean_normalizes_once_and_rechecks_boundaries(self):
        from integrations.home_assistant.coordinator import begin_group,Device
        for sign in (-1,1):
            members=[Device(str(i),99,0,7,-100,100,sign*(10+i*.001),20,40,1000,0) for i in range(2)]
            job,envelopes=begin_group(members,50.00025,1000)
            normalize_plan(job)
            # Explicit ties-to-even: ±10.0005 becomes ±10.000 mm.
            self.assertEqual({c['start_height_mm'] for c in job.commands.values()},{sign*10})
            self.assertEqual({c['target_height_mm'] for c in job.commands.values()},{0})
            self.assertEqual(job.target_height_mm,envelopes[0].payload['target_height_mm'])
        members=[Device('a',99,0,7,.0004,100,50,20,40,1000,0)]
        job,_=begin_group(members,0,1000)
        with self.assertRaises(ValueError): normalize_plan(job) # Rounding must not clamp outside range.
        self.assertEqual(job.target_height_mm,.0004)
        job,_=begin_group([Device('a',99,0,7,-100,100,0,20,40,1000,0)],50,1000)
        job.commands['a']['start_height_mm']=5.0006
        with self.assertRaises(ValueError): normalize_plan(job)

    def test_source_interval_rounds_outward_once(self):
        # Report metadata is authenticated and already validated by MotionSession.
        from types import SimpleNamespace
        r=SimpleNamespace(new_sample=True,sampled_us=17,sample_host_earliest_us=1000123,clock_error_us=1111)
        s=source_stamp(r,1005)
        self.assertLessEqual((s.sample_ms-s.clock_error_ms)*1000,1000123)
        self.assertGreaterEqual((s.sample_ms+s.clock_error_ms)*1000,1002345)
        self.assertEqual(s.sequence,17)
        r.clock_error_us=10000
        with self.assertRaises(ValueError): source_stamp(r,1012) # Outward bound exceeds 10 ms.
        r.clock_error_us=1; r.new_sample=False
        with self.assertRaises(ValueError): source_stamp(r,1005)
        r.new_sample=True
        with self.assertRaises(ValueError): source_stamp(r,1200)

    def test_mailbox_latest_original_lease_and_stop_preempt(self):
        q=Mailbox()
        for i in range(4): self.assertTrue(q.put(Envelope('a','prepare',{'sent_ms':i})))
        self.assertFalse(q.put(Envelope('a','commit',{})))
        for i in (10,9,12): self.assertTrue(q.put(Envelope('a','lease',{'sent_ms':i})))
        for i in range(4): self.assertEqual(q.take().payload['sent_ms'],i)
        self.assertEqual(q.take().payload['sent_ms'],12)
        q.put(Envelope('a','commit',{}));q.put(Envelope('a','lease',{'sent_ms':15}))
        self.assertTrue(q.put(Envelope('a','stop',{})))
        self.assertEqual(q.take(),'stop')
        self.assertFalse(q.put(Envelope('a','lease',{'sent_ms':20})))

    def test_clock_probe_cannot_overtake_unconsumed_request(self):
        from .ledger import Reservation
        from types import SimpleNamespace
        w=Worker(selection(),Reservation('a',99,1,0,100,1),None,queue.Queue(1),clock=lambda:1000050)
        w.pending_message=4
        calls=[]
        w.session=SimpleNamespace(qualify_clock=lambda **kw:calls.append(kw))
        with patch.object(w,'_poll',return_value=SimpleNamespace(last_message=3)):
            w._qualify()
        self.assertEqual(calls,[])
        with patch.object(w,'_poll',return_value=SimpleNamespace(last_message=4)):
            w._qualify()
        self.assertEqual(calls,[{'boot':99,'sequence':1}])

    def test_coordinator_stop_retains_original_source_time(self):
        from .ledger import Reservation
        from types import SimpleNamespace
        w=Worker(selection(),Reservation('a',99,1,0,100,1),None,queue.Queue(1),clock=lambda:1000050)
        w.active=True;calls=[];w.session=SimpleNamespace(stop=lambda **kw:calls.append(kw))
        self.assertTrue(w.submit(Envelope('a','stop',{'boot_nonce':99,'sequence':1,'sent_ms':990})))
        w._stop()
        self.assertEqual(calls[0]['sent_us'],990000)
        self.assertEqual(calls[0]['message'],100)

    def test_worker_owns_submitted_payload_and_latches_queue_failure(self):
        from .ledger import Reservation
        w=Worker(selection(),Reservation('a',99,1,0,100,1),None,queue.Queue(1))
        p={'boot_nonce':99,'sequence':1,'sent_ms':123}
        self.assertTrue(w.submit(Envelope('a','lease',p)))
        p['sent_ms']=999
        self.assertEqual(w.mailbox.take().payload['sent_ms'],123)
        for _ in range(4): self.assertTrue(w.submit(Envelope('a','prepare',p)))
        self.assertFalse(w.submit(Envelope('a','commit',p)))
        self.assertIn('overflow',w.snapshot()[1])

    def test_original_timestamp_uncertain_delivery_stop_and_overflow(self):
        from .ledger import Reservation
        from types import SimpleNamespace
        s=selection(); r=Reservation('a',99,1,0,100,1)
        w=Worker(s,r,None,queue.Queue(1),clock=lambda:1000050)
        calls=[]
        class Session:
            def lease(self,**kw): calls.append(kw)
            def stop(self,**kw): calls.append(kw); raise RuntimeError('uncertain')
        w.session=Session();w.active=True
        w._dispatch(Envelope('a','lease',{'sent_ms':999}))
        self.assertEqual(calls[0]['sent_us'],999000)
        with self.assertRaises(RuntimeError): w._stop()
        self.assertEqual(calls[-1]['message'],100)
        w._stop(); self.assertEqual(len(calls),2) # Never retry STOP.
        w._emit('queued');w._emit('queued')
        self.assertIn('overflow',w.snapshot()[1])
        with self.assertRaises(Exception): w._dispatch(Envelope('a','lease',{'sent_ms':800}))
        self.assertEqual(len(calls),2)


if __name__=='__main__': unittest.main()
