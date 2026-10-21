"""Cached API and publication ordering; no network, actuator or timing model.

These tests use the existing Group clock injection to place a publication at a
specific copy boundary. They do not replace an executor's clock or run firmware.
"""
from dataclasses import replace
import queue
import threading
from types import SimpleNamespace as NS
import unittest
from unittest.mock import patch

from integrations.home_assistant.coordinator import Phase
from integrations.physical_bridge.service import Pairing, Reader
from integrations.thread_bridge.group import Group
from integrations.thread_bridge.ledger import Reservation
from integrations.thread_bridge.selection import Selection
from integrations.thread_transport.motion import Report
from .handoff import Handoff
from .service import PhysicalControl


def report(*, phase='moving', reference=True, height=51, sample=19000, **changes):
    value=Report(99,sample,sample,0,1000,phase,'accepted',1,2,True,True,False,
                 reference,True,height,True,sample,1000,65,True)
    return replace(value,**changes)


def selection(name='blind'):
    return Selection(name,'::1',5684,'fixture',b'k'*32,99,7,0,100000,30000,60000,'fixture-only',True)


class CachedActor:
    def __init__(self):
        self.pairing=Pairing('blind','Fixture','::1',5684,'fixture',b'k'*32,99)
        self.lock=threading.Lock();self.failed=False;self.halt=threading.Event();self.observation=None
        self.last_position=NS(reference_valid=True,height_mm=50,sampled_us=9000,earliest_host_us=9000)
        self.last_report=None

    def state(self):
        value=Reader.state(self);value['available']=True
        return value


def service(current=None):
    actor=CachedActor();s=PhysicalControl.__new__(PhysicalControl)
    s.lock=threading.Lock();s.bridge_id='fixture';s.phase='moving';s.reason='';s.last_intent=1
    s.pairings={'blind':actor.pairing};s.actors={'blind':actor};s.configured={'blind':selection()}
    s.active=None if current is None else NS(workers={'blind':NS(snapshot=lambda:(current,None,True,2,False))},
                                            job=NS(target_height_mm=70))
    return s,actor


class PresentationTests(unittest.TestCase):
    def state(self,s,now=20000):
        with patch('integrations.physical_control.service.now_us',return_value=now):return s.state()

    def test_current_reference_loss_cannot_fall_back_to_last_off(self):
        for phase in ('fault','unreferenced','moving'):
            with self.subTest(phase=phase):
                s,_=service(report(phase=phase,reference=False,height=None))
                value=self.state(s);d=value['devices'][0]
                self.assertFalse(d['referenced']);self.assertIsNone(d['position'])
                self.assertIsNone(d['height_mm']);self.assertIsNone(d['position_sample_us'])
                self.assertIsNone(value['group']['position']);self.assertFalse(value['group']['aligned'])

    def test_absent_moving_coordinate_never_compares_none(self):
        s,_=service(report(reference=True,height=None))
        d=self.state(s)['devices'][0]
        self.assertEqual(d['state'],'stopped');self.assertFalse(d['referenced'])

    def test_reference_loss_survives_facade_removal(self):
        for sample in (9000,19000):
            with self.subTest(sample=sample):
                s,actor=service();actor.last_report=report(reference=False,height=None,sample=sample)
                self.assertFalse(self.state(s)['devices'][0]['referenced'])
                self.assertEqual(actor.last_position.sampled_us,9000)  # Read-only presentation.

    def test_new_actual_off_supersedes_older_reference_loss(self):
        s,actor=service();actor.last_report=report(reference=False,height=None,sample=8000)
        d=self.state(s)['devices'][0]
        self.assertTrue(d['referenced']);self.assertEqual(d['position_sample_us'],'0000000000002328')
        self.assertEqual(d['position_age_ms'],11)

    def test_retained_age_limit_failure_and_current_source_remain_exact(self):
        s,actor=service()
        self.assertTrue(self.state(s,9000+1800000000)['devices'][0]['referenced'])
        self.assertFalse(self.state(s,9000+1800000001)['devices'][0]['referenced'])
        actor.failed=True;self.assertFalse(self.state(s)['devices'][0]['referenced'])
        s,_=service(report());d=self.state(s)['devices'][0]
        self.assertEqual((d['height_mm'],d['position_sample_us'],d['position_age_ms'],d['state']),
                         (51,'0000000000004a38',1,'opening'))

    def test_room_rejected_before_coordinator_actor_or_ledger(self):
        p=Pairing('room','Fixture','::1',5684,'fixture',b'k'*32,99)
        for selections in ([],[selection('room')]):
            with self.subTest(selected=bool(selections)), \
                 patch('integrations.physical_control.service.threading.Thread') as thread, \
                 patch('integrations.physical_control.service.Actor') as actor, \
                 patch('integrations.physical_control.service.Ledger') as ledger:
                thread.side_effect=AssertionError('Identity validation opened coordinator')
                with self.assertRaisesRegex(ValueError,'reserved'):
                    PhysicalControl('fixture',[p],selections,None,None)
                thread.assert_not_called();actor.assert_not_called();ledger.assert_not_called()


class Job:
    def __init__(self):
        self.phase=Phase.MOVING;self.completed={};self.queued={'blind'};self.reason=''
        self.reports=[];self.receipts=[];self.ticks=[]
    def abort(self,reason):self.reason=reason;self.phase=Phase.ABORTED;return []
    def tick(self,now):self.ticks.append(now);return []
    def prepare_queued(self,*args):self.receipts.append(args);return []
    def report(self,*args,**kwargs):self.reports.append((args,kwargs));return []


class Worker:
    thread=None;active=False
    def __init__(self,value,on_snapshot=lambda:None,completion=None,on_completion=lambda:None):
        self.value=value;self.on_snapshot=on_snapshot;self.terminal=completion;self.on_completion=on_completion
        self.selected=selection();self.sent=[];self.failure=None
    def snapshot(self):
        self.on_snapshot();return self.value,self.failure,True,2,False
    def completion(self):self.on_completion();return self.terminal
    def submit(self,envelope):self.sent.append(envelope);return True
    def start(self):pass
    def close(self):pass


def group(worker,now):
    g=Group.__new__(Group);g.clock=lambda:now[0];g.closed=False;g.started=False;g.job=Job()
    g.workers={'blind':worker};g.events=queue.Queue(maxsize=32)
    g.reservations={'blind':Reservation('blind',99,1,0,4096,1)};g.last_sample={}
    return g


def handoff(**changes):
    return replace(Handoff(99,1,19000,19000,1,2,'idle','finished',True,51,True,
                           20000,19000,19000),**changes)


class PublicationTests(unittest.TestCase):
    def test_preflight_uses_time_after_all_owner_copies(self):
        now=[10000];copies=[]
        def publish():copies.append(1);now[0]=20000
        w=Worker(report(phase='idle'),publish);g=group(w,now);g.job=None
        # A second iteration would mask the original ordering defect. It must
        # accept the first complete copy and must not sleep to obtain a pass.
        with patch('integrations.thread_bridge.group.time.sleep',side_effect=AssertionError('unexpected retry')):
            job=g.start(70)
        self.assertEqual(copies,[1]);self.assertEqual(job.last_now_ms,20)
        self.assertEqual(job.members['blind'].report_ms,19)

    def test_copy_cannot_cross_preflight_deadline_and_still_start(self):
        now=[10000]
        w=Worker(report(phase='idle',sample=9000),lambda:now.__setitem__(0,16000));g=group(w,now);g.job=None
        with self.assertRaisesRegex(RuntimeError,'preflight deadline'):g.start(70,timeout_s=.005)
        self.assertIsNone(g.job);self.assertFalse(w.sent);self.assertTrue(g.closed)

    def test_report_publication_after_entry_clock_is_valid(self):
        now=[10000];g=group(Worker(report(),lambda:now.__setitem__(0,20000)),now)
        self.assertEqual(g.step(),Phase.MOVING)
        args,kw=g.job.reports[0]
        self.assertEqual(args[-1],20);self.assertEqual((kw['stamp'].sample_ms,kw['stamp'].sequence),(19,19000))

    def test_terminal_publication_after_report_copy_uses_same_post_copy_time(self):
        now=[10000]
        w=Worker(None,completion=handoff(),on_completion=lambda:now.__setitem__(0,20000));g=group(w,now)
        self.assertEqual(g.step(),Phase.MOVING)
        args,kw=g.job.reports[0]
        self.assertEqual(args[-1],20);self.assertEqual((kw['state'],kw['stamp'].sequence),('idle',19000))

    def test_receipt_batch_is_copied_before_validation_time_and_bounded(self):
        now=[10000];g=group(Worker(None),now)
        class RefillingQueue:
            maxsize=32
            def __init__(self):self.reads=0
            def get_nowait(self):
                self.reads+=1;now[0]=20000
                return NS(kind='queued',device_id='blind')
        events=g.events=RefillingQueue();g.step()
        self.assertEqual(events.reads,32);self.assertEqual(len(g.job.receipts),32)
        self.assertEqual({event[-1] for event in g.job.receipts},{20})

    def test_copied_failure_wins_over_queued_receipt_or_completion(self):
        now=[20000];w=Worker(None,completion=handoff());w.failure='STOP/owner failed'
        g=group(w,now);g.events.put(NS(kind='queued',device_id='blind'))
        self.assertEqual(g.step(),Phase.ABORTED)
        self.assertEqual(g.job.reason,'blind: STOP/owner failed')
        self.assertFalse(g.job.receipts);self.assertFalse(g.job.reports);self.assertFalse(g.job.ticks)

    def test_future_and_old_reports_still_reject_at_original_bounds(self):
        for phase,ready,now,sample,expected in (
            ('moving',False,20000,21000,Phase.ABORTED),
            ('moving',False,120000,19000,Phase.ABORTED),
            ('moving',False,119000,19000,Phase.MOVING),
            ('ready',True,50000,19000,Phase.ABORTED),
            ('ready',True,49000,19000,Phase.MOVING)):
            with self.subTest(phase=phase,now=now,sample=sample):
                g=group(Worker(report(phase=phase,ready=ready,sample=sample)),[now])
                self.assertEqual(g.step(),expected)
                if expected==Phase.ABORTED:self.assertFalse(g.job.reports)

    def test_terminal_rejects_future_receipt_age_boot_and_missing_off(self):
        for changes,now in (({},49001),({'receipt_us':20001},20000),({'boot':100},20000),
                            ({'settled_off':False},20000),({'command':2},20000)):
            with self.subTest(changes=changes,now=now):
                g=group(Worker(None,completion=handoff(**changes)),[now])
                self.assertEqual(g.step(),Phase.ABORTED);self.assertFalse(g.job.reports)
        g=group(Worker(None,completion=handoff()),[49000])
        self.assertEqual(g.step(),Phase.MOVING);self.assertEqual(g.job.reports[0][0][-1],49)

    def test_repeated_source_and_wrong_command_do_not_refresh_report(self):
        for value,last in ((report(),19000),(report(command=2),0)):
            with self.subTest(command=value.command,last=last):
                g=group(Worker(value),[20000]);g.last_sample={'blind':last};g.step()
                self.assertFalse(g.job.reports)


if __name__=='__main__':unittest.main()
