import unittest
from freshness import SourceStamp, FreshnessTracker, earliest_sample


class FreshnessTests(unittest.TestCase):
    def test_clock_bound_and_conservative_age(self):
        self.assertEqual(earliest_sample(SourceStamp(1010, 1, 10), 1000, 250), 1000)
        with self.assertRaisesRegex(ValueError, "future"):
            earliest_sample(SourceStamp(1011, 1, 10), 1000, 250)
        with self.assertRaisesRegex(ValueError, "stale"):
            earliest_sample(SourceStamp(760, 1, 10), 1001, 250)

    def test_delayed_packet_is_not_new_on_arrival(self):
        tracker = FreshnessTracker()
        tracker.accept("a", SourceStamp(1000, 1, 0), 1000, 250)
        with self.assertRaisesRegex(ValueError, "stale"):
            tracker.accept("a", SourceStamp(1100, 2, 0), 2000, 250)
        self.assertEqual(tracker.accept("a", SourceStamp(2000, 3, 0), 2000, 250), 2000)

    def test_replay_and_out_of_order_do_not_reset_high_water(self):
        tracker = FreshnessTracker()
        tracker.accept("a", SourceStamp(1000, 4, 0), 1000, 250)
        for stamp in (SourceStamp(1000, 4, 0), SourceStamp(1010, 3, 0), SourceStamp(999, 5, 0)):
            with self.assertRaises(ValueError):
                tracker.accept("a", stamp, 1010, 250)
        self.assertEqual(tracker.accept("a", SourceStamp(1010, 5, 0), 1010, 250), 1010)

    def test_invalid_types_and_clock(self):
        for stamp in (SourceStamp(True, 1, 0), SourceStamp(1, 0, 0),
                      SourceStamp(1, 2**64, 0), SourceStamp(1, 1, 11)):
            with self.assertRaises(ValueError):
                earliest_sample(stamp, 10, 250)


if __name__ == "__main__":
    unittest.main()
