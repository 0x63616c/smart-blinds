"""One connection owner per explicitly paired device; HTTP reads never poll it."""
from dataclasses import dataclass, field
import ipaddress
import re
import threading

from integrations.telemetry_transport.client import (
    TelemetrySession, BATTERY_MAX_AGE_MS, SOURCE_MAX_AGE_MS, _now_us,
)


@dataclass(frozen=True)
class Pairing:
    device_id: str
    name: str
    host: str
    port: int
    identity: str
    key: bytes = field(repr=False)
    boot: int = 0

    def endpoint(self):
        address = ipaddress.ip_address(self.host)
        if isinstance(address, ipaddress.IPv6Address) and address.ipv4_mapped is not None:
            address = address.ipv4_mapped
        return (str(address), self.port)

    def validate(self):
        for value in (self.device_id, self.identity):
            if type(value) is not str or re.fullmatch(r"[A-Za-z0-9_-]{1,32}", value) is None:
                raise ValueError("Invalid pairing identity")
        if type(self.name) is not str or not 1 <= len(self.name) <= 80:
            raise ValueError("Invalid device name")
        address = ipaddress.ip_address(self.host)
        if "%" in self.host or address.is_multicast or address.is_unspecified:
            raise ValueError("An explicit unicast address is required")
        if type(self.port) is not int or not 1 <= self.port <= 65535:
            raise ValueError("Invalid device port")
        if type(self.boot) is not int or not 0 < self.boot < (1 << 64):
            raise ValueError("An explicitly selected boot is required")
        if type(self.key) is not bytes or len(self.key) != 32 or not any(self.key):
            raise ValueError("A pre-existing per-device key is required")


class Reader:
    """Sole owner. No per-request thread, handoff, wake or automatic reconnect."""
    def __init__(self, pairing, library, *, factory=TelemetrySession, clock=_now_us, period_s=15):
        pairing.validate()
        if not 1 <= period_s <= 30:
            raise ValueError("Invalid bounded polling period")
        self.pairing, self.library, self.factory = pairing, library, factory
        self.clock, self.period = clock, period_s
        self.lock = threading.Lock()
        self.halt = threading.Event()
        self.observation = None
        self.failed = False
        self.thread = threading.Thread(target=self._run, name="telemetry-"+pairing.device_id)
        self.thread.start()

    def _run(self):
        session = None
        try:
            p = self.pairing
            session = self.factory(self.library, p.host, p.port, p.identity, p.key,
                                   expected_boot=p.boot, timeout_ms=1000, clock=self.clock)
            while not self.halt.is_set():
                result = session.poll()
                with self.lock:
                    self.observation = result
                # No catch-up: every bounded exchange is followed by a full idle period.
                if self.halt.wait(self.period):
                    break
        except Exception:
            # Never include a third-party exception, address or secret in API/logs.
            with self.lock:
                self.failed = True
        finally:
            if session is not None:
                session.close()  # Only this owner performs SDK/native teardown.

    def state(self):
        p = self.pairing
        with self.lock:
            observation, failed = self.observation, self.failed
        value = {
            "id": p.device_id, "name": p.name, "boot": f"{p.boot:016x}",
            "available": bool(observation) and not failed and not self.halt.is_set(),
            "battery_percent": None, "battery_last_percent": None, "battery_age_ms": None,
            "battery_sample_us": None, "battery_state": "absent", "battery_epoch": 0,
            "battery_serial": 0, "charging": None, "charger_age_ms": None,
            "charger_sample_us": None, "usb_connected": None,
            "pd_state": "unavailable", "pd_age_ms": None, "pd_sample_us": None,
            "pending": False, "fault": None, "charge_authorized": False,
        }
        if observation is None:
            return value
        try:
            data = observation.display(self.clock())
        except Exception:
            value["available"] = False
            return value
        b, c, pd = data["battery"], data["charger"], data["pd"]
        value.update(
            battery_last_percent=b["soc_pct"], battery_age_ms=b["age_ms"],
            battery_sample_us=b["sample_us"], battery_state=b["state"],
            battery_epoch=b["bus_epoch"], battery_serial=b["serial"],
            charger_age_ms=c["age_ms"], charger_sample_us=c["sample_us"],
            pd_age_ms=pd["age_ms"], pd_sample_us=pd["sample_us"], pending=data["pending"],
            fault=None if data["fault"]["kind"] == "none" else data["fault"],
        )
        if not value["available"]:
            return value
        if b["state"] == "retained" and b["age_ms"] is not None and b["age_ms"] <= BATTERY_MAX_AGE_MS:
            value["battery_percent"] = b["soc_pct"]
        if c["state"] == "not_charging" and c["age_ms"] is not None and c["age_ms"] <= SOURCE_MAX_AGE_MS:
            value["charging"] = False
        if pd["age_ms"] is not None and pd["age_ms"] <= SOURCE_MAX_AGE_MS:
            value["pd_state"] = pd["state"]
            value["usb_connected"] = pd["attached"]
        return value

    def close(self):
        self.halt.set()
        self.thread.join(timeout=2)
        if self.thread.is_alive():
            with self.lock:
                self.failed = True
            raise RuntimeError("Telemetry owner did not stop")


class PhysicalBridge:
    def __init__(self, bridge_id, pairings, library, **reader_options):
        if type(bridge_id) is not str or re.fullmatch(r"[A-Za-z0-9_-]{1,64}", bridge_id) is None:
            raise ValueError("Invalid explicit bridge identity")
        if not 1 <= len(pairings) <= 8 or len({p.device_id for p in pairings}) != len(pairings):
            raise ValueError("Select one to eight unique paired devices")
        for p in pairings:
            p.validate()
        if len({p.endpoint() for p in pairings}) != len(pairings):
            raise ValueError("A physical endpoint cannot have two owners")
        self.bridge_id, self.readers = bridge_id, []
        try:
            for p in pairings:
                self.readers.append(Reader(p, library, **reader_options))
        except Exception:
            self.close()
            raise

    def state(self):
        return {"schema_version": 2, "mode": "physical_read_only", "bridge_id": self.bridge_id,
                "devices": [r.state() for r in self.readers]}

    def close(self):
        errors = []
        for reader in self.readers:
            try:
                reader.close()
            except Exception as error:
                errors.append(error)
        if errors:
            raise RuntimeError("A telemetry owner remains unclosed")
