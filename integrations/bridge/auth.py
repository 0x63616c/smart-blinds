"""Experimental authenticated packet codec; not a radio stack or provisioning flow.

HMAC-SHA256 supplies integrity/authentication, not confidentiality. Keys, device boot
nonce and fresh session are established out of band in this simulator. Production
requires a reviewed handshake, key storage/rotation and authenticated clock estimator.
"""
from __future__ import annotations
import hashlib
import hmac
import json
from math import isfinite
import struct

HEADER = struct.Struct("!BB16sQQQH")
MAX_PACKET = 1200
TAG_SIZE = 32


class PacketError(ValueError):
    pass


def _object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise PacketError("duplicate JSON field")
        result[key] = value
    return result


def _finite(value, depth=0):
    if depth > 12:
        raise PacketError("payload too deeply nested")
    if isinstance(value, float) and not isfinite(value):
        raise PacketError("nonfinite number")
    if isinstance(value, dict):
        for child in value.values():
            _finite(child, depth + 1)
    elif isinstance(value, list):
        for child in value:
            _finite(child, depth + 1)


class Channel:
    def __init__(self, key: bytes, session: bytes, boot_nonce: int, device_id: str,
                 *, coordinator: bool):
        if len(key) != 32 or len(session) != 16 or not 0 < boot_nonce < 2**64:
            raise ValueError("32-byte key, 16-byte fresh session and uint64 boot nonce required")
        if not device_id or len(device_id.encode()) > 64:
            raise ValueError("invalid device identity")
        self._key, self.session, self.boot_nonce = key, session, boot_nonce
        self._context = b"smart-blinds-packet-v1\0" + device_id.encode() + b"\0"
        self._tx_direction = 0 if coordinator else 1
        self._tx_sequence = 0
        self._rx_sequence = 0

    def encode(self, kind: str, payload: dict, now_ms: int) -> bytes:
        if type(now_ms) is not int or not 0 <= now_ms < 2**64:
            raise PacketError("invalid send time")
        if not isinstance(kind, str) or not kind or len(kind) > 32 or not isinstance(payload, dict):
            raise PacketError("invalid message")
        _finite(payload)
        body = json.dumps({"kind": kind, "payload": payload}, separators=(",", ":"),
                          sort_keys=True, allow_nan=False).encode()
        if HEADER.size + len(body) + TAG_SIZE > MAX_PACKET:
            raise PacketError("oversized packet")
        if self._tx_sequence >= 2**64 - 1:
            raise PacketError("packet counter exhausted; re-establish session")
        self._tx_sequence += 1
        message = HEADER.pack(1, self._tx_direction, self.session, self.boot_nonce,
                              self._tx_sequence, now_ms, len(body)) + body
        return message + hmac.digest(self._key, self._context + message, hashlib.sha256)

    def decode(self, data: bytes, now_ms: int, *, max_age_ms: int = 250,
               clock_error_ms: int = 0) -> tuple[str, dict]:
        if not HEADER.size + TAG_SIZE <= len(data) <= MAX_PACKET:
            raise PacketError("packet size")
        if type(now_ms) is not int or not 0 <= now_ms < 2**64:
            raise PacketError("invalid receive time")
        if type(clock_error_ms) is not int or not 0 <= clock_error_ms <= 10:
            raise PacketError("uncertain clock")
        if type(max_age_ms) is not int or not 0 <= max_age_ms <= 250:
            raise PacketError("invalid lifetime")
        message, tag = data[:-TAG_SIZE], data[-TAG_SIZE:]
        expected = hmac.digest(self._key, self._context + message, hashlib.sha256)
        if not hmac.compare_digest(tag, expected):
            raise PacketError("authentication failed")
        version, direction, session, boot, sequence, sent, length = HEADER.unpack(message[:HEADER.size])
        if version != 1 or direction != 1 - self._tx_direction or session != self.session or boot != self.boot_nonce:
            raise PacketError("wrong version, direction, session or boot")
        if len(message) != HEADER.size + length or sequence <= self._rx_sequence:
            raise PacketError("invalid length or replayed packet")
        earliest = max(0, sent - clock_error_ms)
        if sent > now_ms + clock_error_ms or now_ms - earliest > max_age_ms:
            raise PacketError("stale or future packet")
        try:
            body = json.loads(message[HEADER.size:], object_pairs_hook=_object,
                              parse_constant=lambda _: (_ for _ in ()).throw(PacketError("nonfinite number")))
            _finite(body)
        except (UnicodeError, json.JSONDecodeError, RecursionError) as exc:
            raise PacketError("invalid payload") from exc
        if (not isinstance(body, dict) or set(body) != {"kind", "payload"}
                or not isinstance(body["kind"], str) or not 0 < len(body["kind"]) <= 32
                or not isinstance(body["payload"], dict)):
            raise PacketError("invalid envelope schema")
        self._rx_sequence = sequence  # malformed/unauthenticated packets cannot advance it
        return body["kind"], body["payload"]
