# Explicit group-to-DTLS adapter

This library connects the existing physical-height group coordinator to the explicit
qualified-motion transport. It has no discovery, network listener, Home Assistant
service, automatic commissioning, reconnect, or movement replay. The existing HA
application remains simulation-only and both C6 application defaults remain inhibited.

**Current evidence is localhost correctness with synthetic motors, power and references.**
The current JSON polling cadence exceeds the intended 802.15.4 radio budget. Do not
use this cadence as a Thread deployment or battery-life claim.

## Ownership and authority

- The caller supplies 1–8 `Selection` records from an independently established
  commissioning process: exact device identity, boot, calibration, reachable physical
  range, motion limits and per-device secret. `commissioned` defaults false; this
  library cannot create a physical qualification or reference. Keys remain in memory.
- The caller owns `Group` and calls `step()` at a bounded cadence (tests use 5 ms).
  A single worker thread owns each `MotionSession`; no two threads access its native
  DTLS context. The worker uses four ordinary mailbox slots, one replaceable unsent
  lease and a separate priority STOP. The 32-slot receipt queue cannot silently drop
  an error/receipt: overflow latches failure and causes a group abort.
- Preflight opens authenticated sessions in parallel, explicitly wakes and qualifies
  clocks, and waits for all peers' fresh idle/reference/power evidence. Only then is
  a group trajectory created. A queue acknowledgement is never readiness. A fresh
  worker `ready` sample authorizes the coordinator's preparation acknowledgement;
  a later processed commit sample separately authorizes its commit acknowledgement.
- After preflight, the explicit client deadline is shortened to 40 ms. Ordinary
  source timestamps are preserved from the original coordinator envelope, including
  STOP. A newly detected local worker failure may generate its own new STOP intent.
  There are no late catch-up leases, automatic retries or implicit reconnects.
- Clock refresh waits for the last queued motion message to be consumed before
  replacing its probe. Otherwise a refresh could invalidate an earlier queued lease.
- Telemetry remains tied to device source time and current boot. Its uncertainty
  interval is rounded outward to integer milliseconds; rounding must still satisfy
  the coordinator's 10 ms uncertainty limit. A receipt timestamp never replaces it.
  Reference, power or qualification loss revokes preflight immediately.
- The group continues to supervise `settling`. Completion requires a fresh,
  matching-command `finished` outcome in `idle`, at the common target. Mere queue
  acceptance, idle state, STOP receipt or cached target position is insufficient.
  A late ordinary request cannot erase the portable session's terminal outcome;
  it still consumes its replay sequence. New valid preparation replaces that outcome.
  Faults remain dominant. Definitive completed peers stop receiving wire leases.

## Durable sequence reservation

`Ledger(path, create=True)` and `enroll(...)` are explicit administrative operations,
not part of automatic connection setup. Enrolment requires independently trusted
command/message floors. The device's `last_message` report is insufficient: it does
not expose STOP/discarded inbox high-water state. Existing enrolments cannot be overwritten.

A local SQLite transaction with EXTRA synchronous durability reserves one command and
4096 wire message IDs per peer atomically **before any preparation**. A process-level
exclusive lock prevents concurrent ledger owners. EXTRA also syncs the journal directory
after deletion ([SQLite durability documentation](https://www.sqlite.org/pragma.html#pragma_synchronous));
mode readback is required and macOS fullfsync is requested. No disk transaction runs on the
active control path. Ordinary messages use the range in order; the highest ID is
reserved for a single STOP attempt, even if delivery is uncertain. A process crash
burns the entire reserved range. Restarting creates a new job; it never replays a
saved target. The database contains counters and a hash of nonsecret commissioning
identity, not keys, commands or trajectories.

Use a local filesystem with working locks/fsync. This is not an anti-rollback store:
a lost database, restored backup, unknown boot, changed calibration/commissioning
identity or exhausted counter requires explicit recovery. Do not infer recovery
from a device report or set the floor back to zero.

## Physical coordinate precision

The wire carries integer micrometres. The bridge normalizes the shared target once
using the common reachable range and requested group percentage. Shared origins
are also normalized once per identical value. Rounding is nearest micrometre,
with exact decimal half ties going to the even integer, at most 0.5 µm error.
The coordinator's stored geometry and every emitted command use that same result.
Explicit alignment jobs may retain different origins, but keep one target.

Every normalized origin and target is checked against every relevant member's
reachable range and the 5 mm start tolerance; an out-of-range boundary is rejected,
never individually clamped. Speed and acceleration must be represented exactly.
This representation precision says nothing about the physical 5 mm alignment goal.

## Calling contract

Use `Group(explicit_selections, existing_ledger, native_library)` as a context
manager, call `start(percent)`, then call `step()` until complete/aborted. Creation
reserves its sequence range; each Group is single-use. `abort()` requests all-peer
STOP. `close()` also aborts an unfinished job and bounds worker teardown. Inspect
worker failures and `stop_confirmed` separately; an uncertain transport outcome is
never reported as confirmed physical OFF. Independent firmware leases and hardware
cutoffs remain necessary if the host process disappears.

This is deliberately a library API. No command line tool or HA service installs or
chooses commissioning records on the owner's behalf.

## Tests

Build the existing native test library as documented in
[thread_transport](../thread_transport/README.md), including its explicit scoped
CCM8 policy exception and test-only fixture option. Then run from the repository root:

```sh
SB_THREAD_LIBRARY="$PWD/work/thread-transport-build/libsb_thread.dylib" \
  python3 -m unittest integrations.thread_bridge.test_bridge \
  integrations.thread_bridge.test_group_dtls -v
```

Use `libsb_thread.so` on Linux. Tests generate disposable keys, bind to IPv6 localhost,
and use temporary ledgers. They cover atomic/crash-safe reservations, source and unit
mapping, bounded queues, clock/command ordering, seven different calibration maps
reaching one physical height, unavailable readiness, failed power, worker loss,
uncertain commit delivery and explicit next-job sequence continuity. These fixtures
are excluded from the production library build.

The test prints application-body byte counts and host request durations. Those counts
exclude DTLS/CoAP/UDP/IPv6/MAC headers, acknowledgement/retry overhead and mesh hops.
The native fixture retains first-fault timing; a deliberate 30 ms control stall
must fail closed at the unchanged 20 ms update bound. Positive cases can fail under
a real host scheduling stall and never retry or waive that failure.
See the [checkpoint evidence](../../docs/firmware/thread-group-bridge.md) for limits.
