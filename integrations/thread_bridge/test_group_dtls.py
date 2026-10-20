"""Localhost protocol evidence only: real DTLS, synthetic I/O and pack data."""
from contextlib import ExitStack
import dataclasses
import json
from pathlib import Path
import tempfile
import time
import unittest
from integrations.home_assistant.coordinator import Phase
from integrations.thread_transport.test_motion import MotionPeer
from integrations.thread_transport.test_transport import LIBRARY
from integrations.thread_transport.wire_fixture import WireFixture
from .group import Group
from .ledger import Ledger
from .worker import Worker
from .test_bridge import selection


class GroupDTLSTests(unittest.TestCase):
    def fixtures(self,stack,n=7):
        peers=[stack.enter_context(MotionPeer(boot=99+i,geometry=(-5*i,140+10*i,1400+120*i))) for i in range(n)]
        folder=stack.enter_context(tempfile.TemporaryDirectory())
        ledger=stack.enter_context(Ledger(Path(folder)/'ledger.db',create=True))
        selected=[selection(str(i),port=p.port,boot=p.boot,key=p.key,low_um=-5000*i,
                            high_um=140000+10000*i) for i,p in enumerate(peers)]
        for s in selected: ledger.enroll(s,command_floor=0,message_floor=0)
        return peers,ledger,selected

    def finish(self,g,timeout=8):
        deadline=time.monotonic()+timeout
        while time.monotonic()<deadline:
            phase=g.step()
            if phase in (Phase.COMPLETE,Phase.ABORTED): return phase
            time.sleep(.005)
        self.fail('Group did not terminate')

    def test_seven_real_dtls_peers_reach_same_physical_height(self):
        with ExitStack() as stack:
            peers,ledger,selected=self.fixtures(stack)
            g=stack.enter_context(Group(selected,ledger,LIBRARY))
            began=time.monotonic(); job=g.start(50)
            self.assertEqual(job.target_height_mm,70) # Common 0..140, not each peer's own 50%.
            self.assertEqual(self.finish(g),Phase.COMPLETE,job.reason+str([p.diagnostics for p in peers]))
            self.assertEqual(len(job.completed),7)
            self.assertLess(max(job.completed.values())-min(job.completed.values()),1)
            self.assertTrue(all(p.off for p in peers))
            calls=[duration for w in g.workers.values() for _,duration in w.calls]
            elapsed=time.monotonic()-began
            observation={'scope':'localhost synthetic peers only','peers':7,'elapsed_s':round(elapsed,3),
                'application_body_bytes':sum(p.body_bytes for p in peers),'requests':sum(p.requests for p in peers),
                'call_p95_us':sorted(calls)[int(.95*len(calls))],'call_max_us':max(calls),
                'final_spread_mm':max(job.completed.values())-min(job.completed.values())}
            print('LOOPBACK_OBSERVATION '+json.dumps(observation,sort_keys=True))

    def test_next_explicit_job_uses_burned_range_and_current_physical_reference(self):
        with ExitStack() as stack:
            peers,ledger,selected=self.fixtures(stack,2)
            first=stack.enter_context(Group(selected,ledger,LIBRARY));first.start(50)
            self.assertEqual(self.finish(first),Phase.COMPLETE,first.job.reason+str([p.diagnostics for p in peers]))
            first.close()
            second=stack.enter_context(Group(selected,ledger,LIBRARY));second.start(60)
            self.assertTrue(all(r.command==2 and r.floor==4096 for r in second.reservations.values()))
            self.assertEqual(self.finish(second),Phase.COMPLETE,second.job.reason+str([p.diagnostics for p in peers]))
            self.assertEqual(second.job.target_height_mm,84)
            self.assertTrue(all(p.off for p in peers))

    def test_one_failed_power_report_aborts_all_peers(self):
        with ExitStack() as stack:
            peers,ledger,selected=self.fixtures(stack)
            g=stack.enter_context(Group(selected,ledger,LIBRARY));g.start(90)
            until=time.monotonic()+4
            while g.job.phase!=Phase.MOVING and time.monotonic()<until:
                self.assertNotEqual(g.step(),Phase.ABORTED,g.job.reason);time.sleep(.005)
            peers[3].mode(2)
            self.assertEqual(self.finish(g),Phase.ABORTED)
            g.close()
            self.assertTrue(all(p.off for p in peers))
            self.assertTrue(all(not w.active or w.reservation.stopped for w in g.workers.values()))
            self.assertFalse(g.job.completed)

    def test_paused_worker_cannot_turn_queue_receipt_into_readiness(self):
        with ExitStack() as stack:
            peers,ledger,selected=self.fixtures(stack,2)
            class Paused(Worker):
                def _call(self,name,**kw):
                    if name=='prepare' and self.selected.device_id=='1': peers[1].mode(1)
                    return super()._call(name,**kw)
            g=stack.enter_context(Group(selected,ledger,LIBRARY,worker_factory=Paused));g.start(90)
            self.assertEqual(self.finish(g),Phase.ABORTED)
            self.assertFalse(g.job.committed)
            peers[1].mode(0);g.close()
            self.assertTrue(all(p.off for p in peers))

    def test_worker_loss_aborts_peers_and_never_resumes(self):
        with ExitStack() as stack:
            peers,ledger,selected=self.fixtures(stack,2)
            g=stack.enter_context(Group(selected,ledger,LIBRARY));g.start(90)
            until=time.monotonic()+1
            while g.job.phase!=Phase.ARMED and time.monotonic()<until:
                self.assertNotEqual(g.step(),Phase.ABORTED,g.job.reason);time.sleep(.005)
            g.workers['1'].shutdown.set()
            self.assertEqual(self.finish(g),Phase.ABORTED)
            g.close()
            self.assertTrue(all(p.off for p in peers))
            self.assertTrue(all(w.reservation.stopped for w in g.workers.values()))
            with self.assertRaises(RuntimeError): g.start(50)

    def test_wrong_credentials_no_prepare_and_reservation_stays_burned(self):
        with ExitStack() as stack:
            peers,ledger,selected=self.fixtures(stack,2)
            selected[1]=dataclasses.replace(selected[1],key=b'X'*32)
            g=stack.enter_context(Group(selected,ledger,LIBRARY))
            with self.assertRaises(RuntimeError): g.start(50)
            self.assertTrue(all(not w.active for w in g.workers.values()))
            self.assertTrue(all(p.off for p in peers))
            r=ledger.reserve(selected)
            self.assertTrue(all(v.floor==4096 and v.command==2 for v in r.values()))

    def test_uncertain_commit_delivery_aborts_without_reconnect(self):
        with ExitStack() as stack:
            peers,ledger,selected=self.fixtures(stack,2)
            wire=stack.enter_context(WireFixture(peers[1].port))
            selected[1]=dataclasses.replace(selected[1],port=wire.port)
            attempted=[]
            class LostCommit(Worker):
                def _call(self,name,**kw):
                    if name=='commit' and self.selected.device_id=='1':
                        attempted.append(kw['message']);wire.delay(reverse_ms=150)
                    return super()._call(name,**kw)
            g=stack.enter_context(Group(selected,ledger,LIBRARY,worker_factory=LostCommit));g.start(90)
            self.assertEqual(self.finish(g),Phase.ABORTED)
            self.assertEqual(len(attempted),1)
            g.close();wire.delay();time.sleep(.35)
            self.assertTrue(all(p.off for p in peers))
            self.assertTrue(all(not w.active or w.reservation.stopped for w in g.workers.values()))


if __name__=='__main__': unittest.main()
