"""Read-only authenticated observations. These types never grant motion readiness."""
from copy import deepcopy
from dataclasses import dataclass
import math
import secrets
import struct
import threading

from integrations.thread_transport.client import (
    Session, ProtocolError, Rejected, _hex64, _json, _now_us,
)

MAX_TIME = (1 << 63) - 1
BATTERY_MAX_AGE_MS = 30 * 60 * 1000
SOURCE_MAX_AGE_MS = 60 * 1000


def integer(v, low, high):
    if type(v) is not int or not low <= v <= high:
        raise ProtocolError("Invalid telemetry integer")
    return v


def fields(value, expected):
    if type(value) is not dict or set(value) != set(expected.split()):
        raise ProtocolError("Unsupported telemetry fields")


def stamp(value):
    if value is None:
        return None
    return integer(_hex64(value), 0, MAX_TIME)


@dataclass(frozen=True)
class Observation:
    """Private copied wire data; display() returns a new independent dictionary."""
    _wire: dict
    received_us: int
    roundtrip_us: int

    def display(self, now_us):
        if now_us < self.received_us:
            raise ProtocolError("Host observation clock regressed")
        result = deepcopy(self._wire)
        sent = _hex64(result["sent_us"])
        for name in ("battery", "charger", "pd"):
            value = result[name]
            source = stamp(value["sample_us"])
            value["age_ms"] = None if source is None else (
                (sent-source+999)//1000 + (self.roundtrip_us+999)//1000
                + (now_us-self.received_us+999)//1000)
        return result


def decode(payload, *, boot, nonce, sent_host_us, received_us):
    v = _json(payload)
    fields(v, "schema boot nonce sent_us battery charger pd pending fault charge_authorized")
    if (type(v["schema"]) is not int or v["schema"] != 1
            or _hex64(v["boot"], nonzero=True) != boot
            or _hex64(v["nonce"], nonzero=True) != nonce
            or v["charge_authorized"] is not False or type(v["pending"]) is not bool):
        raise ProtocolError("Wrong telemetry version, binding or policy")
    sent = integer(_hex64(v["sent_us"]), 0, MAX_TIME)
    if received_us < sent_host_us:
        raise ProtocolError("Host exchange clock regressed")
    b, c, p = v["battery"], v["charger"], v["pd"]
    fields(b, "sample_us bus_epoch serial pack soc_pct state")
    fields(c, "sample_us bus_epoch state input_present")
    fields(p, "sample_us bus_epoch epoch serial state current_ma attached")
    fields(v["fault"], "kind code")
    if v["fault"]["kind"] not in ("none", "gauge", "charger", "lifecycle", "runtime"):
        raise ProtocolError("Unknown diagnostic fault")
    integer(v["fault"]["code"], 0, 65535)
    if v["fault"]["kind"] == "none" and v["fault"]["code"]:
        raise ProtocolError("Inconsistent diagnostic fault")
    for item in (b, c, p):
        sample = stamp(item["sample_us"])
        epoch = integer(item["bus_epoch"], 0, (1 << 32)-1)
        if sample is not None and (sample > sent or not epoch):
            raise ProtocolError("Invalid source observation time or epoch")
        if sample is None and epoch:
            raise ProtocolError("Absent observation has an epoch")
    if b["state"] not in ("absent", "retained", "invalid"):
        raise ProtocolError("Unknown battery state")
    integer(b["serial"], 0, (1 << 32)-1)
    soc = b["soc_pct"]
    if soc is not None and (type(soc) not in (int, float) or not math.isfinite(soc) or not 0 <= soc <= 100):
        raise ProtocolError("Invalid measured charge estimate")
    if b["sample_us"] is None:
        if b["state"] != "absent" or b["serial"] or b["pack"] is not None or soc is not None:
            raise ProtocolError("Absent battery fabricated data")
    elif b["state"] == "absent" or not b["serial"] or not _hex64(b["pack"], nonzero=True):
        raise ProtocolError("Incomplete battery identity")
    if c["state"] not in ("not_charging", "unknown") or (c["input_present"] is not None and type(c["input_present"]) is not bool):
        raise ProtocolError("Invalid charger observation")
    if c["state"] == "not_charging" and (c["sample_us"] is None or c["input_present"] is None or v["pending"]):
        raise ProtocolError("Unobserved charger state")
    if c["state"] == "unknown" and c["input_present"] is not None:
        raise ProtocolError("Unknown charger presented as connected")
    if p["state"] not in ("unavailable", "detached", "negotiating", "unapproved", "policy_observed", "fault"):
        raise ProtocolError("Unknown PD observation")
    integer(p["epoch"], 0, (1 << 32)-1)
    integer(p["serial"], 0, (1 << 32)-1)
    integer(p["current_ma"], 0, 65535)
    if p["attached"] is not None and type(p["attached"]) is not bool:
        raise ProtocolError("Invalid observed Type-C attachment")
    if (p["state"] == "unavailable") != (p["attached"] is None):
        raise ProtocolError("Inconsistent observed Type-C attachment")
    if p["sample_us"] is None:
        if p["epoch"] or p["serial"] or p["current_ma"] or p["state"] != "unavailable":
            raise ProtocolError("Absent PD fabricated data")
    elif not p["epoch"] or not p["serial"]:
        raise ProtocolError("Incomplete PD identity")
    if p["state"] == "detached" and p["attached"] is not False:
        raise ProtocolError("Detached source reported attached")
    if p["state"] == "policy_observed" and (p["current_ma"] != 2500 or p["attached"] is not True):
        raise ProtocolError("Unexpected observed policy")
    if v["pending"] and p["state"] != "unavailable":
        raise ProtocolError("Pending source presented as current")
    if v["fault"]["kind"] != "none" and (b["state"] == "retained" or c["state"] != "unknown" or p["state"] != "unavailable"):
        raise ProtocolError("Fault retained a current presentation")
    return Observation(v, received_us, received_us-sent_host_us)


class _Handle(Session):
    _native_constructor = "sb_telemetry_client_new"


class TelemetrySession:
    """Only poll/close; its native handle independently rejects all other routes.

    No wake, clock, command, retry, reconnect or boot adoption operation exists.
    Expected boot and PSK are explicit pre-existing pairing data, not calibration.
    """
    def __init__(self, *args, expected_boot, clock=_now_us, nonce_source=lambda: secrets.randbits(64) or 1, **kwargs):
        self.boot = integer(expected_boot, 1, (1 << 64)-1)
        self._clock, self._nonce_source = clock, nonce_source
        self._handle = _Handle(*args, **kwargs)
        self._previous = None
        self._lock = threading.Lock()

    def close(self):
        with self._lock:
            self._handle.close()

    def poll(self):
        with self._lock:
            nonce = integer(self._nonce_source(), 1, (1 << 64)-1)
            try:
                before = self._clock()
                with self._handle._lock:
                    code, payload = self._handle._exchange(7, struct.pack(">QQ", self.boot, nonce))
                after = self._clock()
                if code != 69:
                    raise Rejected(code)
                result = decode(payload, boot=self.boot, nonce=nonce, sent_host_us=before, received_us=after)
                old, new = self._previous, result._wire
                if old is not None:
                    if _hex64(new["sent_us"]) < _hex64(old["sent_us"]):
                        raise ProtocolError("Device response clock regressed")
                    for name, identity, measured in (
                        ("battery", ("bus_epoch", "serial"), ("sample_us", "pack", "soc_pct")),
                        ("pd", ("bus_epoch", "epoch", "serial"), ("sample_us", "current_ma")),
                    ):
                        a, b = old[name], new[name]
                        if a["sample_us"] is None:
                            continue
                        if b["sample_us"] is None:
                            raise ProtocolError("Device discarded historical observation")
                        ka, kb = tuple(a[k] for k in identity), tuple(b[k] for k in identity)
                        if kb < ka or _hex64(b["sample_us"]) < _hex64(a["sample_us"]):
                            raise ProtocolError("Source observation regressed")
                        if kb == ka and any(a[k] != b[k] for k in measured):
                            raise ProtocolError("Conflicting source observation")
                    if (old["battery"]["pack"] is not None
                            and old["battery"]["pack"] != new["battery"]["pack"]):
                        raise ProtocolError("Pack binding changed")
                    if old["fault"]["kind"] != "none" and old["fault"] != new["fault"]:
                        if old["fault"] != {"kind": "runtime", "code": 0} or new["fault"]["kind"] == "none":
                            raise ProtocolError("First observed fault was cleared or replaced")
                self._previous = deepcopy(new)
                return result
            except Exception:
                self._handle.close()
                raise

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()
