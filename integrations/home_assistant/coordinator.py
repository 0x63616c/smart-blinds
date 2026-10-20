"""Transport-independent group coordinator; no network I/O or hardware claims.

An authenticated adapter supplies fresh device reports and sends returned envelopes.
Run the unit tests with: python3 -m unittest discover -s integrations/home_assistant -p 'test_*.py'
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from math import isfinite
if __package__:
    from .freshness import FreshnessTracker, SourceStamp, earliest_sample
else:  # Existing standalone unittest discovery entry point.
    from freshness import FreshnessTracker, SourceStamp, earliest_sample


class Phase(str, Enum):
    PREPARING = "preparing"
    COMMITTING = "committing"
    ARMED = "armed"
    MOVING = "moving"
    COMPLETE = "complete"
    ABORTED = "aborted"


@dataclass(frozen=True)
class Device:
    device_id: str
    boot_nonce: int
    consumed_sequence: int
    calibration_revision: int
    low_mm: float
    high_mm: float
    height_mm: float
    max_speed_mm_s: float
    max_accel_mm_s2: float
    report_ms: int  # Actual source sample time translated into coordinator clock
    clock_error_ms: int
    referenced: bool = True
    ready: bool = True
    report_sequence: int = 1


@dataclass(frozen=True)
class Envelope:
    recipient: str
    kind: str
    payload: dict
    # All commands are unretained. Sender must enforce this at the MQTT adapter.
    retain: bool = False


@dataclass
class Job:
    members: dict[str, Device]
    commands: dict[str, dict]
    requested_percent: float
    target_height_mm: float
    start_ms: int
    prepare_deadline_ms: int
    commit_deadline_ms: int
    phase: Phase = Phase.PREPARING
    reason: str = ""
    queued: set[str] = field(default_factory=set)
    prepared: set[str] = field(default_factory=set)
    committed: set[str] = field(default_factory=set)
    completed: dict[str, float] = field(default_factory=dict)
    last_report_ms: dict[str, int] = field(default_factory=dict)
    lease_sent_ms: dict[str, int] = field(default_factory=dict)
    last_now_ms: int = 0
    freshness: FreshnessTracker = field(default_factory=FreshnessTracker)

    def envelope(self, device_id: str, kind: str, **extra) -> Envelope:
        cmd = self.commands[device_id]
        return Envelope(device_id, kind, {
            "version": 1, "boot_nonce": cmd["boot_nonce"], "sequence": cmd["sequence"],
            "sent_ms": self.last_now_ms, **extra,
        })

    def abort(self, reason: str) -> list[Envelope]:
        if self.phase in (Phase.ABORTED, Phase.COMPLETE):
            return []
        self.phase, self.reason = Phase.ABORTED, reason
        return [self.envelope(device_id, "stop") for device_id in self.members]

    def _supervise(self, now_ms: int) -> list[Envelope]:
        """No fresh receipt or late tick can revive an expired supervision period."""
        if self.phase in (Phase.ABORTED, Phase.COMPLETE):
            return []
        if type(now_ms) is not int or not 0 <= now_ms < 2**63 or now_ms < self.last_now_ms:
            return self.abort("coordinator clock moved backwards or is invalid")
        self.last_now_ms = now_ms
        if self.phase == Phase.PREPARING and now_ms >= self.prepare_deadline_ms:
            return self.abort("member missing at prepare deadline")
        if self.phase == Phase.COMMITTING and now_ms >= self.commit_deadline_ms:
            return self.abort("member missing at commit deadline")
        for member in self.queued - self.completed.keys():
            # 250 ms leaves margin before the device's source-based 300 ms lease;
            # a coordinator stall must abort, never emit catch-up leases.
            if now_ms - self.lease_sent_ms[member] >= 250:
                return self.abort(f"{member}: lease refresh missed")
            source = self.last_report_ms.get(member, self.commands[member]["sent_ms"])
            if now_ms - source > 250:
                return self.abort(f"{member}: telemetry timeout")
        return []

    def prepare_queued(self, device_id: str, boot_nonce: int, sequence: int,
                       now_ms: int, *, ok: bool = True) -> list[Envelope]:
        """Authenticated transport receipt only; never source telemetry or ready.

        The first lease deadline derives from the original prepare source time,
        not this receipt. Repeated queue acknowledgements cannot extend it.
        """
        stopped = self._supervise(now_ms)
        if stopped or self.phase != Phase.PREPARING or device_id not in self.members:
            return stopped
        cmd = self.commands[device_id]
        if boot_nonce != cmd["boot_nonce"] or sequence != cmd["sequence"] or device_id in self.queued:
            return []
        if type(ok) is not bool or not ok:
            return self.abort(f"{device_id}: prepare queue rejected")
        if now_ms - cmd["sent_ms"] >= 250:
            return self.abort(f"{device_id}: late prepare queue receipt")
        self.queued.add(device_id)
        self.lease_sent_ms[device_id] = cmd["sent_ms"]
        return self.tick(now_ms)

    def acknowledge(self, device_id: str, boot_nonce: int, sequence: int,
                    kind: str, now_ms: int, *, stamp: SourceStamp, ok: bool = True) -> list[Envelope]:
        stopped = self._supervise(now_ms)
        if stopped or self.phase in (Phase.ABORTED, Phase.COMPLETE) or device_id not in self.queued:
            return stopped
        command = self.commands[device_id]
        if boot_nonce != command["boot_nonce"] or sequence != command["sequence"]:
            return []  # unrelated or delayed ACK cannot advance this job
        if not ((kind == "prepared" and self.phase == Phase.PREPARING) or
                (kind == "committed" and self.phase == Phase.COMMITTING)):
            return []
        try:
            sampled = self.freshness.accept(device_id, stamp, now_ms, 250)
        except ValueError:
            return []  # stale ACK must not establish readiness or refresh supervision
        if type(ok) is not bool or not ok:
            return self.abort(f"{device_id}: rejected {kind}")
        self.last_report_ms[device_id] = sampled
        if kind == "prepared":
            self.prepared.add(device_id)
            if self.prepared == self.members.keys():
                self.phase = Phase.COMMITTING
                return [self.envelope(member, "commit") for member in self.members]
        else:
            self.committed.add(device_id)
            if self.committed == self.members.keys():
                self.phase = Phase.ARMED
                return self.tick(now_ms)
        return []

    def report(self, device_id: str, boot_nonce: int, sequence: int,
               now_ms: int, *, stamp: SourceStamp, height_mm: float,
               state: str, fault: str = "") -> list[Envelope]:
        stopped = self._supervise(now_ms)
        if stopped or self.phase in (Phase.ABORTED, Phase.COMPLETE) or device_id not in self.queued:
            return stopped
        cmd = self.commands[device_id]
        if boot_nonce != cmd["boot_nonce"]:
            return self.abort(f"{device_id}: reboot during group move")
        if sequence != cmd["sequence"]:
            return []
        try:
            sampled = self.freshness.accept(device_id, stamp, now_ms, 250)
        except ValueError:
            return []
        allowed = ("preparing", "prepared") if self.phase == Phase.PREPARING else (
            ("prepared", "armed") if self.phase == Phase.COMMITTING else ("armed", "moving", "idle"))
        if not isfinite(height_mm) or fault or state not in allowed:
            return self.abort(f"{device_id}: {fault or state}")
        if self.phase == Phase.COMMITTING and device_id in self.committed and state != "armed":
            return self.abort(f"{device_id}: commit readiness lost")
        self.last_report_ms[device_id] = sampled
        if self.phase == Phase.PREPARING and state == "preparing":
            self.prepared.discard(device_id)  # A readiness withdrawal requires a new ready ACK.
        if self.phase in (Phase.ARMED, Phase.MOVING) and state == "idle" and sampled >= self.start_ms:
            if abs(height_mm - self.target_height_mm) > 1:
                return self.abort(f"{device_id}: stopped before target")
            self.completed[device_id] = height_mm
            if self.completed.keys() == self.members.keys():
                if max(self.completed.values()) - min(self.completed.values()) > 5:
                    return self.abort("final physical levels disagree")
                self.phase = Phase.COMPLETE
        return []

    def tick(self, now_ms: int) -> list[Envelope]:
        stopped = self._supervise(now_ms)
        if stopped or self.phase in (Phase.ABORTED, Phase.COMPLETE):
            return stopped
        if self.phase == Phase.ARMED and now_ms >= self.start_ms:
            self.phase = Phase.MOVING
        due = [member for member in self.members if member in self.queued and member not in self.completed
               and now_ms - self.lease_sent_ms[member] >= 100]
        for member in due:
            self.lease_sent_ms[member] = now_ms
        return [self.envelope(member, "lease", sent_ms=now_ms) for member in due]


def begin_group(devices: list[Device], percent: float, now_ms: int,
                *, align: bool = False, speed_mm_s: float = 20,
                accel_mm_s2: float = 40) -> tuple[Job, list[Envelope]]:
    """One shared height and trajectory; align=True explicitly allows unequal origins.

    This is an API candidate, not a Home Assistant service installed on the user's server.
    """
    if type(now_ms) is not int or not 0 < now_ms < 2**63 - 3000:
        raise ValueError("invalid coordinator start time")
    if not 1 <= len(devices) <= 8 or len({d.device_id for d in devices}) != len(devices):
        raise ValueError("need 1-8 unique members")
    if not isfinite(percent) or not 0 <= percent <= 100:
        raise ValueError("position must be 0..100")
    if not isfinite(speed_mm_s) or not isfinite(accel_mm_s2) or speed_mm_s <= 0 or accel_mm_s2 <= 0:
        raise ValueError("positive finite speed and acceleration required")
    for d in devices:
        if not all(isfinite(v) for v in (d.low_mm, d.high_mm, d.height_mm,
                                        d.max_speed_mm_s, d.max_accel_mm_s2)):
            raise ValueError(f"{d.device_id}: nonfinite geometry")
        if not (0 < d.boot_nonce < 2**64 and 0 <= d.consumed_sequence < 2**64 - 1
                and 0 < d.calibration_revision < 2**32):
            raise ValueError(f"{d.device_id}: invalid device epoch")
        if d.low_mm >= d.high_mm or not d.low_mm <= d.height_mm <= d.high_mm:
            raise ValueError(f"{d.device_id}: invalid travel")
        earliest_sample(SourceStamp(d.report_ms, d.report_sequence, d.clock_error_ms), now_ms, 1500)
        if not d.referenced or not d.ready:
            raise ValueError(f"{d.device_id}: unavailable or stale")
        if not 0 <= d.clock_error_ms <= 10:
            raise ValueError(f"{d.device_id}: clock not synchronized")
        if d.max_speed_mm_s <= 0 or d.max_accel_mm_s2 <= 0:
            raise ValueError(f"{d.device_id}: invalid motion capability")
    low, high = max(d.low_mm for d in devices), min(d.high_mm for d in devices)
    if low >= high:
        raise ValueError("no common reachable physical level")
    target = low + (high - low) * percent / 100
    heights = [d.height_mm for d in devices]
    if not align and max(heights) - min(heights) > 5:
        raise ValueError("needs_alignment: run explicit align first")
    origin = sum(heights) / len(heights)
    if not align and not all(d.low_mm <= origin <= d.high_mm for d in devices):
        raise ValueError("needs_alignment: origin outside common range")
    speed = min(speed_mm_s, *(d.max_speed_mm_s for d in devices))
    acceleration = min(accel_mm_s2, *(d.max_accel_mm_s2 for d in devices))
    start = now_ms + 3000
    commands = {
        d.device_id: {
            "version": 1, "boot_nonce": d.boot_nonce, "sequence": d.consumed_sequence + 1,
            "calibration_revision": d.calibration_revision, "sent_ms": now_ms, "start_ms": start,
            "start_height_mm": d.height_mm if align else origin, "target_height_mm": target,
            "speed_mm_s": speed, "accel_mm_s2": acceleration,
        } for d in devices
    }
    job = Job({d.device_id: d for d in devices}, commands, percent, target, start,
              now_ms + 1700, now_ms + 2500, last_now_ms=now_ms)
    for d in devices:
        job.freshness.accept(d.device_id,
                             SourceStamp(d.report_ms, d.report_sequence, d.clock_error_ms), now_ms, 1500)
    return job, [Envelope(member, "prepare", payload) for member, payload in commands.items()]
