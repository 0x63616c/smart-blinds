import unittest
from dataclasses import replace
from coordinator import Device, Phase, begin_group
from freshness import SourceStamp


class GroupTests(unittest.TestCase):
    def setUp(self):
        self.devices = [Device(f"blind-{i}", 100 + i, 12, 3, i * 10, 2000 + i * 30,
                               300, 20 + i, 40, 1000, 5) for i in range(7)]

    def ack(self, job, device, boot, sequence, kind, now, **kwargs):
        return job.acknowledge(device, boot, sequence, kind, now,
                               stamp=SourceStamp(now, now + 1, 0), **kwargs)

    def report(self, job, device, boot, sequence, now, **kwargs):
        return job.report(device, boot, sequence, now,
                          stamp=SourceStamp(now, now + 1, 0), **kwargs)

    def ready(self, job):
        out = []
        for d in self.devices:
            out = self.ack(job, d.device_id, d.boot_nonce, 13, "prepared", 2000)
        self.assertEqual(len(out), 7)
        for d in self.devices:
            out = self.ack(job, d.device_id, d.boot_nonce, 13, "committed", 2500)
        self.assertEqual(len(out), 7)
        self.assertTrue(all(m.kind == "lease" for m in out))

    def test_shared_height_and_speed(self):
        job, messages = begin_group(self.devices, 50, 1000)
        self.assertEqual(job.target_height_mm, 1030)  # intersection [60, 2000]
        self.assertEqual({m.payload["target_height_mm"] for m in messages}, {1030})
        self.assertEqual({m.payload["start_ms"] for m in messages}, {4000})
        self.assertEqual({m.payload["speed_mm_s"] for m in messages}, {20})
        self.assertTrue(all(not m.retain for m in messages))
        self.ready(job)
        self.assertEqual(job.phase, Phase.ARMED)

    def test_missing_member_stops_without_commit(self):
        job, _ = begin_group(self.devices, 50, 1000)
        for d in self.devices[:-1]:
            self.assertEqual(self.ack(job, d.device_id, d.boot_nonce, 13, "prepared", 2000), [])
        stops = job.tick(2700)
        self.assertEqual(len(stops), 7)
        self.assertTrue(all(m.kind == "stop" for m in stops))
        self.assertEqual(job.phase, Phase.ABORTED)
        self.assertEqual(job.tick(3000), [])

    def test_wrong_boot_duplicate_and_stale_ack(self):
        job, _ = begin_group(self.devices, 50, 1000)
        self.assertEqual(self.ack(job, "blind-0", 99, 13, "prepared", 1200), [])
        self.assertEqual(self.ack(job, "blind-0", 100, 12, "prepared", 1200), [])
        self.assertFalse(job.prepared)
        self.ack(job, "blind-0", 100, 13, "prepared", 1200)
        self.ack(job, "blind-0", 100, 13, "prepared", 1200)
        self.assertEqual(len(job.prepared), 1)
        self.ack(job, "blind-1", 101, 13, "prepared", 3000)
        self.assertEqual(job.phase, Phase.ABORTED)

    def test_commit_ack_missing_never_emits_run_lease(self):
        job, _ = begin_group(self.devices, 50, 1000)
        for d in self.devices:
            self.ack(job, d.device_id, d.boot_nonce, 13, "prepared", 2000)
        for d in self.devices[:-1]:
            self.assertEqual(self.ack(job, d.device_id, d.boot_nonce, 13, "committed", 2500), [])
        self.assertEqual(job.phase, Phase.COMMITTING)
        self.assertEqual({m.kind for m in job.tick(3500)}, {"stop"})

    def test_unequal_starts_need_explicit_alignment(self):
        devices = [replace(self.devices[0], height_mm=400), *self.devices[1:]]
        with self.assertRaisesRegex(ValueError, "needs_alignment"):
            begin_group(devices, 50, 1000)
        job, messages = begin_group(devices, 50, 1000, align=True)
        self.assertEqual({m.payload["target_height_mm"] for m in messages}, {1030})
        self.assertEqual({m.payload["start_height_mm"] for m in messages}, {300, 400})
        self.assertEqual(job.phase, Phase.PREPARING)

    def test_stale_unreferenced_bad_clock_and_nan(self):
        for change in ({"report_ms": -1000}, {"referenced": False}, {"clock_error_ms": 11},
                       {"height_mm": float("nan")}, {"consumed_sequence": 2**64 - 1}):
            with self.subTest(change=change), self.assertRaises(ValueError):
                begin_group([replace(self.devices[0], **change), *self.devices[1:]], 50, 1000)
        with self.assertRaises(ValueError):
            begin_group(self.devices, 101, 1000)
        with self.assertRaises(ValueError):
            begin_group(self.devices, float("nan"), 1000)

    def test_fault_stops_whole_group_and_no_replay(self):
        job, _ = begin_group(self.devices, 50, 1000)
        self.ready(job)
        stops = self.report(job, "blind-3", 103, 13, 2550, height_mm=300, state="fault", fault="jam")
        self.assertEqual(len(stops), 7)
        self.assertEqual(job.phase, Phase.ABORTED)
        self.assertEqual(job.tick(2600), [])
        self.assertEqual(self.ack(job, "blind-3", 103, 13, "committed", 2700), [])

    def test_reboot_and_lost_telemetry_abort(self):
        job, _ = begin_group(self.devices, 50, 1000)
        self.ready(job)
        self.assertEqual(len(self.report(job, "blind-2", 999, 13, 2550, height_mm=300, state="idle")), 7)
        job, _ = begin_group(self.devices, 50, 1000)
        self.ready(job)
        self.assertEqual(len(job.tick(2751)), 7)
        self.assertEqual(job.phase, Phase.ABORTED)

    def test_only_complete_with_all_measured_at_target(self):
        job, _ = begin_group(self.devices, 50, 1000)
        self.ready(job)
        for now in range(2600, 60000, 100):
            for d in self.devices:
                self.report(job, d.device_id, d.boot_nonce, 13, now, height_mm=300, state="moving")
            job.tick(now)
        for d in self.devices[:-1]:
            self.report(job, d.device_id, d.boot_nonce, 13, 60000, height_mm=1030, state="idle")
        self.assertNotEqual(job.phase, Phase.COMPLETE)
        self.report(job, "blind-6", 106, 13, 60000, height_mm=1030, state="idle")
        self.assertEqual(job.phase, Phase.COMPLETE)
        self.assertEqual(job.tick(60001), [])

    def test_delayed_source_telemetry_cannot_keep_group_alive(self):
        job, _ = begin_group(self.devices, 50, 1000)
        self.ready(job)
        for d in self.devices:
            job.report(d.device_id, d.boot_nonce, 13, 2700,
                       stamp=SourceStamp(2400, 2701, 0), height_mm=300, state="moving")
        self.assertEqual(job.last_report_ms["blind-0"], 2500)
        self.assertEqual(len(job.tick(2751)), 7)
        self.assertEqual(job.phase, Phase.ABORTED)

    def test_old_ack_does_not_establish_readiness(self):
        job, _ = begin_group(self.devices, 50, 1000)
        job.acknowledge("blind-0", 100, 13, "prepared", 2000,
                        stamp=SourceStamp(1100, 2, 0))
        self.assertFalse(job.prepared)

    def test_start_report_can_be_slightly_future_with_bound(self):
        from dataclasses import replace
        ds = [replace(d, report_ms=1010, clock_error_ms=10) for d in self.devices]
        job, _ = begin_group(ds, 50, 1000)
        self.assertEqual(job.phase, Phase.PREPARING)


if __name__ == "__main__":
    unittest.main()
