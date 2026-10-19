"""Transport-independent group coordinator; no network I/O or hardware claims.

An authenticated adapter supplies fresh device reports and sends returned envelopes.
Run the unit tests with: python3 -m unittest discover -s integrations/home_assistant -p 'test_*.py'
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from math import isfinite


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
    report_ms: int
    clock_error_ms: int
    referenced: bool = True
    ready: bool = True


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
    prepared: set[str] = field(default_factory=set)
    committed: set[str] = field(default_factory=set)
    completed: dict[str, float] = field(default_factory=dict)
    last_report_ms: dict[str, int] = field(default_factory=dict)
    last_lease_ms: int = -1

    def envelope(self, device_id: str, kind: str, **extra) -> Envelope:
        cmd = self.commands[device_id]
        return Envelope(device_id, kind, {
            "version": 1, "boot_nonce": cmd["boot_nonce"], "sequence": cmd["sequence"], **extra,
        })

    def abort(self, reason: str) -> list[Envelope]:
        if self.phase in (Phase.ABORTED, Phase.COMPLETE):
            return []
        self.phase, self.reason = Phase.ABORTED, reason
        return [self.envelope(device_id, "stop") for device_id in self.members]

    def acknowledge(self, device_id: str, boot_nonce: int, sequence: int,
                    kind: str, now_ms: int, *, ok: bool = True) -> list[Envelope]:
        if self.phase in (Phase.ABORTED, Phase.COMPLETE) or device_id not in self.members:
            return []
        command = self.commands[device_id]
        if boot_nonce != command["boot_nonce"] or sequence != command["sequence"]:
            return []  # unrelated or delayed ACK cannot advance this job
        if not ok:
            return self.abort(f"{device_id}: rejected {kind}")
        if kind == "prepared" and self.phase == Phase.PREPARING:
            if now_ms >= self.prepare_deadline_ms:
                return self.abort("prepare deadline")
            self.prepared.add(device_id)
            if self.prepared == self.members.keys():
                self.phase = Phase.COMMITTING
                return [self.envelope(member, "commit") for member in self.members]
        elif kind == "committed" and self.phase == Phase.COMMITTING:
            if now_ms >= self.commit_deadline_ms:
                return self.abort("commit deadline")
            self.committed.add(device_id)
            if self.committed == self.members.keys():
                self.phase = Phase.ARMED
                self.last_report_ms = dict.fromkeys(self.members, now_ms)
                return self.tick(now_ms)
        return []

    def report(self, device_id: str, boot_nonce: int, sequence: int,
               now_ms: int, *, height_mm: float, state: str, fault: str = "") -> list[Envelope]:
        if self.phase not in (Phase.ARMED, Phase.MOVING) or device_id not in self.members:
            return []
        if now_ms < self.last_lease_ms or any(now_ms - report > 250
                for member, report in self.last_report_ms.items() if member not in self.completed):
            return self.abort("late telemetry or coordinator clock discontinuity")
        cmd = self.commands[device_id]
        if boot_nonce != cmd["boot_nonce"]:
            return self.abort(f"{device_id}: reboot during group move")
        if sequence != cmd["sequence"]:
            return []
        if not isfinite(height_mm) or fault or state in ("fault", "unreferenced", "stopped"):
            return self.abort(f"{device_id}: {fault or state}")
        self.last_report_ms[device_id] = now_ms
        if state == "idle" and now_ms >= self.start_ms:
            if abs(height_mm - self.target_height_mm) > 1:
                return self.abort(f"{device_id}: stopped before target")
            self.completed[device_id] = height_mm
            if self.completed.keys() == self.members.keys():
                if max(self.completed.values()) - min(self.completed.values()) > 5:
                    return self.abort("final physical levels disagree")
                self.phase = Phase.COMPLETE
        return []

    def tick(self, now_ms: int) -> list[Envelope]:
        if self.phase == Phase.PREPARING and now_ms >= self.prepare_deadline_ms:
            return self.abort("member missing at prepare deadline")
        if self.phase == Phase.COMMITTING and now_ms >= self.commit_deadline_ms:
            return self.abort("member missing at commit deadline")
        if self.phase not in (Phase.ARMED, Phase.MOVING):
            return []
        if now_ms < self.last_lease_ms:
            return self.abort("coordinator clock moved backwards")
        if now_ms >= self.start_ms:
            self.phase = Phase.MOVING
        if any(now_ms - report > 250 for member, report in self.last_report_ms.items()
               if member not in self.completed):
            return self.abort("member telemetry timeout")
        if self.last_lease_ms >= 0 and now_ms - self.last_lease_ms < 100:
            return []
        self.last_lease_ms = now_ms
        return [self.envelope(member, "lease", sent_ms=now_ms) for member in self.members
                if member not in self.completed]


def begin_group(devices: list[Device], percent: float, now_ms: int,
                *, align: bool = False, speed_mm_s: float = 20,
                accel_mm_s2: float = 40) -> tuple[Job, list[Envelope]]:
    """One shared height and trajectory; align=True explicitly allows unequal origins.

    This is an API candidate, not a Home Assistant service installed on the user's server.
    """
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
        if not d.referenced or not d.ready or not 0 <= now_ms - d.report_ms <= 1500:
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
            "calibration_revision": d.calibration_revision, "start_ms": start,
            "start_height_mm": d.height_mm if align else origin, "target_height_mm": target,
            "speed_mm_s": speed, "accel_mm_s2": acceleration,
        } for d in devices
    }
    job = Job({d.device_id: d for d in devices}, commands, percent, target, start,
              now_ms + 1700, now_ms + 2500)
    return job, [Envelope(member, "prepare", payload) for member, payload in commands.items()]
