"""Typed synchronous worker API over native libcoap. One persistent session/node.

All calls are bounded and serialized. Run this API outside HA's event loop and
outside any motor task. No retry/reconnect or motion command is implicit.
"""
from __future__ import annotations
import ctypes as C
from dataclasses import dataclass
import ipaddress
import json
from pathlib import Path
import re
import threading
import time
from .clock import ClockBounds, ClockUncertain, MAX_ERROR_US


class TransportError(RuntimeError):
    pass


class ProtocolError(TransportError):
    pass


class Rejected(TransportError):
    def __init__(self, code: int):
        super().__init__(f"Device rejected request with CoAP {code >> 5}.{code & 31:02d}")
        self.code = code


@dataclass(frozen=True)
class Status:
    boot: int
    last_wake: int
    awake: bool
    # Intentionally no motion permission or clock-qualified field.


@dataclass(frozen=True)
class Readiness:
    boot: int
    last_probe: int
    awake: bool
    clock_assessed: bool
    device_error_us: int | None
    host_error_us: int | None
    source_age_us: int | None
    clock_model_validated: bool = False
    clock_qualified: bool = False
    motor_ready: bool = False


def _now_us() -> int:
    return time.monotonic_ns() // 1000


def _object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ProtocolError("Duplicate response field")
        result[key] = value
    return result


def _json(payload: bytes) -> dict:
    try:
        value = json.loads(payload, object_pairs_hook=_object,
                           parse_constant=lambda _: (_ for _ in ()).throw(ProtocolError("Nonfinite JSON")))
    except (ValueError, UnicodeError) as error:
        raise ProtocolError("Invalid response encoding") from error
    if type(value) is not dict:
        raise ProtocolError("Response must be an object")
    return value


def _uint64(value: int, *, nonzero=False) -> bool:
    return type(value) is int and int(nonzero) <= value < (1 << 64)


def _hex64(value, *, nonzero=False) -> int:
    if type(value) is not str or re.fullmatch(r"[0-9a-f]{16}", value) is None:
        raise ProtocolError("Invalid exact-width identity")
    result = int(value, 16)
    if nonzero and result == 0:
        raise ProtocolError("Zero boot identity")
    return result


def _load(path: Path):
    library = C.CDLL(str(path.resolve(strict=True)))
    library.sb_client_new.argtypes = [C.c_char_p, C.c_uint16, C.c_char_p, C.POINTER(C.c_uint8)]
    library.sb_client_new.restype = C.c_void_p
    library.sb_motion_client_new.argtypes = library.sb_client_new.argtypes
    library.sb_motion_client_new.restype = C.c_void_p
    if hasattr(library, "sb_telemetry_client_new"):
        library.sb_telemetry_client_new.argtypes = library.sb_client_new.argtypes
        library.sb_telemetry_client_new.restype = C.c_void_p
    library.sb_client_free.argtypes = [C.c_void_p]
    library.sb_client_free.restype = None
    library.sb_client_request.argtypes = [C.c_void_p, C.c_int, C.POINTER(C.c_uint8), C.c_size_t,
        C.c_uint, C.POINTER(C.c_uint8), C.c_size_t, C.POINTER(C.c_size_t), C.POINTER(C.c_int)]
    library.sb_client_request.restype = C.c_int
    library.sb_client_handshakes.argtypes = [C.c_void_p]
    library.sb_client_handshakes.restype = C.c_uint
    return library


class Session:
    """Connect only to an explicitly configured literal IP and per-device PSK.

    Construction may begin DTLS negotiation but sends no application request. An
    initial status call completes and proves the authenticated connection. Failure permanently closes this object's network
    session; create a new object and obtain fresh status deliberately to recover.
    """
    _native_constructor = "sb_client_new"
    def __init__(self, library: Path, host: str, port: int, identity: str, key: bytes,
                 *, timeout_ms: int = 3000):
        if not isinstance(host, str) or '%' in host:
            raise ValueError("Use a literal routable IPv4/IPv6 address")
        ip = ipaddress.ip_address(host)
        if ip.is_multicast or ip.is_unspecified:
            raise ValueError("Use an explicit unicast address")
        if type(port) is not int or not 1 <= port <= 65535:
            raise ValueError("Invalid port")
        if type(identity) is not str or re.fullmatch(r"[A-Za-z0-9_-]{1,32}", identity) is None:
            raise ValueError("Invalid PSK identity")
        if type(key) is not bytes or len(key) != 32 or not any(key):
            raise ValueError("A nonzero 32-byte per-device PSK is required")
        if type(timeout_ms) is not int or not 1 <= timeout_ms <= 5000:
            raise ValueError("Timeout must be 1–5000 ms")
        self._lock = threading.Lock()
        self._library = _load(Path(library))
        self._handle = None
        self._failed = False
        self._boot = None
        self._last_sequence = 0
        self._last_probe = 0
        self._clock = None
        self._clock_probe = 0
        self._timeout = timeout_ms
        key_copy = (C.c_uint8 * 32).from_buffer_copy(key)
        try:
            self._handle = getattr(self._library, self._native_constructor)(
                host.encode("ascii"), port, identity.encode("ascii"), key_copy)
        finally:
            C.memset(key_copy, 0, 32)
        if not self._handle:
            raise TransportError("Could not initialize DTLS session")

    def close(self):
        with self._lock:
            if self._handle:
                self._library.sb_client_free(self._handle)
                self._handle = None
            self._failed = True
            self._boot = None
            self._clock = None

    def __del__(self):
        if getattr(self, "_handle", None):
            self.close()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()

    @property
    def handshakes(self) -> int:
        with self._lock:
            return self._library.sb_client_handshakes(self._handle) if self._handle else 0

    def _exchange(self, kind: int, body: bytes = b"") -> tuple[int, bytes]:
        # Caller owns the Python lock. The native handle also serializes I/O.
        if not self._handle or self._failed:
            raise TransportError("Session is closed; explicit recovery and fresh status required")
        output = (C.c_uint8 * 1024)()
        payload = (C.c_uint8 * len(body)).from_buffer_copy(body)
        size, code = C.c_size_t(), C.c_int()
        result = self._library.sb_client_request(self._handle, kind, payload, len(body), self._timeout,
            output, len(output), C.byref(size), C.byref(code))
        if result:
            self._failed = True
            self._boot = None
            self._clock = None
            raise TransportError("DTLS exchange failed or exceeded its deadline; queued requests discarded")
        return code.value, bytes(output[:size.value])

    def status(self) -> Status:
        with self._lock:
            code, payload = self._exchange(0)
            if code != 69:  # 2.05 Content
                raise Rejected(code)
            try:
                value = _json(payload)
                if (set(value) != {"boot", "last_wake", "awake", "io_qualified", "clock_qualified"}
                    or type(value["awake"]) is not bool or value["io_qualified"] is not False
                    or value["clock_qualified"] is not False):
                    raise ProtocolError("Unsupported status contract")
                status = Status(_hex64(value["boot"], nonzero=True), _hex64(value["last_wake"]), value["awake"])
            except ProtocolError:
                self._failed = True
                self._boot = None
                raise
            if self._boot != status.boot:
                self._last_sequence = status.last_wake
                self._last_probe = 0
                self._clock = None
            else:
                self._last_sequence = max(self._last_sequence, status.last_wake)
            if not status.awake:
                self._clock = None
            self._boot = status.boot
            return status

    def wake(self, boot: int, sequence: int) -> int:
        """Request the bounded radio window only; return its millisecond budget."""
        with self._lock:
            if not _uint64(boot, nonzero=True) or not _uint64(sequence, nonzero=True):
                raise ValueError("Invalid boot/sequence")
            if self._boot != boot or sequence <= self._last_sequence:
                raise ProtocolError("Fresh status and a new wake sequence are required")
            self._last_sequence = sequence  # Consume uncertain outcomes; never retry automatically.
            code, payload = self._exchange(1, boot.to_bytes(8, "big") + sequence.to_bytes(8, "big"))
            if code != 68:  # 2.04 Changed
                raise Rejected(code)
            try:
                value = _json(payload)
                if (set(value) != {"awake_ms", "io_qualified"} or type(value["awake_ms"]) is not int
                    or value["awake_ms"] != 10000 or value["io_qualified"] is not False):
                    raise ProtocolError("Unsupported wake response")
            except ProtocolError:
                self._failed = True
                self._boot = None
                raise
            return value["awake_ms"]

    def _readiness(self, payload: bytes) -> Readiness:
        value = _json(payload)
        if (set(value) != {"boot", "last_probe", "sampled_us", "awake", "clock_assessed",
                          "clock_model_validated", "clock_qualified", "clock_error_us", "motor_ready", "reason"}
            or type(value["awake"]) is not bool or type(value["clock_assessed"]) is not bool
            or value["clock_model_validated"] is not False or value["clock_qualified"] is not False
            or value["motor_ready"] is not False or value["reason"] != "hardware_unconfigured"):
            raise ProtocolError("Unsupported motor-disabled readiness contract")
        boot, probe = _hex64(value["boot"], nonzero=True), _hex64(value["last_probe"])
        sampled = _hex64(value["sampled_us"])
        error = value["clock_error_us"]
        if (boot != self._boot or sampled > (1 << 63) - 1 or
            (value["clock_assessed"] and (not value["awake"] or type(error) is not int or not 0 <= error <= MAX_ERROR_US)) or
            (not value["clock_assessed"] and error is not None)):
            raise ProtocolError("Inconsistent readiness report")
        self._last_probe = max(self._last_probe, probe)
        host_error = source_age = None
        if not value["clock_assessed"] or probe != self._clock_probe:
            self._clock = None
        if self._clock:
            now = _now_us()
            host_error = self._clock.error_us(now)
            source_age = self._clock.source_age_us(sampled, now)
        return Readiness(boot, probe, value["awake"], value["clock_assessed"], error, host_error, source_age)

    def readiness(self) -> Readiness:
        """Read diagnostics. Without matching fresh clock evidence age is unknown.

        Every report is motor-unready in this target. A cached report is never a
        motion capability, including when experimental clock arithmetic passed.
        """
        with self._lock:
            if self._boot is None:
                raise ProtocolError("Fresh status is required before readiness")
            code, payload = self._exchange(4)
            if code != 69:
                raise Rejected(code)
            try:
                return self._readiness(payload)
            except ProtocolError:
                self._failed = True
                self._boot = None
                self._clock = None
                raise
            except ClockUncertain:
                self._clock = None
                raise

    def qualify_clock(self, boot: int, sequence: int) -> Readiness:
        """Measure and echo authenticated four timestamps during the awake window.

        This assesses an unvalidated experimental model; it cannot qualify motion.
        Explicitly call readiness first after reconnect to learn the last probe.
        No failed/uncertain probe is retried or reused automatically.
        """
        with self._lock:
            if not _uint64(boot, nonzero=True) or not _uint64(sequence, nonzero=True):
                raise ValueError("Invalid boot/probe sequence")
            if self._boot != boot or sequence <= self._last_probe:
                raise ProtocolError("Fresh status and a new probe sequence are required")
            self._last_probe = sequence
            self._clock = None
            prefix = boot.to_bytes(8, "big") + sequence.to_bytes(8, "big")
            try:
                sent_us = _now_us()  # Includes wrapper, crypto and queue delays conservatively.
                code, payload = self._exchange(2, prefix)
                received_us = _now_us()
                if code != 69:
                    raise Rejected(code)
                value = _json(payload)
                if (set(value) != {"boot", "probe", "received_us", "sent_us"} or
                    _hex64(value["boot"], nonzero=True) != boot or _hex64(value["probe"]) != sequence):
                    raise ProtocolError("Clock response does not match this boot/probe")
                clock = ClockBounds.estimate(sent_us, _hex64(value["received_us"]),
                                             _hex64(value["sent_us"]), received_us)
                clock.error_us(_now_us())
                code, payload = self._exchange(3, prefix + sent_us.to_bytes(8, "big") + received_us.to_bytes(8, "big"))
                if code != 68:
                    raise Rejected(code)
                self._clock, self._clock_probe = clock, sequence
                result = self._readiness(payload)
                if not result.clock_assessed or result.last_probe != sequence or result.source_age_us is None:
                    raise ClockUncertain("Device did not retain this clock assessment")
                return result
            except ProtocolError:
                self._failed = True
                self._boot = None
                self._clock = None
                raise
            except (ClockUncertain, TransportError):
                self._clock = None
                raise
