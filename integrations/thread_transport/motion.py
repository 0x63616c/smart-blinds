"""Explicit motion transport; no qualification, reconnect, lease or commit loop.

Use only with a separately commissioned device. This client cannot create a
physical reference or a qualification record. ``queued`` acknowledges owned
storage only; the source-stamped worker report is the readiness authority.
"""
from __future__ import annotations
from dataclasses import dataclass
import math
import struct
from .client import (Session, Status, Readiness, ProtocolError, Rejected, TransportError,
                     _now_us, _json, _hex64, _uint64)
from .clock import ClockBounds, ClockUncertain, MAX_ERROR_US

PHASES = frozenset('unreferenced idle preparing ready committed moving settling fault'.split())
RESULTS = frozenset('none accepted stale invalid busy unqualified reference power clock connection deadline control io stopped finished'.split())
MAX_TIME = (1 << 63) - 1


def _integer(value, low, high, name):
    if type(value) is not int or not low <= value <= high:
        raise ValueError(f'Invalid {name}')
    return value


def encode(kind: int, *, boot: int, message: int, command: int, sent_us: int,
           calibration: int = 0, probe: int = 0, start_us: int = 0, origin_um: int = 0,
           target_um: int = 0, speed_um_s: int = 0, accel_um_s2: int = 0) -> bytes:
    """Canonical v1 80-byte record. Units are exact integers; never clamp/round."""
    _integer(kind, 1, 4, 'kind')
    for name, value in (('boot', boot), ('message', message), ('command', command)):
        _integer(value, 1, (1 << 64) - 1, name)
    _integer(sent_us, 1, MAX_TIME, 'source timestamp')
    _integer(calibration, 0 if kind == 4 else 1, (1 << 32) - 1, 'calibration')
    _integer(probe, 0 if kind == 4 else 1, (1 << 64) - 1, 'probe')
    if kind == 1:
        _integer(start_us, 1, MAX_TIME, 'start timestamp')
        _integer(origin_um, -1_000_000_000, 1_000_000_000, 'origin')
        _integer(target_um, -1_000_000_000, 1_000_000_000, 'target')
        _integer(speed_um_s, 1, 30000, 'speed')
        _integer(accel_um_s2, 1, 60000, 'acceleration')
    elif any(type(x) is not int or x != 0 for x in (start_us, origin_um, target_um, speed_um_s, accel_um_s2)):
        raise ValueError('Non-prepare trajectory fields must be zero')
    return struct.pack('>BBHIQQQQQQqqII', 1, kind, 0, calibration, boot, message, command,
                       probe, sent_us, start_us, origin_um, target_um, speed_um_s, accel_um_s2)


@dataclass(frozen=True)
class MotionStatus(Status):
    io_qualified: bool
    clock_qualified: bool


@dataclass(frozen=True)
class Queued:
    """Receipt acknowledgement, deliberately without a ready/accepted property."""
    message: int
    command: int
    kind: int


@dataclass(frozen=True)
class Report:
    boot: int
    sampled_us: int
    sample_host_earliest_us: int
    clock_error_us: int
    source_age_us: int
    phase: str
    result: str
    command: int
    last_message: int
    io_qualified: bool
    fresh: bool
    ready: bool
    reference_valid: bool
    awake_required: bool
    height_mm: float | None
    power_ready: bool
    power_sampled_us: int
    power_age_us: int | None
    soc_percent: float | None
    new_sample: bool


class MotionSession(Session):
    """Per-boot explicit motion-capable DTLS handle, separate from evaluation.

    ``message_floor`` is the caller's durably consumed floor for this boot. The
    device's last_message excludes STOP/discarded records, so it cannot replace
    that ledger. Persist consumed_message even after an uncertain response.
    Construction sends no command, and never installs qualification records.
    """
    _native_constructor = 'sb_motion_client_new'

    def __init__(self, *args, expected_boot: int, calibration_revision: int,
                 message_floor: int, **kwargs):
        self.expected_boot = _integer(expected_boot, 1, (1 << 64) - 1, 'expected boot')
        self.calibration = _integer(calibration_revision, 1, (1 << 32) - 1, 'calibration')
        self._message = _integer(message_floor, 0, (1 << 64) - 1, 'message floor')
        self._report = None
        self._sample = 0
        self._sample_payload = None
        self._command = 0
        self._prepare_message = 0
        self._qualified_clock = False
        super().__init__(*args, **kwargs)

    @property
    def consumed_message(self):
        return self._message

    def _fail(self):
        self._failed = True
        self._boot = self._clock = self._report = None
        self._qualified_clock = False

    def status(self) -> MotionStatus:
        with self._lock:
            code, payload = self._exchange(0)
            if code != 69:
                raise Rejected(code)
            try:
                v = _json(payload)
                if (set(v) != {'boot', 'last_wake', 'awake', 'io_qualified', 'clock_qualified'} or
                    any(type(v[k]) is not bool for k in ('awake', 'io_qualified', 'clock_qualified'))):
                    raise ProtocolError('Unsupported motion status contract')
                boot = _hex64(v['boot'], nonzero=True)
                if boot != self.expected_boot:
                    raise ProtocolError('Boot changed; explicit recovery is required')
                wake = _hex64(v['last_wake'])
                self._boot, self._last_sequence = boot, max(self._last_sequence, wake)
                if not v['io_qualified']:
                    self._report = None
                if not v['awake'] or not v['clock_qualified']:
                    self._clock = self._report = None
                    self._qualified_clock = False
                return MotionStatus(boot, wake, v['awake'], v['io_qualified'], v['clock_qualified'])
            except ProtocolError:
                self._fail()
                raise

    def wake(self, boot: int, sequence: int) -> int:
        with self._lock:
            if not _uint64(boot, nonzero=True) or not _uint64(sequence, nonzero=True):
                raise ValueError('Invalid boot/wake sequence')
            if boot != self._boot or sequence <= self._last_sequence:
                raise ProtocolError('Fresh status and a new wake sequence are required')
            self._last_sequence = sequence
            code, payload = self._exchange(1, struct.pack('>QQ', boot, sequence))
            if code != 68:
                raise Rejected(code)
            try:
                v = _json(payload)
                if (set(v) != {'awake_ms', 'io_qualified'} or type(v['awake_ms']) is not int or
                    v['awake_ms'] != 10000 or type(v['io_qualified']) is not bool):
                    raise ProtocolError('Unsupported wake response')
                return v['awake_ms']
            except ProtocolError:
                self._fail()
                raise

    def _readiness(self, payload: bytes) -> Readiness:
        v = _json(payload)
        if (set(v) != {'boot', 'last_probe', 'sampled_us', 'awake', 'clock_assessed',
                      'clock_model_validated', 'clock_qualified', 'clock_error_us', 'motor_ready', 'reason'} or
            any(type(v[k]) is not bool for k in ('awake', 'clock_assessed', 'clock_model_validated', 'clock_qualified')) or
            v['motor_ready'] is not False or v['reason'] != 'hardware_unconfigured'):
            raise ProtocolError('Unsupported clock diagnostics')
        boot, probe, sample = _hex64(v['boot'], nonzero=True), _hex64(v['last_probe']), _hex64(v['sampled_us'])
        error = v['clock_error_us']
        if (boot != self._boot or sample > MAX_TIME or
            (v['clock_assessed'] and (not v['awake'] or type(error) is not int or not 0 <= error <= MAX_ERROR_US)) or
            (not v['clock_assessed'] and error is not None) or
            (v['clock_qualified'] and not (v['clock_assessed'] and v['clock_model_validated']))):
            raise ProtocolError('Inconsistent clock diagnostics')
        self._last_probe = max(self._last_probe, probe)
        self._qualified_clock = v['clock_qualified'] and probe == self._clock_probe
        host_error = source_age = None
        if not self._qualified_clock:
            self._clock = self._report = None
        if self._clock:
            now = _now_us()
            host_error = self._clock.error_us(now)
            source_age = self._clock.source_age_us(sample, now)
        return Readiness(boot, probe, v['awake'], v['clock_assessed'], error, host_error, source_age,
                         v['clock_model_validated'], v['clock_qualified'], False)

    def qualify_clock(self, boot: int, sequence: int) -> Readiness:
        """Explicit exchange only. Uses the worst permitted C6 clock-model bounds.

        A true clock_model_validated value is a device assertion, never created
        by this host. It still does not imply physical reference or motor ready.
        """
        with self._lock:
            if not _uint64(boot, nonzero=True) or not _uint64(sequence, nonzero=True):
                raise ValueError('Invalid boot/probe')
            if boot != self._boot or sequence <= self._last_probe:
                raise ProtocolError('Fresh status and a new clock probe are required')
            self._last_probe = sequence
            self._clock = self._report = None
            self._qualified_clock = False
            prefix = struct.pack('>QQ', boot, sequence)
            try:
                t1 = _now_us()
                code, payload = self._exchange(2, prefix)
                t4 = _now_us()
                if code != 69:
                    raise Rejected(code)
                v = _json(payload)
                if (set(v) != {'boot', 'probe', 'received_us', 'sent_us'} or
                    _hex64(v['boot'], nonzero=True) != boot or _hex64(v['probe']) != sequence):
                    raise ProtocolError('Clock response does not match boot/probe')
                clock = ClockBounds.estimate(t1, _hex64(v['received_us']), _hex64(v['sent_us']), t4,
                                             growth_ppm=10000, stamp_guard_us=1000)
                clock.error_us(_now_us())
                code, payload = self._exchange(3, prefix + struct.pack('>QQ', t1, t4))
                if code != 68:
                    raise Rejected(code)
                self._clock, self._clock_probe = clock, sequence
                result = self._readiness(payload)
                if not result.clock_qualified or result.last_probe != sequence or result.source_age_us is None:
                    raise ClockUncertain('Device did not retain qualified clock evidence')
                return result
            except ProtocolError:
                self._fail()
                raise
            except (ClockUncertain, TransportError):
                self._clock = None
                self._qualified_clock = False
                raise

    def _bounds(self):
        if self._boot != self.expected_boot or not self._clock or not self._qualified_clock:
            raise ClockUncertain('Explicit clock qualification is required')
        self._clock.error_us(_now_us())
        return self._clock

    def motion_status(self) -> Report:
        """Fresh authenticated source time, never receipt-time freshness.

        Repeated snapshots are diagnostic (new_sample/ready false); decreasing
        sample times or conflicting data for the same sample fail the session.
        A fresh fault report remains readable; missing power is not synthesized.
        """
        with self._lock:
            clock = self._bounds()
            code, payload = self._exchange(6)
            if code != 69:
                raise Rejected(code)
            try:
                v = _json(payload)
                fields = {'boot', 'sampled_us', 'phase', 'result', 'command', 'last_message', 'io_qualified',
                          'fresh', 'ready', 'reference_valid', 'awake_required', 'height_mm', 'power_ready',
                          'power_sampled_us', 'soc_percent'}
                bools = ('io_qualified', 'fresh', 'ready', 'reference_valid', 'awake_required', 'power_ready')
                if set(v) != fields or any(type(v[k]) is not bool for k in bools):
                    raise ProtocolError('Unsupported worker status')
                if (type(v['phase']) is not str or v['phase'] not in PHASES or
                    type(v['result']) is not str or v['result'] not in RESULTS):
                    raise ProtocolError('Unknown worker state')
                boot, sample = _hex64(v['boot'], nonzero=True), _hex64(v['sampled_us'], nonzero=True)
                power_sample = _hex64(v['power_sampled_us'])
                command, message = _hex64(v['command']), _hex64(v['last_message'])
                if boot != self.expected_boot or sample > MAX_TIME or power_sample > MAX_TIME:
                    raise ProtocolError('Wrong boot or invalid source time')
                for name, low, high in (('height_mm', -1000000, 1000000), ('soc_percent', 0, 100)):
                    val = v[name]
                    if val is not None and (type(val) not in (int, float) or not math.isfinite(val) or not low <= val <= high):
                        raise ProtocolError('Invalid measured value')
                if ((v['reference_valid'] and v['height_mm'] is None) or
                    (not v['power_ready'] and v['soc_percent'] is not None) or
                    (v['ready'] and not (v['phase'] == 'ready' and v['fresh'] and v['io_qualified'] and
                                         v['reference_valid'] and v['power_ready'] and v['awake_required']))):
                    raise ProtocolError('Inconsistent readiness')
                now = _now_us()
                age = clock.source_age_us(sample, now)
                power_age = clock.source_age_us(power_sample, now, 250000) if v['power_ready'] else None
                if sample < self._sample:
                    raise ProtocolError('Worker source time regressed')
                # Network readiness and power age may change between readings of
                # one worker snapshot. Only worker-owned fields must be stable.
                stable = tuple(v[k] for k in ('phase', 'result', 'command', 'last_message', 'reference_valid',
                                              'awake_required', 'height_mm'))
                new = sample > self._sample
                if not new and stable != self._sample_payload:
                    raise ProtocolError('Conflicting worker snapshot')
                self._sample, self._sample_payload = sample, stable
                report = Report(boot, sample, now-age, clock.error_us(now), age, v['phase'], v['result'],
                    command, message, v['io_qualified'], v['fresh'] and age <= 30000,
                    v['ready'] and age <= 30000 and new, v['reference_valid'], v['awake_required'],
                    v['height_mm'], v['power_ready'], power_sample, power_age, v['soc_percent'], new)
                self._report = report
                return report
            except ProtocolError:
                self._fail()
                raise
            except ClockUncertain:
                self._report = None
                raise

    def _send(self, kind, *, message, command, sent_us, **trajectory) -> Queued:
        if self._boot != self.expected_boot:
            raise ProtocolError('Fresh status is required')
        _integer(message, 1, (1 << 64) - 1, 'message')
        if message <= self._message:
            raise ProtocolError('Message was already consumed; never replay it')
        body = encode(kind, boot=self.expected_boot, message=message, command=command, sent_us=sent_us,
                      calibration=self.calibration if kind != 4 else 0,
                      probe=self._clock_probe if kind != 4 else 0, **trajectory)
        if kind != 4:
            self._bounds()
            now = _now_us()
            if not 0 <= now-sent_us <= 100000:
                raise ClockUncertain('Command source time is future or stale')
        self._message = message  # Even a timeout/rejection consumes this attempt.
        code, payload = self._exchange(5, body)
        self._report = None
        if code != 68:
            raise Rejected(code)
        try:
            value = _json(payload)
            if set(value) != {'queued'} or value['queued'] is not True:
                raise ProtocolError('Unsupported queue acknowledgement')
        except ProtocolError:
            self._fail()
            raise
        return Queued(message, command, kind)

    def _fresh_report(self):
        clock = self._bounds()
        r = self._report
        if not r or not r.new_sample or not r.fresh or not r.io_qualified or not r.power_ready or not r.reference_valid:
            raise ProtocolError('Fresh qualified worker and power evidence are required')
        clock.source_age_us(r.sampled_us, _now_us(), 30000)
        clock.source_age_us(r.power_sampled_us, _now_us(), 250000)
        return r

    def prepare(self, *, message: int, command: int, sent_us: int, start_us: int,
                origin_um: int, target_um: int, speed_um_s: int, accel_um_s2: int) -> Queued:
        with self._lock:
            report = self._fresh_report()
            if report.phase != 'idle':
                raise ProtocolError('Prepare requires an idle referenced worker')
            result = self._send(1, message=message, command=command, sent_us=sent_us, start_us=start_us,
                origin_um=origin_um, target_um=target_um, speed_um_s=speed_um_s, accel_um_s2=accel_um_s2)
            self._command, self._prepare_message = command, message
            return result

    def commit(self, *, message: int, command: int, sent_us: int) -> Queued:
        with self._lock:
            report = self._fresh_report()
            if (command != self._command or report.command != command or not report.ready or
                report.last_message < self._prepare_message):
                raise ProtocolError('Matching source-stamped ready report is required before commit')
            return self._send(2, message=message, command=command, sent_us=sent_us)

    def lease(self, *, message: int, command: int, sent_us: int) -> Queued:
        """Explicitly refresh during prepare/ready as well as committed/moving."""
        with self._lock:
            if not self._command or command != self._command:
                raise ProtocolError('Lease belongs to this connection\'s explicit prepare')
            return self._send(3, message=message, command=command, sent_us=sent_us)

    def stop(self, *, message: int, command: int, sent_us: int) -> Queued:
        """Authenticated boot-bound STOP does not require a clock or ready state."""
        with self._lock:
            return self._send(4, message=message, command=command, sent_us=sent_us)
