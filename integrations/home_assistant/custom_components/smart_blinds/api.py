"""Finite-time local bridge client; never retries a movement request."""
import asyncio
import ipaddress
import json
import math
from urllib.parse import urlsplit

from typing import TYPE_CHECKING

# The schema validators are also used by dependency-free transport checks.
if TYPE_CHECKING:
    from aiohttp import ClientSession


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
        raise BridgeError("Unsupported simulator schema or mode")
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


def validate_physical_state(value: object) -> dict:
    """Physical diagnostics have a separate exact schema and no control state."""
    if (type(value) is not dict or set(value) != {"schema_version", "mode", "bridge_id", "devices"}
        or type(value["schema_version"]) is not int or value["schema_version"] != 2
        or value["mode"] != "physical_read_only" or type(value["bridge_id"]) is not str or not value["bridge_id"]
        or type(value["devices"]) is not list or not 1 <= len(value["devices"]) <= 8):
        raise BridgeError("Unsupported physical read-only bridge schema")
    fields = set("id name boot available battery_percent battery_last_percent battery_age_ms battery_sample_us battery_state battery_epoch battery_serial charging charger_age_ms charger_sample_us usb_connected pd_state pd_age_ms pd_sample_us pending fault charge_authorized".split())
    ids = set()
    def hex64(v):
        return type(v) is str and len(v) == 16 and all(c in "0123456789abcdef" for c in v)
    for d in value["devices"]:
        if (type(d) is not dict or set(d) != fields or type(d["id"]) is not str or not d["id"] or d["id"] in ids
            or type(d["name"]) is not str or not d["name"] or not hex64(d["boot"]) or int(d["boot"],16) == 0
            or type(d["available"]) is not bool or type(d["pending"]) is not bool or d["charge_authorized"] is not False):
            raise BridgeError("Invalid physical identity or state")
        ids.add(d["id"])
        for key in ("battery_age_ms", "charger_age_ms", "pd_age_ms"):
            age = d[key]
            if age is not None and (type(age) is not int or not 0 <= age <= (1 << 63)-1):
                raise BridgeError("Invalid informational age")
        for key in ("battery_sample_us", "charger_sample_us", "pd_sample_us"):
            if d[key] is not None and not hex64(d[key]):
                raise BridgeError("Invalid original source timestamp")
        for key in ("battery_percent", "battery_last_percent"):
            v = d[key]
            if v is not None and (type(v) not in (int,float) or not math.isfinite(v) or not 0 <= v <= 100):
                raise BridgeError("Invalid battery estimate")
        for key in ("battery_epoch", "battery_serial"):
            if type(d[key]) is not int or not 0 <= d[key] < (1 << 32):
                raise BridgeError("Invalid source identity")
        if d["battery_state"] not in ("absent", "retained", "invalid"):
            raise BridgeError("Invalid battery state")
        for key in ("charging", "usb_connected"):
            if d[key] is not None and type(d[key]) is not bool:
                raise BridgeError("Invalid measured binary state")
        if d["charging"] is True:
            raise BridgeError("This device image cannot authorize charging")
        if d["pd_state"] not in ("unavailable", "detached", "negotiating", "unapproved", "policy_observed", "fault"):
            raise BridgeError("Invalid observed source policy")
        if d["fault"] is not None and (type(d["fault"]) is not dict or set(d["fault"]) != {"kind","code"}
            or d["fault"]["kind"] not in ("gauge","charger","lifecycle","runtime")
            or type(d["fault"]["code"]) is not int or not 0 <= d["fault"]["code"] <= 65535):
            raise BridgeError("Invalid source fault")
        if d["battery_percent"] is not None and (not d["available"] or d["fault"] is not None
            or d["battery_state"] != "retained" or d["battery_age_ms"] is None or d["battery_age_ms"] > 1800000
            or d["battery_sample_us"] is None or not d["battery_epoch"] or not d["battery_serial"]
            or d["battery_percent"] != d["battery_last_percent"]):
            raise BridgeError("Unobserved or stale battery estimate")
        if d["charging"] is not None and (not d["available"] or d["pending"]
            or d["fault"] is not None or d["charger_age_ms"] is None or d["charger_age_ms"] > 60000
            or d["charger_sample_us"] is None):
            raise BridgeError("Unobserved or stale charger state")
        if d["usb_connected"] is not None and (not d["available"] or d["pending"] or d["fault"] is not None
            or d["pd_age_ms"] is None or d["pd_age_ms"] > 60000 or d["pd_sample_us"] is None
            or d["pd_state"] == "unavailable"):
            raise BridgeError("Unobserved or stale Type-C attachment")
    return value


PHYSICAL_CONTROL_FIELDS = set("control_configured position height_mm position_age_ms position_sample_us referenced state".split())


def validate_control_state(value):
    """Pinned physical-control schema; diagnostics never become motion authority."""
    if (type(value) is not dict or set(value)!={'schema_version','mode','bridge_id','devices','group'}
        or type(value['schema_version']) is not int or value['schema_version']!=3
        or value['mode']!='physical_control' or type(value['devices']) is not list):
        raise BridgeError('Unsupported physical control schema')
    devices=value['devices']
    if any(type(d) is not dict or not PHYSICAL_CONTROL_FIELDS<=set(d) for d in devices):
        raise BridgeError('Missing physical control fields')
    # The unchanged informational validator still owns every battery/source rule.
    validate_physical_state(dict(schema_version=2,mode='physical_read_only',bridge_id=value['bridge_id'],
        devices=[{k:v for k,v in d.items() if k not in PHYSICAL_CONTROL_FIELDS} for d in devices]))
    g=value['group']
    if (type(g) is not dict or set(g)!=set('id name available control_configured position state aligned spread_mm phase reason low_mm high_mm intent'.split())
        or type(g['control_configured']) is not bool or type(g['intent']) is not int or g['intent']<0
        or g['phase'] not in ('idle','queued','preflight','preparing','committing','armed','moving','complete','aborted')
        or type(g['reason']) is not str):
        raise BridgeError('Invalid physical group state')
    # Common cover shape/range semantics, without selecting simulator mode locally.
    validate_state(dict(value,schema_version=1,mode='simulation'))
    for d in devices:
        age=d['position_age_ms'];stamp=d['position_sample_us'];height=d['height_mm']
        if (type(d['control_configured']) is not bool or
            (age is not None and (type(age) is not int or age<0)) or
            (stamp is not None and (type(stamp) is not str or len(stamp)!=16 or any(c not in '0123456789abcdef' for c in stamp))) or
            (height is not None and (type(height) not in (int,float) or not math.isfinite(height) or not -1e6<=height<=1e6))):
            raise BridgeError('Invalid original position evidence')
        if (d['referenced'] and (height is None or age is None or age>1800000 or stamp is None)) or (not d['referenced'] and d['position'] is not None):
            raise BridgeError('Unobserved or stale position')
        if not d['control_configured'] and d['position'] is not None:
            raise BridgeError('Unconfigured physical coordinate')
    for k in ('low_mm','high_mm','spread_mm'):
        v=g[k]
        if v is not None and (type(v) not in (int,float) or not math.isfinite(v)):
            raise BridgeError('Invalid shared range')
    if (g['available'] and not g['control_configured']) or (g['position'] is not None and
        (not g['control_configured'] or g['low_mm'] is None or g['high_mm'] is None or g['low_mm']>=g['high_mm'])):
        raise BridgeError('Unconfigured shared position')
    return value


class BridgeClient:
    def __init__(self, session: "ClientSession", base_url: str, token: str, mode="simulation"):
        if mode not in ("simulation", "physical_read_only", "physical_control"):
            raise ValueError("invalid_mode")
        self.mode = mode
        self.session = session
        self.base_url = normalize_url(base_url)
        if not isinstance(token, str) or len(token) < 32 or any(c.isspace() for c in token):
            raise ValueError("invalid_token")
        self._token = token

    async def _request(self, method: str, path: str, payload=None):
        from aiohttp import ClientError, ClientTimeout

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
        if self.mode == "physical_control":
            return validate_control_state(await self._request("GET", "/v3/state"))
        if self.mode == "physical_read_only":
            return validate_physical_state(await self._request("GET", "/v2/state"))
        return validate_state(await self._request("GET", "/v1/state"))

    async def async_move(self, target: str, position: float, *, align: bool = False):
        if self.mode == "physical_read_only":
            raise BridgeError("Physical telemetry has no movement interface")
        result = await self._request("POST", "/v3/move" if self.mode == "physical_control" else "/v1/move", {"target": target, "position": position, "align": align})
        if not isinstance(result, dict) or result.get("accepted") is not True:
            raise BridgeError("Bridge did not accept command")

    async def async_stop(self):
        if self.mode == "physical_read_only":
            raise BridgeError("Physical telemetry has no movement interface")
        await self._request("POST", "/v3/stop" if self.mode == "physical_control" else "/v1/stop", {})
