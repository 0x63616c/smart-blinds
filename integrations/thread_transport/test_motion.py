"""Real DTLS plus shared queue/session/executor, with test-only synthetic I/O."""
import ctypes as C
import json
import secrets
import struct
import time
import unittest
from unittest.mock import patch

from .client import ProtocolError, Rejected, TransportError, _load, _now_us
from .clock import ClockUncertain
from .motion import MotionSession, Queued, encode
from .test_transport import LIBRARY, Peer, free_port, raw
from .wire_fixture import WireFixture


class MotionPeer:
    def __init__(self, *, boot=99, port=None, key=None, geometry=None):
        self.boot, self.port, self.key = boot, port or free_port(), key or secrets.token_bytes(32)
        self.library = _load(LIBRARY)
        for name, args, result in (
            ('new', [C.c_uint16, C.c_char_p, C.POINTER(C.c_uint8), C.c_uint64], C.c_void_p),
            ('new_geometry', [C.c_uint16, C.c_char_p, C.POINTER(C.c_uint8), C.c_uint64, C.c_double, C.c_double, C.c_double], C.c_void_p),
            ('body_bytes', [C.c_void_p], C.c_uint64),
            ('executor_fault', [C.c_void_p], C.c_uint),
            ('timing', [C.c_void_p, C.c_uint], C.c_uint64),
            ('stall_next', [C.c_void_p, C.c_uint], C.c_bool),
            ('io_timing', [C.c_void_p, C.c_uint], C.c_uint64),
            ('io_probe_next', [C.c_void_p, C.c_uint, C.c_uint, C.c_uint], C.c_bool),
            ('free', [C.c_void_p], None), ('mode', [C.c_void_p, C.c_uint], C.c_bool),
            ('requests', [C.c_void_p], C.c_uint), ('off', [C.c_void_p], C.c_bool)):
            fn = getattr(self.library, 'sb_motion_peer_' + name)
            fn.argtypes, fn.restype = args, result
        key_buffer = (C.c_uint8 * 32).from_buffer_copy(self.key)
        try:
            self.handle = (self.library.sb_motion_peer_new_geometry(self.port, b'disposable', key_buffer, boot, *geometry)
                           if geometry else self.library.sb_motion_peer_new(self.port, b'disposable', key_buffer, boot))
        finally:
            C.memset(key_buffer, 0, 32)
        if not self.handle:
            raise RuntimeError('Motion loopback fixture could not bind')

    def session(self, **kwargs):
        return MotionSession(LIBRARY, '::1', kwargs.pop('port', self.port), kwargs.pop('identity', 'disposable'),
            kwargs.pop('key', self.key), expected_boot=kwargs.pop('expected_boot', self.boot),
            calibration_revision=7, message_floor=kwargs.pop('message_floor', 0), **kwargs)

    def mode(self, value):
        if not self.library.sb_motion_peer_mode(self.handle, value):
            raise RuntimeError('Control worker did not acknowledge pause')

    @property
    def off(self):
        return self.library.sb_motion_peer_off(self.handle)

    @property
    def executor_fault(self):
        return self.library.sb_motion_peer_executor_fault(self.handle)

    @property
    def diagnostics(self):
        # First executor-fault timing is diagnostic evidence, never permission.
        result = dict(executor_fault=self.executor_fault, **{
            label:self.library.sb_motion_peer_timing(self.handle,i)
            for i,label in enumerate(('start_gap_us','end_gap_us','cycle_duration_us',
                                      'max_clock_read_gap_us','clock_read_reversed','first_executor_fault'))})
        result.update({label:self.library.sb_motion_peer_io_timing(self.handle,i)
                       for i,label in enumerate(('io_operation','io_before_us','io_entered_us',
                            'io_returned_us','io_after_us','io_wall_us','io_cpu_ns','io_cpu_valid',
                            'io_result','io_ordered','io_injected'))})
        operations=('none','parked','request','charge','coast','wdi','encoder',
                    'counter_start','counter_stop','awake','pwm','heartbeat')
        result['io_name']=operations[result['io_operation']]
        return result

    def io_probe_next(self, operation, kind, us=0):
        operations=('none','parked','request','charge','coast','wdi','encoder',
                    'counter_start','counter_stop','awake','pwm','heartbeat')
        kinds={'during_call':1,'after_return':2,'false_result':3}
        if not self.library.sb_motion_peer_io_probe_next(self.handle,operations.index(operation),kinds[kind],us):
            raise ValueError('Invalid or already pending I/O probe')

    def stall_next(self, us):
        if not self.library.sb_motion_peer_stall_next(self.handle,us):
            raise ValueError('Invalid or already pending test stall')

    @property
    def body_bytes(self):
        return self.library.sb_motion_peer_body_bytes(self.handle)

    @property
    def requests(self):
        return self.library.sb_motion_peer_requests(self.handle)

    def close(self):
        if self.handle:
            self.library.sb_motion_peer_free(self.handle)
            self.handle = None

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()


def connected(session):
    s = session.status()
    if not s.awake:
        session.wake(s.boot, s.last_wake + 1)
    r = session.readiness()
    session.qualify_clock(s.boot, r.last_probe + 1)
    return wait_for(session, lambda s: s.fresh and s.new_sample)


def wait_for(session, predicate, timeout=.2):
    deadline = time.monotonic() + timeout
    last = None
    while time.monotonic() < deadline:
        last = session.motion_status()
        if predicate(last):
            return last
        time.sleep(.005)
    raise AssertionError(f'Worker did not reach expected state: {last}')


def prepare(session, *, message=1, command=1, target=52000, lead=300000):
    now = _now_us()
    return session.prepare(message=message, command=command, sent_us=now, start_us=now+lead,
        origin_um=50000, target_um=target, speed_um_s=20000, accel_um_s2=40000)


class MotionTests(unittest.TestCase):
    def test_prepare_ready_commit_lease_then_stop(self):
        with MotionPeer() as peer, peer.session() as s:
            self.assertEqual(connected(s).phase, 'idle')
            queued = prepare(s)
            self.assertIsInstance(queued, Queued)
            self.assertFalse(hasattr(queued, 'ready'))
            with self.assertRaises(ProtocolError):
                s.commit(message=2, command=1, sent_us=_now_us())  # No worker report yet.
            ready = wait_for(s, lambda r: r.ready)
            self.assertEqual((ready.command, ready.last_message), (1, 1))
            s.commit(message=2, command=1, sent_us=_now_us())
            wait_for(s, lambda r: r.phase == 'committed')
            # Explicit owner cadence, including refreshing before scheduled start.
            message = 3
            started = time.monotonic()
            last_refresh = started
            while time.monotonic() - started < .36:
                s.lease(message=message, command=1, sent_us=_now_us())
                message += 1
                if time.monotonic() - last_refresh > .2:
                    s.qualify_clock(peer.boot, s._last_probe + 1)
                    last_refresh = time.monotonic()
                time.sleep(.06)
            moving = s.motion_status()
            self.assertEqual(moving.phase, 'moving', moving)
            self.assertGreater(moving.height_mm, 50)
            s.stop(message=message, command=1, sent_us=_now_us())
            stopped = wait_for(s, lambda r: r.phase == 'idle' and r.result == 'stopped')
            self.assertTrue(stopped.reference_valid)
            self.assertTrue(peer.off)
            self.assertEqual(s.handshakes, 1)

    def test_explicit_active_deadline_requires_idle_preflight(self):
        with MotionPeer() as peer, peer.session() as s:
            with self.assertRaises(ClockUncertain): s.set_active_deadline(40)
            connected(s)
            for value in (0,101,True):
                with self.assertRaises(ValueError): s.set_active_deadline(value)
            s.set_active_deadline(40)
            self.assertEqual(s._timeout,40)
            prepare(s);wait_for(s,lambda r:r.ready)
            with self.assertRaises(ProtocolError): s.set_active_deadline(50)
            s.stop(message=2,command=1,sent_us=_now_us())

    def test_queue_receipt_is_not_ready_and_delayed_queue_never_arms(self):
        with MotionPeer() as peer, peer.session() as s:
            connected(s)
            peer.mode(1)
            prepare(s)
            report = s.motion_status()
            self.assertFalse(report.ready)
            with self.assertRaises(ProtocolError):
                s.commit(message=2, command=1, sent_us=_now_us())
            time.sleep(.06)
            peer.mode(0)
            report = wait_for(s, lambda r: r.last_message == 1)
            self.assertEqual(report.result, 'invalid')
            self.assertEqual(report.phase, 'idle')
            self.assertTrue(peer.off)

    def test_stop_bypasses_full_queue_and_consumes_replay_floor(self):
        with MotionPeer() as peer, peer.session() as s:
            connected(s)
            peer.mode(1)
            for n in range(1, 5):
                body = encode(1, boot=peer.boot, message=n, command=n, calibration=7, probe=1,
                    sent_us=_now_us(), start_us=_now_us()+300000, origin_um=50000,
                    target_um=52000, speed_um_s=20000, accel_um_s2=40000)
                self.assertEqual(raw(s, 5, body)[0], 68)
            body = encode(2, boot=peer.boot, message=5, command=1, calibration=7, probe=1, sent_us=_now_us())
            self.assertEqual(raw(s, 5, body)[0], 163)
            s.stop(message=6, command=1, sent_us=_now_us())
            self.assertEqual(raw(s, 5, body)[0], 163)
            peer.mode(0)
            report = wait_for(s, lambda r: r.result == 'stopped')
            self.assertEqual(report.phase, 'idle')
            self.assertEqual(report.last_message, 0)  # Does NOT expose ingress STOP high-water.
            self.assertTrue(peer.off)

    def test_malformed_boot_and_source_stale_records(self):
        with MotionPeer() as peer, peer.session() as s:
            connected(s)
            payload = encode(1, boot=peer.boot, message=1, command=1, calibration=7, probe=1,
                sent_us=_now_us(), start_us=_now_us()+300000, origin_um=50000,
                target_um=52000, speed_um_s=20000, accel_um_s2=40000)
            for data in (b'', payload[:-1], b'\x02'+payload[1:], payload[:2]+b'\x01'+payload[3:]):
                self.assertEqual(raw(s, 5, data)[0], 128)
            wrong_boot = payload[:8] + (peer.boot+1).to_bytes(8, 'big') + payload[16:]
            self.assertEqual(raw(s, 5, wrong_boot)[0], 163)
            old = payload[:40] + (_now_us()-200000).to_bytes(8, 'big') + payload[48:]
            self.assertEqual(raw(s, 5, old)[0], 68)
            report = wait_for(s, lambda r: r.last_message == 1)
            self.assertEqual(report.result, 'stale')
            self.assertEqual(report.phase, 'idle')
            self.assertEqual(raw(s, 5, payload)[0], 163)  # Rejected command cannot revive.
            self.assertTrue(peer.off)

    def test_lease_expiry_and_failed_power_disarm(self):
        for fault in ('lease', 'power'):
            with self.subTest(fault=fault), MotionPeer() as peer, peer.session() as s:
                connected(s); prepare(s, lead=500000)
                wait_for(s, lambda r: r.ready)
                if fault == 'power':
                    peer.mode(2)
                else:
                    time.sleep(.3)  # No implicit lease worker exists in this client.
                report = wait_for(s, lambda r: r.phase == 'fault')
                self.assertFalse(report.reference_valid)
                self.assertFalse(report.ready)
                self.assertTrue(peer.off)
                if fault == 'power':
                    self.assertFalse(report.power_ready)
                    self.assertIsNone(report.soc_percent)

    def test_real_control_stall_faults_without_catch_up_or_resume(self):
        with MotionPeer() as peer, peer.session() as s:
            connected(s); prepare(s,lead=500000)
            wait_for(s,lambda r:r.ready)
            peer.stall_next(30000)
            report=wait_for(s,lambda r:r.phase=='fault')
            self.assertEqual(peer.executor_fault,4,peer.diagnostics) # Fault::clock.
            self.assertGreater(peer.diagnostics['end_gap_us'],20000)
            self.assertEqual(report.result,'io') # Session's deliberately broader boundary.
            self.assertFalse(report.reference_valid)
            self.assertTrue(peer.off)
            time.sleep(.04)
            self.assertEqual(s.motion_status().phase,'fault')
            self.assertTrue(peer.off)

    def _io_probe_fault(self, kind, delay):
        with MotionPeer() as peer, peer.session() as s:
            connected(s); prepare(s,lead=500000)
            wait_for(s,lambda r:r.ready)
            peer.io_probe_next('coast',kind,delay)
            s.commit(message=2,command=1,sent_us=_now_us())
            report=wait_for(s,lambda r:r.phase=='fault')
            d=peer.diagnostics
            self.assertEqual(d['first_executor_fault'],5,d)
            self.assertEqual(d['io_name'],'coast',d)
            self.assertEqual(d['io_injected'],{'during_call':1,'after_return':2,'false_result':3}[kind],d)
            self.assertEqual(d['io_ordered'],1,d)
            self.assertEqual(d['io_wall_us'],d['io_after_us']-d['io_before_us'])
            self.assertEqual(d['io_result'],0 if kind=='false_result' else 1,d)
            if kind=='during_call':self.assertGreaterEqual(d['io_returned_us']-d['io_entered_us'],delay,d)
            if kind=='after_return':self.assertGreaterEqual(d['io_after_us']-d['io_returned_us'],delay,d)
            if delay:self.assertGreater(d['io_wall_us'],100,d)
            self.assertEqual(report.result,'io')
            self.assertFalse(report.reference_valid)
            self.assertTrue(peer.off)
            time.sleep(.04)
            self.assertEqual(peer.diagnostics,d) # Successful OFF cleanup never replaces first bad operation.
            self.assertEqual(s.motion_status().phase,'fault')
            self.assertTrue(peer.off)

    def test_slow_io_call_identifies_first_operation_and_stays_off(self):
        self._io_probe_fault('during_call',1000)

    def test_post_return_wait_is_not_misattributed_to_io_implementation(self):
        self._io_probe_fault('after_return',1000)

    def test_false_io_result_identifies_operation_before_cleanup(self):
        self._io_probe_fault('false_result',0)

    def test_reconnect_cannot_resume_or_auto_commit(self):
        with MotionPeer() as peer, peer.session() as first:
            connected(first); prepare(first)
            wait_for(first, lambda r: r.ready)
            floor = first.consumed_message
            first.close()
            with peer.session(message_floor=floor) as next_session:
                report = connected(next_session)
                report = wait_for(next_session, lambda r: r.phase == 'fault')
                self.assertFalse(report.reference_valid)
                self.assertTrue(peer.off)
                with self.assertRaises(ProtocolError):
                    next_session.commit(message=2, command=1, sent_us=_now_us())
                next_session.stop(message=2, command=1, sent_us=_now_us())
                self.assertEqual(next_session.consumed_message, 2)

    def test_qualified_client_does_not_approve_evaluation_peer(self):
        with Peer(boot=99) as peer, MotionSession(LIBRARY, '::1', peer.port, peer.identity, peer.key,
                expected_boot=99, calibration_revision=7, message_floor=0) as s:
            self.assertFalse(s.status().io_qualified)
            s.wake(99, 1)
            with self.assertRaises(ClockUncertain):
                s.qualify_clock(99, 1)
            with self.assertRaises(ClockUncertain):
                prepare(s)

    def test_evaluation_handle_cannot_access_motion_resource(self):
        with Peer() as peer, peer.session() as s:
            s.status()
            count = peer.requests
            with self.assertRaises(TransportError):
                raw(s, 5, b'x' * 80)
            self.assertEqual(peer.requests, count)

    def test_wrong_boot_and_credentials_never_motion(self):
        for args in ({'expected_boot': 100}, {'key': secrets.token_bytes(32)}, {'identity': 'wrong'}):
            with self.subTest(args=tuple(args)), MotionPeer() as peer, peer.session(timeout_ms=250, **args) as s:
                with self.assertRaises((ProtocolError, TransportError)):
                    s.status()
                before = peer.requests
                with self.assertRaises((ProtocolError, TransportError)):
                    s.stop(message=1, command=1, sent_us=_now_us())
                self.assertEqual(peer.requests, before)
                self.assertTrue(peer.off)

    def test_encrypted_motion_replay_never_renews_lease(self):
        with MotionPeer() as peer, WireFixture(peer.port) as wire, peer.session(port=wire.port) as s:
            connected(s); prepare(s)
            wait_for(s, lambda r: r.ready)
            s.lease(message=2, command=1, sent_us=_now_us())
            count = peer.requests
            wire.inject()
            wire.inject(corrupt=True)
            time.sleep(.04)
            self.assertEqual(peer.requests, count)
            time.sleep(.27)
            self.assertEqual(s.motion_status().phase, 'fault')
            self.assertTrue(peer.off)

    def test_source_status_replay_and_age_are_not_receipt_freshness(self):
        with MotionPeer() as peer, peer.session() as s:
            connected(s)
            peer.mode(4)
            r = s.motion_status()
            duplicate = s.motion_status()
            self.assertEqual(duplicate.sampled_us, r.sampled_us)
            self.assertFalse(duplicate.new_sample)
            self.assertFalse(duplicate.ready)
            time.sleep(.11)
            with self.assertRaises(ClockUncertain):
                s.motion_status()
            with self.assertRaises(ProtocolError):
                prepare(s)

    def test_timeout_consumes_message_and_never_reconnects(self):
        with MotionPeer() as peer, WireFixture(peer.port) as wire, peer.session(port=wire.port, timeout_ms=80) as s:
            connected(s)
            wire.delay(reverse_ms=250)
            with self.assertRaises(TransportError):
                prepare(s)
            self.assertEqual(s.consumed_message, 1)
            calls = peer.requests
            with self.assertRaises(TransportError):
                s.status()
            time.sleep(.02)
            self.assertEqual(peer.requests, calls)
            # Even if a response was lost after enqueue, no implicit commit can
            # arrive and the device's independent lease bounds the outcome.
            time.sleep(.3)
            self.assertTrue(peer.off)

    def test_reboot_changes_identity_and_requires_new_explicit_client(self):
        peer = MotionPeer()
        old = peer.session(timeout_ms=200)
        try:
            connected(old)
            port, key = peer.port, peer.key
            peer.close()
            with MotionPeer(boot=100, port=port, key=key) as rebooted:
                with self.assertRaises(TransportError):
                    old.status()
                with rebooted.session(expected_boot=99) as wrong_boot:
                    with self.assertRaises(ProtocolError):
                        wrong_boot.status()
                with rebooted.session() as fresh:
                    self.assertEqual(fresh.status().boot, 100)
                    with self.assertRaises(ClockUncertain):
                        prepare(fresh)  # No wake/qualification/reference adoption.
                self.assertTrue(rebooted.off)
        finally:
            old.close(); peer.close()

    def test_clock_expiry_or_asymmetric_refresh_revokes_commit_but_not_stop(self):
        for delayed in (False, True):
            with self.subTest(delayed=delayed), MotionPeer() as peer, WireFixture(peer.port) as wire, peer.session(port=wire.port) as s:
                connected(s); prepare(s)
                wait_for(s, lambda r: r.ready)
                if delayed:
                    wire.delay(reverse_ms=40)
                    with self.assertRaises(ClockUncertain):
                        s.qualify_clock(peer.boot, 2)
                    wire.delay()
                else:
                    time.sleep(1.01)
                with self.assertRaises(ClockUncertain):
                    s.commit(message=2, command=1, sent_us=_now_us())
                self.assertIsInstance(s.stop(message=2, command=1, sent_us=_now_us()), Queued)
                time.sleep(.02)
                self.assertTrue(peer.off)

    def test_old_source_timestamp_cannot_be_replaced_with_receipt_time(self):
        with MotionPeer() as peer, peer.session() as s:
            connected(s)
            before = peer.requests
            with self.assertRaises(ClockUncertain):
                s.prepare(message=1, command=1, sent_us=_now_us()-150000, start_us=_now_us()+300000,
                    origin_um=50000, target_um=52000, speed_um_s=20000, accel_um_s2=40000)
            self.assertEqual(peer.requests, before)
            self.assertEqual(s.consumed_message, 0)  # Locally invalid, never attempted.

    def test_typed_codec_rejects_bool_overflow_and_trailing_trajectory(self):
        base = dict(boot=99, message=1, command=1, calibration=7, probe=1, sent_us=123,
                    start_us=1000, origin_um=-1, target_um=1001, speed_um_s=20000, accel_um_s2=40000)
        payload = encode(1, **base)
        self.assertEqual(len(payload), 80)
        self.assertEqual(payload[56:64], b'\xff' * 8)
        self.assertEqual(struct.unpack('>I', payload[4:8])[0], 7)
        for key, value in (('boot', True), ('sent_us', 1 << 63), ('origin_um', 1_000_000_001),
                           ('speed_um_s', 30001), ('calibration', 1 << 32), ('target_um', 1.5)):
            with self.subTest(key=key), self.assertRaises(ValueError):
                encode(1, **(base | {key: value}))
        with self.assertRaises(ValueError):
            encode(2, **base)

    def test_ambiguous_status_or_ack_fails_closed(self):
        with MotionPeer() as peer, peer.session() as s:
            connected(s)
            with patch.object(s, '_exchange', return_value=(68, b'{"queued":1}')):
                with self.assertRaises(ProtocolError):
                    prepare(s)
            self.assertEqual(s.consumed_message, 1)
            with self.assertRaises((ProtocolError, TransportError)):
                s.stop(message=2, command=1, sent_us=_now_us())
        with MotionPeer() as peer, peer.session() as s:
            connected(s); prepare(s)
            wait_for(s, lambda r: r.ready)
            data = dict(boot=f'{peer.boot:016x}', last_wake=f'{1:016x}', awake=True,
                        io_qualified=False, clock_qualified=True)
            with patch.object(s, '_exchange', return_value=(69, json.dumps(data).encode())):
                self.assertFalse(s.status().io_qualified)
            with self.assertRaises(ProtocolError):
                s.commit(message=2, command=1, sent_us=_now_us())
        for field, value in (('ready', 1), ('height_mm', True), ('phase', []), ('boot', '0' * 16)):
            with self.subTest(field=field), MotionPeer() as peer, peer.session() as s:
                connected(s)
                _, payload = raw(s, 6)
                data = json.loads(payload); data[field] = value
                with patch.object(s, '_exchange', return_value=(69, json.dumps(data).encode())):
                    with self.assertRaises(ProtocolError):
                        s.motion_status()


if __name__ == '__main__':
    unittest.main()
