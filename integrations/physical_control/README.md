# Persistent physical control bridge

This explicitly selected bridge adds a runnable Home Assistant physical-control
path. One actor owns each device's DTLS handle for its lifetime: informational
telemetry → existing qualified preflight → the existing Group/Worker motion
engine → settling → authenticated physical OFF handoff → telemetry. It does not
create physical qualifications, calibration, keys, reference records or ledger
entries. Empty records keep movement unavailable. The simulator and physical
read-only services retain their own explicit modes and native allowlists.

Start the service only for an existing commissioned selection and trusted local
ledger. It must not run beside another bridge for those same endpoints. Literal
IP aliases are canonicalized to prevent duplicate owners inside this process;
there is no cross-process endpoint lock or automatic discovery.

```sh
python -m integrations.physical_control.server --pairings /absolute/pairings.json \
  --selections /absolute/existing-selections.json --ledger /absolute/existing-ledger.db \
  --token-file /absolute/private-token --library /absolute/libsb_thread.so
```

Pairing format remains that of `physical_bridge`. The optional selection file is
`{"version":1,"devices":[...]}`; each member names `id`, lower-case 16-digit `boot`,
`calibration`, `low_um`, `high_um`, `max_speed_um_s`, `max_accel_um_s2`,
`commissioning_id`, and `commissioned`. Values must come from existing trusted
commissioning, never from this README or device telemetry. Omit selections/ledger
for diagnostics-only unavailable controls. Ledger creation/enrollment is deliberate
and is not a service feature; a lost ledger is not reconstructed from the device.

Select **Physical blinds (existing commissioned bridge)** explicitly in HA. It
pins schema 3 and `/v3/state`, `/v3/move`, `/v3/stop`. HTTP binds loopback only;
any separate LAN deployment still needs the existing authenticated HTTPS/tunnel
boundary. `202 accepted/queued` means that a bounded intent was stored, not that
preflight succeeded or a motor moved. One group or individual job is admitted at
a time; further moves reject as busy. STOP cancels pending ordinary intent and is
published directly to each active worker before further coordinator work.

## Authority and lifetime

- The existing `Ledger` commits 4,096 message IDs per peer before starting a job.
  Failed preflight burns its range; STOP consumes the highest reserved ID.
  The next explicit reservation only increases command/message floors. No
  uncertain request is retried; a failed native handle is closed, not reconnected.
- A per-job facade uses the existing Worker command/clock/lease implementation.
  Closing it cannot dispose of another thread's native handle. The actor alone
  creates, uses and closes that handle. Diagnostics are suppressed during the job.
- Original coordinator timestamps, source-qualified reports, common physical
  range, all-peer readiness, 40 ms active exchange deadline, 100 ms message/status
  supervision, 300 ms source lease and physical OFF age remain unchanged.
- A definitive settling outcome suppresses late leases but does not replace
  settling's fresh power/reference/clock evidence. Intentional sensor closure at
  terminal idle is handled by the existing `/v1/handoff` endpoint. Its nonce,
  boot, terminal command, received-message floor, actual height and physical OFF
  observation must match. Completion age is bounded conservatively from the
  original device interval, full exchange RTT and existing clock-rate/stamp bounds;
  this is completion evidence, never a new qualified motion clock.
- Reusing the connection for another job requires a fresh matching OFF handoff
  and a new durably reserved range. Every new job repeats ordinary preflight.
  A refused wake/cooldown is reported as an aborted intent, never queued to move
  later automatically. The C6's existing wake/cooldown policy is unchanged.
- Cached battery/source/position ages retain their original source stamps. HTTP
  only copies state. A configured control is not a device qualification, and
  retained position is not preflight authority. Unqualified/faulted device
  evidence still rejects the actual move. Idle telemetry follows a complete
  exchange by fifteen seconds; it does not acquire the gauge or renew a lease.

STOP cannot interrupt an exchange already in progress; it prevents the next
ordinary call and waits at most that bounded exchange (1 second in idle/preflight,
40 ms active). Native failure still leaves the device's independent lease and
hardware safety boundaries in force. No success or confirmed OFF is synthesized
from the timeout. A failed actor remains unavailable until explicit service
recovery; unattended reconnection is outside this checkpoint.

## Evidence and limits

This integration candidate separates application ownership checks from execution
and physical qualification. Default records still leave movement unavailable.
Deterministic tests cover shared physical coordinates, reference loss, copied
publication before validation time, durable ranges, STOP priority and terminal
OFF evidence. They are not motor or network timing tests.

The separately named [scripted contract fixture](../thread_transport/CONTRACT_PEER.md)
uses actual HA, authenticated HTTP, the production actor/Group/ledger/client and
real localhost DTLS. Explicit per-command synthetic READY, terminal coordinate
and OFF observations exercise one-owner handoff without instantiating or replacing
the MotionExecutor. Seven receiving peers with different ranges check one common
52 mm target at group55%, common speed/start, missing-READY abort and wrong-height
refusal. These are synthetic application observations, not physical measurements.

The original seven-peer positive campaign faulted before start. Retained evidence
narrows the first fault to the active clock guard but does not identify its exact
subpredicate or cause. A later instrumented campaign passed; it is not a fix or
reliable seven-peer timing qualification. The existing strict real-wall-clock
MotionSession/Executor campaign also retains unresolved heartbeat/I/O timing
failures and a precondition wait. The later instrumented strict run records 894/1,031 µs PWM calls and
188/4,331 µs heartbeat acknowledgments against the unchanged 100 µs bounds;
these are host qualification limits, not a demonstrated C6 or actor fix.
Its tests, names, firmware and 100 µs/20 ms
execution bounds remain unchanged by the scripted fixture. Neither test suite
replaces a required check or establishes a passing release gate.

The candidate's evidence hook uses a read-only connection load. Worker call
history is copied before cleanup so later STOP/handoff calls cannot mutate the
captured list; other independently copied fields are not claimed to be an atomic
whole-system snapshot. Source ages and all network/control limits remain intact.

Physical I2C, sensor closure and AP power management still need their owning C6
and hardware tests. The telemetry fixture reports battery/source absent, not
fabricated charge measurements. Loopback traffic establishes neither radio
capacity/latency, motor accuracy, pack life, commissioning nor real-device
interoperability. No device was flashed and no owner's HA configuration changed.
