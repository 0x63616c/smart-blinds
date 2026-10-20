"""Finite-time local bridge client; never retries a movement request."""
import asyncio
import ipaddress
import json
import math
from urllib.parse import urlsplit

from aiohttp import ClientError, ClientSession, ClientTimeout


class BridgeError(Exception):
    """A failed or rejected bridge request."""


class BridgeAuthError(BridgeError):
    """The bridge rejected the token."""


def normalize_url(value: str) -> str:
    parsed = urlsplit(value)
    if parsed.scheme not in ("http", "https") or not parsed.hostname:
        raise ValueError("invalid_url")
    if parsed.username or parsed.password or parsed.query or parsed.fragment or parsed.path not in ("", "/"):
        raise ValueError("invalid_url")
    # Plain HTTP is solely for a simulator on the same host. A LAN bridge needs
    # HTTPS with normal certificate validation, or a separately designed tunnel.
    if parsed.scheme == "http":
        try:
            local = ipaddress.ip_address(parsed.hostname).is_loopback
        except ValueError:
            local = parsed.hostname == "localhost"
        if not local:
            raise ValueError("https_required")
    try:
        _ = parsed.port
    except ValueError as exc:
        raise ValueError("invalid_url") from exc
    return value.rstrip("/")


def validate_state(value: object) -> dict:
    """Reject malformed state before any entity can present it as measured."""
    if not isinstance(value, dict) or value.get("schema_version") != 1 or value.get("mode") != "simulation":
        raise BridgeError("Unsupported bridge schema or mode; this release supports simulation only")
    if not isinstance(value.get("bridge_id"), str) or not value["bridge_id"]:
        raise BridgeError("Missing bridge identity")
    group, devices = value.get("group"), value.get("devices")
    if not isinstance(group, dict) or not isinstance(devices, list) or not 1 <= len(devices) <= 8:
        raise BridgeError("Invalid bridge members")
    ids = set()
    for item in [group, *devices]:
        if not isinstance(item, dict) or not isinstance(item.get("id"), str) or not item["id"] or item["id"] in ids:
            raise BridgeError("Invalid or duplicate identity")
        ids.add(item["id"])
        if not isinstance(item.get("name"), str) or type(item.get("available")) is not bool:
            raise BridgeError("Invalid entity state")
        position = item.get("position")
        if position is not None and (type(position) not in (int, float) or not math.isfinite(position) or not 0 <= position <= 100):
            raise BridgeError("Invalid measured position")
        if item.get("state") not in ("opening", "closing", "stopped"):
            raise BridgeError("Invalid movement state")
    if group["id"] != "room" or type(group.get("aligned")) is not bool:
        raise BridgeError("Invalid group state")
    if not group["aligned"] and group.get("position") is not None:
        raise BridgeError("Unaligned group must not have a reported position")
    for device in devices:
        if type(device.get("referenced")) is not bool:
            raise BridgeError("Invalid reference state")
        age, soc = device.get("battery_age_ms"), device.get("battery_percent")
        if age is not None and (type(age) is not int or age < 0):
            raise BridgeError("Invalid battery sample age")
        if soc is not None and (type(soc) not in (int, float) or not math.isfinite(soc) or not 0 <= soc <= 100):
            raise BridgeError("Invalid battery value")
        if device.get("charging") is not None and type(device["charging"]) is not bool:
            raise BridgeError("Invalid charging state")
    return value


class BridgeClient:
    def __init__(self, session: ClientSession, base_url: str, token: str):
        self.session = session
        self.base_url = normalize_url(base_url)
        if not isinstance(token, str) or len(token) < 32 or any(c.isspace() for c in token):
            raise ValueError("invalid_token")
        self._token = token

    async def _request(self, method: str, path: str, payload=None):
        try:
            async with self.session.request(
                method, self.base_url + path, json=payload,
                headers={"Authorization": "Bearer " + self._token},
                timeout=ClientTimeout(total=5), allow_redirects=False,
            ) as response:
                if response.status in (401, 403):
                    raise BridgeAuthError("Bridge authentication failed")
                if response.status not in (200, 202):
                    # Do not echo server text, URLs or credentials into HA logs.
                    raise BridgeError(f"Bridge rejected request ({response.status})")
                if int(response.headers.get("Content-Length", "0")) > 32768:
                    raise BridgeError("Bridge response too large")
                stream, data = response.content, bytearray()
                while chunk := await stream.read(min(4096, 32769 - len(data))):
                    data.extend(chunk)
                    if len(data) > 32768:
                        raise BridgeError("Bridge response too large")
                return json.loads(data)
        except (ClientError, asyncio.TimeoutError, ValueError) as exc:
            raise BridgeError("Bridge response unavailable or invalid") from exc

    async def async_state(self):
        return validate_state(await self._request("GET", "/v1/state"))

    async def async_move(self, target: str, position: float, *, align: bool = False):
        result = await self._request("POST", "/v1/move", {"target": target, "position": position, "align": align})
        if not isinstance(result, dict) or result.get("accepted") is not True:
            raise BridgeError("Bridge did not accept command")

    async def async_stop(self):
        await self._request("POST", "/v1/stop", {})
