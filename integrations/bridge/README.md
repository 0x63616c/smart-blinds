# Seven-blind simulator bridge

This is a runnable software fixture. It serves seven virtual blinds to the real Home Assistant custom component and exercises the shared-height coordinator over authenticated serialized packets. It does not use a radio, control GPIO, model a physical motor or access the user's Home Assistant installation. Battery values are deliberately synthetic fixtures (80%, 79%, …), not estimates of the proposed pack's runtime.

From the repository root, create a token once in ignored local storage and start the bridge:

```sh
python3 - <<'PY'
import os, secrets
from pathlib import Path
Path('work').mkdir(exist_ok=True)
fd = os.open('work/bridge-token', os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
with os.fdopen(fd, 'w') as f:
    f.write(secrets.token_urlsafe(32))
PY
python3 -m integrations.bridge.server --token-file work/bridge-token
```

The server binds only `127.0.0.1:8765`. The token is read from a file and is not printed or put in the process arguments. Keep that file outside Git. For HA Core on the same host/network namespace, install the [custom component](../home_assistant/README.md) and enter the local URL and token in its configuration form. A separate HA container's localhost is different; deployment packaging for HA OS/add-ons, remote HTTPS and the physical Thread bridge is still work to do. Do not expose this HTTP fixture to the LAN.

The HTTP surface accepts a bearer token and returns `Cache-Control: no-store`:

| Endpoint | Payload / result |
|---|---|
| `GET /v1/state` | Measured simulator state, `schema_version: 1`, `mode: simulation`, stable bridge/member IDs |
| `POST /v1/move` | Exactly `target` (`room` or `blind-1`…`blind-7`), `position` (0…100), `align` (boolean) |
| `POST /v1/stop` | Empty object; aborts the active group or individual job |

For `room`, 0/100 are the intersection of every member's calibrated physical range. Fifty percent sends all seven virtual bottom edges to 1030 mm in this fixture, although their individual cover percentages differ. A normal group move rejects unequal starting levels. `align: true` is the explicit rejoin operation; individual endpoint commands use that blind's own full range. Movement requests are not queued or retried. Restart creates fresh random device boots and sessions and never restores a move. Only one job is active at once.

The bridge ticks independently of HA's one-second display refresh. All-device preparation, commit acknowledgment and short leases belong to the coordinator, not HA polling. The synchronous fixture emits separate authenticated queued and prepared replies; it does not model actual C6 queue delay. Prepared nodes require the same source-based 300 ms lease as armed/moving nodes, and queue receipt never replaces source telemetry. Tests cover an offline member: it stops on lease expiry, the coordinator aborts peers, and reconnecting does not restart motion. The simulator's ideal motion model is separate from the portable C++ controller and does not prove braking, load, tracking accuracy or RF timing.

`auth.py` implements a bounded HMAC-SHA256 packet envelope. It authenticates identity, direction, fresh session, boot, sequence and send time; rejects corruption, reflection, replay, expired packets and non-finite JSON; and preserves uint64 values with integer parsing. It **does not encrypt**, provision devices, perform a key exchange or estimate clocks. Simulator endpoints share a clock and receive fresh random keys/sessions in memory. The production handshake, standard secure transport choice, key storage, rotation and strict per-message C6 decoder remain open. [Transport boundaries and Thread path](../../docs/firmware/thread-transport-plan.md)

Run the dependency-free bridge scenarios with:

```sh
python3 -m unittest discover -s integrations/bridge -p 'test_*.py' -v
```

No fabricated battery, reference or availability state from this fixture is accepted as a physical device: the current HA component explicitly accepts `mode: simulation` only. A hardware release must implement and review its real state adapter before changing that guard.
