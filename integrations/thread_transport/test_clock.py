"""Clock evidence tests: real DTLS plus independent encrypted-path delays."""
import itertools
import time
import unittest

from .client import Session, ProtocolError, Rejected
from .clock import ClockBounds, ClockUncertain
from .test_transport import LIBRARY, Peer, raw, wake_body
from .wire_fixture import WireFixture


def now_us():
    return time.monotonic_ns() // 1000


class ArithmeticTests(unittest.TestCase):
    def test_asymmetric_paths_include_known_offset(self):
        for outward, inward in itertools.product((0, 1000, 10000, 40000), repeat=2):
            bounds = ClockBounds.estimate(1000000, 1100000 + outward,
                                          1100100 + outward, 1000100 + outward + inward)
            self.assertLessEqual(bounds.lower_us, 100000)
            self.assertGreaterEqual(bounds.upper_us, 100000)

    def test_reject_wide_delay_and_grow_uncertainty_with_age(self):
        with self.assertRaises(ClockUncertain):
            ClockBounds.estimate(1000000, 1100000, 1100100, 1040100).error_us(1040100)
        bounds = ClockBounds.estimate(1000000, 1109000, 1109100, 1018100)
        self.assertLess(bounds.error_us(1018100), 10000)
        for stamp in (1018099, 2018100, 2018101):
            with self.assertRaises(ClockUncertain):
                bounds.error_us(stamp)

    def test_invalid_exchange_and_source_timestamps(self):
        for values in ((10,20,30,9), (10,30,20,40), (10,20,40,20), (0,1,2,500001),
                       (True,1,2,3), (0,1,2,1 << 63)):
            with self.assertRaises(ClockUncertain):
                ClockBounds.estimate(*values)
        bound = ClockBounds.estimate(1000000, 1101000, 1101100, 1002100)
        self.assertLess(bound.source_age_us(1102200, 1002300), 100000)
        for source in (900000, 1200000):
            with self.assertRaises(ClockUncertain):
                bound.source_age_us(source, 1002300)

    def test_explicit_motion_model_encloses_default_and_bounds_source_age(self):
        values = (1000000, 1101000, 1101100, 1002100)
        default = ClockBounds.estimate(*values)
        conservative = ClockBounds.estimate(*values, growth_ppm=10000, stamp_guard_us=1000)
        self.assertLessEqual(conservative.lower_us, default.lower_us)
        self.assertGreaterEqual(conservative.upper_us, default.upper_us)
        self.assertGreater(conservative.error_us(1502100), default.error_us(1502100))
        with self.assertRaises(ClockUncertain):
            conservative.error_us(1902100)
        self.assertGreater(conservative.source_age_us(1002200, 1002300, 250000), 100000)
        with self.assertRaises(ClockUncertain):
            conservative.source_age_us(1002200, 1002300)
        for kwargs in ({'growth_ppm': True}, {'growth_ppm': 10001}, {'stamp_guard_us': -1}, {'stamp_guard_us': 1001}):
            with self.assertRaises(ClockUncertain):
                ClockBounds.estimate(*values, **kwargs)


class ClockTransportTests(unittest.TestCase):
    def test_real_assessment_remains_unvalidated_and_motor_disabled(self):
        with Peer() as peer, peer.session() as session:
            status = session.status()
            initial = session.readiness()
            self.assertFalse(initial.clock_assessed)
            self.assertIsNone(initial.source_age_us)
            session.wake(status.boot, 1)
            result = session.qualify_clock(status.boot, 1)
            self.assertTrue(result.clock_assessed)
            self.assertFalse(result.clock_model_validated)
            self.assertFalse(result.clock_qualified)
            self.assertFalse(result.motor_ready)
            self.assertLessEqual(result.host_error_us, 10000)
            self.assertLessEqual(result.source_age_us, 100000)
            self.assertTrue(session.readiness().clock_assessed)
            self.assertEqual(session.handshakes, 1)
            with self.assertRaises(ProtocolError):
                session.qualify_clock(status.boot, 1)

    def test_probes_are_boot_bound_one_use_and_awake_only(self):
        with Peer() as peer, peer.session() as session:
            session.status()
            self.assertEqual(raw(session, 2, wake_body(peer.boot, 1))[0], 128)
            session.wake(peer.boot, 1)
            prefix = wake_body(peer.boot, 1)
            t1 = now_us()
            self.assertEqual(raw(session, 2, prefix)[0], 69)
            t4 = now_us()
            stamps = t1.to_bytes(8, "big") + t4.to_bytes(8, "big")
            self.assertEqual(raw(session, 3, wake_body(peer.boot ^ 1, 1) + stamps)[0], 128)
            self.assertEqual(raw(session, 3, wake_body(peer.boot, 2) + stamps)[0], 128)
            self.assertEqual(raw(session, 3, prefix + stamps)[0], 68)
            self.assertEqual(raw(session, 3, prefix + stamps)[0], 128)
            self.assertEqual(raw(session, 2, prefix)[0], 128)
            self.assertEqual(raw(session, 4, b"unexpected")[0], 128)
            for kind, invalid in ((2,b""), (2,b"x"*17), (3,b""), (3,b"x"*31)):
                self.assertEqual(raw(session, kind, invalid)[0], 128)

    def test_deliberate_asymmetric_delivery_is_rejected(self):
        for forward, reverse in ((0,40), (40,0), (20,20)):
            with self.subTest(forward=forward, reverse=reverse), Peer() as peer, WireFixture(peer.port) as wire, Session(
                    LIBRARY, "::1", wire.port, peer.identity, peer.key) as session:
                session.status()
                session.wake(peer.boot, 1)
                wire.delay(forward_ms=forward, reverse_ms=reverse)
                with self.assertRaises(ClockUncertain):
                    session.qualify_clock(peer.boot, 1)
                self.assertFalse(session.readiness().clock_assessed)

    def test_delayed_source_report_rejected_even_with_authenticated_connection(self):
        with Peer() as peer, WireFixture(peer.port) as wire, Session(
                LIBRARY, "::1", wire.port, peer.identity, peer.key) as session:
            session.status()
            session.wake(peer.boot, 1)
            session.qualify_clock(peer.boot, 1)
            wire.delay(reverse_ms=150)
            with self.assertRaises(ClockUncertain):
                session.readiness()
            self.assertEqual(session.handshakes, 1)

    def test_source_clock_jump_stale_proof_and_reverse_latch(self):
        with Peer() as peer, peer.session() as session:
            session.status()
            session.wake(peer.boot, 1)
            session.qualify_clock(peer.boot, 1)
            peer.shift_clock(1000001)
            self.assertFalse(session.readiness().clock_assessed)
            # A source clock reversal is latched until a new boot; new probes fail.
            peer.shift_clock(-2000000)
            with self.assertRaises(Rejected):
                session.qualify_clock(peer.boot, 2)
        with Peer() as peer, peer.session() as session:
            session.status()
            session.wake(peer.boot, 1)
            t1 = now_us()
            self.assertEqual(raw(session, 2, wake_body(peer.boot, 1))[0], 69)
            t4 = now_us()
            peer.shift_clock(500001)
            self.assertEqual(raw(session, 3, wake_body(peer.boot, 1) + t1.to_bytes(8,"big") + t4.to_bytes(8,"big"))[0],128)

    def test_return_to_sleep_discards_assessment_and_preserves_sequence(self):
        with Peer() as peer, peer.session() as session:
            session.status()
            session.wake(peer.boot, 1)
            session.qualify_clock(peer.boot, 1)
            peer.clock(10000)
            report = session.readiness()
            self.assertFalse(report.awake)
            self.assertFalse(report.clock_assessed)
            self.assertIsNone(report.source_age_us)
            peer.clock(15000)
            session.wake(peer.boot, 2)
            self.assertEqual(raw(session, 2, wake_body(peer.boot,1))[0],128)
            self.assertTrue(session.qualify_clock(peer.boot, 2).clock_assessed)


if __name__ == "__main__":
    unittest.main()
