"""Seven ideal simulated blinds behind authenticated serialized messages.

No GPIO, sockets to devices, battery estimation, clock estimator or RF simulation.
The model is a test fixture for host integration; the C++ core owns real motion.
"""
from __future__ import annotations
from dataclasses import dataclass
import math
import secrets

from integrations.home_assistant.coordinator import Device, Envelope, Job, Phase, begin_group
from integrations.home_assistant.freshness import SourceStamp
from .auth import Channel, PacketError


def travel(origin: float, target: float, speed: float, acceleration: float, seconds: float):
    distance = abs(target - origin)
    ramp = min(speed / acceleration, math.sqrt(distance / acceleration))
    peak = acceleration * ramp
    cruise = max(0.0, (distance - peak * ramp) / peak) if peak else 0
    duration = 2 * ramp + cruise
    if seconds >= duration:
        return target, True
    if seconds <= 0:
        return origin, False
    if seconds < ramp:
        travelled = acceleration * seconds * seconds / 2
    elif seconds < ramp + cruise:
        travelled = peak * ramp / 2 + peak * (seconds - ramp)
    else:
        remaining = duration - seconds
        travelled = distance - acceleration * remaining * remaining / 2
    return origin + math.copysign(travelled, target - origin), False


@dataclass
class SimNode:
    device_id: str
    low: float
    high: float
    boot: int
    height: float = 300
    consumed_sequence: int = 0
    report_sequence: int = 0
    state: str = "idle"
    fault: str = ""
    online: bool = True
    referenced: bool = True
    pending: dict | None = None
    lease_until: int = 0
    last_lease_sent: int = -1

    def stamp(self, now: int) -> SourceStamp:
        self.report_sequence += 1
        return SourceStamp(now, self.report_sequence, 0)

    def describe(self, now: int) -> Device:
        stamp = self.stamp(now)
        return Device(self.device_id, self.boot, self.consumed_sequence, 1,
                      self.low, self.high, self.height, 20, 40, now, 0,
                      self.referenced, self.online and not self.fault,
                      stamp.sequence)

    def handle(self, kind: str, payload: dict, now: int) -> tuple[str, bool] | None:
        if payload.get("boot_nonce") != self.boot:
            return None
        sequence = payload.get("sequence")
        if kind == "prepare":
            ok = (self.state == "idle" and not self.fault and self.referenced
                  and type(sequence) is int and sequence > self.consumed_sequence
                  and payload.get("calibration_revision") == 1
                  and now < payload["start_ms"] <= now + 10000
                  and self.low <= payload["target_height_mm"] <= self.high)
            if ok:
                self.pending = dict(payload)
                self.consumed_sequence = sequence
                self.state = "prepared"
                self.lease_until, self.last_lease_sent = 0, -1
            return "prepared", ok
        if sequence != self.consumed_sequence:
            return None
        if kind == "stop":
            self.state = "fault" if self.fault else "idle"
            self.pending = None
        elif kind == "commit":
            ok = (self.state in ("prepared", "armed") and self.pending is not None
                  and now < self.pending["start_ms"])
            if ok:
                self.state = "armed"
            return "committed", ok
        elif kind == "lease" and self.state in ("armed", "moving"):
            sent = payload["sent_ms"]
            if self.last_lease_sent < sent <= now and now - sent < 300:
                self.last_lease_sent = sent
                self.lease_until = sent + 300
        return None

    def advance(self, now: int):
        if self.fault:
            self.state = "fault"
        if self.state not in ("armed", "moving"):
            return
        if now >= self.lease_until:
            self.state, self.fault = "fault", "lease_expired"
            return
        command = self.pending
        if command is None or now < command["start_ms"]:
            return
        self.state = "moving"
        self.height, finished = travel(command["start_height_mm"], command["target_height_mm"],
                                      command["speed_mm_s"], command["accel_mm_s2"],
                                      (now - command["start_ms"]) / 1000)
        if finished:
            self.state = "idle"


class Simulation:
    """Call from one serialized owner (HTTP wrapper uses a lock). Times are virtual."""
    def __init__(self, now_ms: int = 1000):
        self.nodes = {f"blind-{i+1}": SimNode(f"blind-{i+1}", i * 10, 2000 + i * 30,
                                            secrets.randbits(64) or 1) for i in range(7)}
        self.channels = {}
        for name, node in self.nodes.items():
            key, session = secrets.token_bytes(32), secrets.token_bytes(16)
            self.channels[name] = (Channel(key, session, node.boot, name, coordinator=True),
                                   Channel(key, session, node.boot, name, coordinator=False))
        self.job: Job | None = None
        self.now = now_ms
        self.last_supervision = now_ms

    def _deliver(self, envelopes: list[Envelope], now: int):
        queue = list(envelopes)
        while queue:
            message = queue.pop(0)
            node = self.nodes[message.recipient]
            if not node.online:
                continue
            coordinator, device = self.channels[node.device_id]
            kind, payload = device.decode(coordinator.encode(message.kind, message.payload, now), now)
            reply = node.handle(kind, payload, now)
            if reply and self.job:
                stamp = node.stamp(now)
                reply_kind, ok = reply
                reply_payload = {"boot_nonce": node.boot, "sequence": message.payload["sequence"],
                                 "sample_ms": stamp.sample_ms, "report_sequence": stamp.sequence,
                                 "clock_error_ms": stamp.clock_error_ms, "ok": ok}
                kind, payload = coordinator.decode(device.encode(reply_kind, reply_payload, now), now)
                queue.extend(self.job.acknowledge(node.device_id, payload["boot_nonce"],
                    payload["sequence"], kind, now, stamp=SourceStamp(payload["sample_ms"],
                    payload["report_sequence"], payload["clock_error_ms"]), ok=payload["ok"]))

    def move(self, percent: float, *, device_id: str | None = None, align: bool = False):
        if self.job and self.job.phase not in (Phase.COMPLETE, Phase.ABORTED):
            raise ValueError("A move is already active; stop it first")
        members = [self.nodes[device_id]] if device_id else list(self.nodes.values())
        job, envelopes = begin_group([node.describe(self.now) for node in members], percent,
                                     self.now, align=align)
        self.job = job
        self._deliver(envelopes, self.now)

    def stop(self):
        if self.job:
            self._deliver(self.job.abort("user stop"), self.now)

    def tick(self, now: int):
        if now < self.now:
            self.stop()
            raise ValueError("simulation clock moved backwards")
        self.now = now
        for node in self.nodes.values():
            node.advance(now)
        if not self.job:
            return
        if now - self.last_supervision >= 100:
            self.last_supervision = now
            for name in self.job.members:
                node = self.nodes[name]
                if not node.online:
                    continue
                coordinator, device = self.channels[name]
                stamp = node.stamp(now)
                body = {"boot_nonce": node.boot, "sequence": node.consumed_sequence,
                        "sample_ms": stamp.sample_ms, "report_sequence": stamp.sequence,
                        "clock_error_ms": 0, "height_mm": node.height,
                        "state": node.state, "fault": node.fault}
                try:
                    _, payload = coordinator.decode(device.encode("report", body, now), now)
                except PacketError:
                    continue
                replies = self.job.report(name, payload["boot_nonce"], payload["sequence"], now,
                    stamp=SourceStamp(payload["sample_ms"], payload["report_sequence"], 0),
                    height_mm=payload["height_mm"], state=payload["state"], fault=payload["fault"])
                self._deliver(replies, now)
        self._deliver(self.job.tick(now), now)

    def state(self) -> dict:
        devices = []
        for i, node in enumerate(self.nodes.values()):
            available = node.online and node.referenced and not node.fault
            opening = bool(node.pending and node.pending["target_height_mm"] > node.height)
            motion = ("opening" if opening else "closing") if node.state == "moving" else "stopped"
            devices.append({"id": node.device_id, "name": f"Blind {i+1} (simulation)",
                "available": available, "position": round((node.height - node.low) / (node.high - node.low) * 100, 2)
                if available else None, "height_mm": node.height, "state": motion,
                "referenced": node.referenced, "fault": node.fault or None,
                "battery_percent": 80 - i, "battery_age_ms": 0, "charging": False})
        low, high = max(n.low for n in self.nodes.values()), min(n.high for n in self.nodes.values())
        heights = [n.height for n in self.nodes.values()]
        spread = max(heights) - min(heights)
        available = all(d["available"] for d in devices)
        aligned = available and spread <= 5
        # No optimistic target or averaged position presented as an aligned result.
        position = (heights[0] - low) / (high - low) * 100 if aligned else None
        if position is not None and not 0 <= position <= 100:
            position = None
        active = [d["state"] for d in devices if d["state"] != "stopped"]
        return {"schema_version": 1, "bridge_id": "smart-blinds-simulator", "mode": "simulation",
                "group": {"id": "room", "name": "Room blinds (simulation)",
                    "available": available, "aligned": aligned, "position": position,
                    "state": active[0] if active else "stopped", "spread_mm": spread,
                    "phase": self.job.phase.value if self.job else "idle",
                    "reason": self.job.reason if self.job else "", "low_mm": low, "high_mm": high},
                "devices": devices}
