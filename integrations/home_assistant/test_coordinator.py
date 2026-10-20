import unittest
from dataclasses import replace
from coordinator import Device, Phase, begin_group
from freshness import SourceStamp


class GroupTests(unittest.TestCase):
    def setUp(self):
        self.devices = [Device(f"blind-{i}", 100 + i, 12, 3, i * 10, 2000 + i * 30,
                               300, 20 + i, 40, 1000, 5) for i in range(7)]
        self.sequence = 100

    def stamp(self, now):
        self.sequence += 1
        return SourceStamp(now, self.sequence, 0)

    def ack(self, job, device, boot, sequence, kind, now, **kwargs):
        return job.acknowledge(device, boot, sequence, kind, now, stamp=self.stamp(now), **kwargs)

    def report(self, job, device, boot, sequence, now, **kwargs):
        return job.report(device, boot, sequence, now, stamp=self.stamp(now), **kwargs)

    def queue_all(self, job, now=1000):
        for d in self.devices:
            self.assertEqual(job.prepare_queued(d.device_id, d.boot_nonce, 13, now), [])

    def ready(self, job):
        self.queue_all(job)
        out = []
        for d in self.devices:
            out = self.ack(job, d.device_id, d.boot_nonce, 13, "prepared", 1050)
        self.assertEqual(len(out), 7)
        self.assertTrue(all(m.kind == "commit" and m.payload['sent_ms'] == 1050 for m in out))
        for d in self.devices:
            out = self.ack(job, d.device_id, d.boot_nonce, 13, "committed", 1100)
        self.assertEqual(len(out), 7)
        self.assertTrue(all(m.kind == "lease" for m in out))

    def sustain(self, job, now, *, state='armed'):
        for d in self.devices:
            self.assertEqual(self.report(job, d.device_id, d.boot_nonce, 13, now,
                                          height_mm=300, state=state), [])
        return job.tick(now)

    def test_shared_height_and_speed(self):
        job, messages = begin_group(self.devices, 50, 1000)
        self.assertEqual(job.target_height_mm, 1030)
        self.assertEqual({m.payload["target_height_mm"] for m in messages}, {1030})
        self.assertEqual({m.payload["start_ms"] for m in messages}, {4000})
        self.assertEqual({m.payload["sent_ms"] for m in messages}, {1000})
        self.assertEqual({m.payload["speed_mm_s"] for m in messages}, {20})
        self.assertTrue(all(not m.retain for m in messages))
        self.ready(job)
        self.assertEqual(job.phase, Phase.ARMED)

    def test_receipt_and_readiness_are_distinct(self):
        job, _ = begin_group(self.devices, 50, 1000)
        self.assertEqual(self.ack(job, 'blind-0', 100, 13, 'prepared', 1000), [])
        self.assertFalse(job.prepared)  # Direct API requires explicit queue receipt.
        self.assertEqual(job.prepare_queued('blind-0', 100, 13, 1010), [])
        self.assertEqual(job.queued, {'blind-0'})
        self.assertFalse(job.prepared)
        self.assertFalse(job.last_report_ms)  # Receipt cannot create source telemetry.
        self.assertEqual(job.tick(1099), [])
        leases = job.tick(1100)
        self.assertEqual([(m.recipient, m.kind, m.payload['sent_ms']) for m in leases], [('blind-0', 'lease', 1100)])
        self.assertEqual(job.phase, Phase.PREPARING)
        self.assertFalse(job.prepared)

    def test_delayed_ready_peer_gets_leases_without_premature_commit(self):
        job, _ = begin_group(self.devices, 50, 1000)
        self.queue_all(job)
        for d in self.devices[:-1]:
            self.assertEqual(self.ack(job, d.device_id, d.boot_nonce, 13, 'prepared', 1050), [])
        for now in range(1100, 1700, 100):
            for d in self.devices:
                state = 'preparing' if d.device_id == 'blind-6' else 'prepared'
                self.assertEqual(self.report(job, d.device_id, d.boot_nonce, 13, now,
                                             height_mm=300, state=state), [])
            out = job.tick(now)
            self.assertEqual(len(out), 7)
            self.assertEqual({m.kind for m in out}, {'lease'})
            self.assertEqual({m.payload['sent_ms'] for m in out}, {now})
            self.assertEqual(job.phase, Phase.PREPARING)
        commit = self.ack(job, 'blind-6', 106, 13, 'prepared', 1650)
        self.assertEqual(len(commit), 7)
        self.assertEqual({m.kind for m in commit}, {'commit'})
        self.assertEqual(job.phase, Phase.COMMITTING)
        # Waiting for commit acknowledgements also retains explicit lease cadence.
        self.assertEqual(len(self.sustain(job, 1700, state='prepared')), 7)

    def test_missing_ready_stops_all_before_any_commit(self):
        job, _ = begin_group(self.devices, 50, 1000)
        self.queue_all(job)
        for d in self.devices[:-1]:
            self.assertEqual(self.ack(job, d.device_id, d.boot_nonce, 13, 'prepared', 1050), [])
        for now in range(1100, 2700, 100):
            for d in self.devices:
                state = 'preparing' if d.device_id == 'blind-6' else 'prepared'
                self.report(job, d.device_id, d.boot_nonce, 13, now, height_mm=300, state=state)
            self.assertEqual({m.kind for m in job.tick(now)}, {'lease'})
        stops = job.tick(2700)
        self.assertEqual(len(stops), 7)
        self.assertEqual({m.kind for m in stops}, {'stop'})
        self.assertEqual(job.phase, Phase.ABORTED)
        self.assertEqual(job.tick(3000), [])

    def test_unqueued_missing_member_is_not_leased(self):
        job, _ = begin_group(self.devices, 50, 1000)
        job.prepare_queued('blind-0', 100, 13, 1000)
        self.ack(job, 'blind-0', 100, 13, 'prepared', 1050)
        for now in range(1100, 2700, 100):
            self.report(job, 'blind-0', 100, 13, now, height_mm=300, state='prepared')
            self.assertEqual([m.recipient for m in job.tick(now)], ['blind-0'])
        self.assertEqual({m.kind for m in job.tick(2700)}, {'stop'})

    def test_wrong_boot_duplicate_and_stale_ack(self):
        job, _ = begin_group(self.devices, 50, 1000)
        self.queue_all(job)
        self.assertEqual(self.ack(job, 'blind-0', 99, 13, 'prepared', 1050), [])
        self.assertEqual(self.ack(job, 'blind-0', 100, 12, 'prepared', 1050), [])
        self.assertFalse(job.prepared)
        stamp = self.stamp(1050)
        for _ in range(2):
            job.acknowledge('blind-0', 100, 13, 'prepared', 1050, stamp=stamp)
        self.assertEqual(job.prepared, {'blind-0'})
        self.assertEqual(job.last_report_ms['blind-0'], 1050)

    def test_late_or_duplicate_queue_receipt_never_retimes_prepare(self):
        job, _ = begin_group(self.devices, 50, 1000)
        job.prepare_queued('blind-0', 100, 13, 1000)
        self.assertEqual(job.prepare_queued('blind-0', 100, 13, 1090), [])
        self.assertEqual(job.lease_sent_ms['blind-0'], 1000)
        leases = job.prepare_queued('blind-1', 101, 13, 1100)
        self.assertEqual({m.recipient for m in leases}, {'blind-0', 'blind-1'})
        self.assertFalse(job.last_report_ms)
        job, _ = begin_group(self.devices, 50, 1000)
        stops = job.prepare_queued('blind-0', 100, 13, 1250)
        self.assertEqual(len(stops), 7)
        self.assertFalse(job.queued)
        self.assertFalse(job.last_report_ms)
        self.assertEqual(job.phase, Phase.ABORTED)

    def test_queue_rejection_fault_or_expiry_stops_every_peer(self):
        for kind in ('queued', 'prepared', 'fault', 'no_report'):
            with self.subTest(kind=kind):
                job, _ = begin_group(self.devices, 50, 1000)
                self.queue_all(job)
                if kind == 'queued':
                    job, _ = begin_group(self.devices, 50, 1000)
                    job.prepare_queued('blind-0', 100, 13, 1000)
                    out = job.prepare_queued('blind-1', 101, 13, 1050, ok=False)
                elif kind == 'prepared':
                    out = self.ack(job, 'blind-0', 100, 13, 'prepared', 1050, ok=False)
                elif kind == 'fault':
                    out = self.report(job, 'blind-0', 100, 13, 1050, height_mm=300, state='fault', fault='encoder')
                else:
                    job.tick(1100); job.tick(1200)
                    out = job.tick(1251)  # Lease traffic cannot replace source reports.
                self.assertEqual(len(out), 7)
                self.assertEqual({m.kind for m in out}, {'stop'})
                self.assertEqual(job.phase, Phase.ABORTED)

    def test_missed_lease_cadence_does_not_emit_catch_up(self):
        job, _ = begin_group(self.devices, 50, 1000)
        self.queue_all(job)
        for d in self.devices:
            self.report(job, d.device_id, d.boot_nonce, 13, 1200, height_mm=300, state='preparing')
        self.assertEqual({m.kind for m in job.tick(1250)}, {'stop'})
        self.assertEqual(job.tick(1251), [])

    def test_preparing_source_reports_replay_cannot_renew_supervision(self):
        job, _ = begin_group(self.devices, 50, 1000)
        self.queue_all(job)
        for d in self.devices:
            self.report(job, d.device_id, d.boot_nonce, 13, 1050, height_mm=300, state='preparing')
        job.tick(1100); job.tick(1200); job.tick(1300)
        for d in self.devices:
            job.report(d.device_id, d.boot_nonce, 13, 1300,
                stamp=SourceStamp(1000, 9999, 0), height_mm=300, state='preparing')
        self.assertEqual(set(job.last_report_ms.values()), {1050})
        self.assertEqual({m.kind for m in job.tick(1301)}, {'stop'})

    def test_readiness_withdrawal_requires_new_source_ready(self):
        job, _ = begin_group(self.devices, 50, 1000)
        self.queue_all(job)
        for d in self.devices[:-1]:
            self.ack(job, d.device_id, d.boot_nonce, 13, 'prepared', 1050)
        self.report(job, 'blind-0', 100, 13, 1060, height_mm=300, state='preparing')
        self.assertNotIn('blind-0', job.prepared)
        self.assertEqual(self.ack(job, 'blind-6', 106, 13, 'prepared', 1070), [])
        self.assertEqual(job.phase, Phase.PREPARING)
        self.assertEqual({m.kind for m in self.ack(job, 'blind-0', 100, 13, 'prepared', 1080)}, {'commit'})

    def test_commit_ack_missing_stops_after_precommit_leases(self):
        job, _ = begin_group(self.devices, 50, 1000)
        self.queue_all(job)
        for d in self.devices:
            self.ack(job, d.device_id, d.boot_nonce, 13, 'prepared', 1050)
        for d in self.devices[:-1]:
            self.assertEqual(self.ack(job, d.device_id, d.boot_nonce, 13, 'committed', 1070), [])
        for now in range(1100, 3500, 100):
            for d in self.devices:
                state = 'prepared' if d.device_id == 'blind-6' else 'armed'
                self.report(job, d.device_id, d.boot_nonce, 13, now, height_mm=300, state=state)
            self.assertEqual({m.kind for m in job.tick(now)}, {'lease'})
        self.assertEqual(job.phase, Phase.COMMITTING)
        self.assertEqual({m.kind for m in job.tick(3500)}, {'stop'})

    def test_unequal_starts_need_explicit_alignment(self):
        devices = [replace(self.devices[0], height_mm=400), *self.devices[1:]]
        with self.assertRaisesRegex(ValueError, 'needs_alignment'):
            begin_group(devices, 50, 1000)
        job, messages = begin_group(devices, 50, 1000, align=True)
        self.assertEqual({m.payload['target_height_mm'] for m in messages}, {1030})
        self.assertEqual({m.payload['start_height_mm'] for m in messages}, {300, 400})
        self.assertEqual(job.phase, Phase.PREPARING)

    def test_stale_unreferenced_bad_clock_and_nan(self):
        for change in ({'report_ms': -1000}, {'referenced': False}, {'clock_error_ms': 11},
                       {'height_mm': float('nan')}, {'consumed_sequence': 2**64 - 1}):
            with self.subTest(change=change), self.assertRaises(ValueError):
                begin_group([replace(self.devices[0], **change), *self.devices[1:]], 50, 1000)
        for value in (101, float('nan')):
            with self.assertRaises(ValueError):
                begin_group(self.devices, value, 1000)
        for now in (True, -1, 2**63):
            with self.assertRaises(ValueError):
                begin_group(self.devices, 50, now)

    def test_fault_stops_whole_group_and_no_replay(self):
        job, _ = begin_group(self.devices, 50, 1000)
        self.ready(job)
        stops = self.report(job, 'blind-3', 103, 13, 1150, height_mm=300, state='fault', fault='jam')
        self.assertEqual(len(stops), 7)
        self.assertEqual(job.phase, Phase.ABORTED)
        self.assertEqual(job.tick(1200), [])
        self.assertEqual(self.ack(job, 'blind-3', 103, 13, 'committed', 1300), [])

    def test_reboot_and_clock_discontinuity_abort_preparing(self):
        for backwards in (False, True):
            job, _ = begin_group(self.devices, 50, 1000)
            self.queue_all(job)
            out = job.tick(999) if backwards else self.report(job, 'blind-2', 999, 13, 1050, height_mm=300, state='preparing')
            self.assertEqual(len(out), 7)
            self.assertEqual(job.phase, Phase.ABORTED)

    def test_only_complete_with_all_measured_at_target(self):
        job, _ = begin_group(self.devices, 50, 1000)
        self.ready(job)
        for now in range(1200, 60000, 100):
            self.sustain(job, now, state='moving' if now >= 4000 else 'armed')
        for d in self.devices[:-1]:
            self.report(job, d.device_id, d.boot_nonce, 13, 60000, height_mm=1030, state='idle')
        self.assertNotEqual(job.phase, Phase.COMPLETE)
        self.report(job, 'blind-6', 106, 13, 60000, height_mm=1030, state='idle')
        self.assertEqual(job.phase, Phase.COMPLETE)
        self.assertEqual(job.tick(60001), [])

    def test_delayed_source_telemetry_cannot_keep_group_alive(self):
        job, _ = begin_group(self.devices, 50, 1000)
        self.ready(job)
        job.tick(1200); job.tick(1300)
        for d in self.devices:
            job.report(d.device_id, d.boot_nonce, 13, 1300,
                       stamp=SourceStamp(1000, 9999, 0), height_mm=300, state='armed')
        self.assertEqual(job.last_report_ms['blind-0'], 1100)
        self.assertEqual(len(job.tick(1351)), 7)
        self.assertEqual(job.phase, Phase.ABORTED)

    def test_old_ack_does_not_establish_readiness(self):
        job, _ = begin_group(self.devices, 50, 1000)
        self.queue_all(job)
        job.acknowledge('blind-0', 100, 13, 'prepared', 1050, stamp=SourceStamp(700, 2, 0))
        self.assertFalse(job.prepared)

    def test_start_report_can_be_slightly_future_with_bound(self):
        ds = [replace(d, report_ms=1010, clock_error_ms=10) for d in self.devices]
        job, _ = begin_group(ds, 50, 1000)
        self.assertEqual(job.phase, Phase.PREPARING)


if __name__ == '__main__':
    unittest.main()
