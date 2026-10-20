# Bounded motion session

Status: portable C++17 implementation and host fault tests. It joins the real
`Controller` and `MotionExecutor` through an injected I/O boundary; its test motor
is synthetic. The [C6 runtime](c6-motion-runtime.md) now instantiates it behind
empty qualification defaults and connects authenticated motion resources and
coherent worker snapshots. Commissioning and hardware qualification remain
separate work. No motor or owner device has been accessed.

Sources: [session](../../firmware/include/smart_blinds/motion_session.hpp),
[implementation](../../firmware/src/motion_session.cpp),
[fixed protocol](../../firmware/include/smart_blinds/motion_protocol.hpp).
The C6 `BenchC6Io` implements the explicit `CounterOrigin` interface and provides
`motion_observation()` to project its actual ADC/PCNT/button sample into the
portable input. This does not authorize an application to enable the adapter.

## Ownership and real evidence

One control task owns the session, controller, executor and board adapter, with
a nominal 10 ms cadence. The DTLS resource decodes and enqueues a bounded
frame; it must never drive a GPIO, feed WDI, run I2C or write flash. The inbox is
single producer/single consumer, holds four commands, and rejects overflow.
Its connection generation is assigned locally after a successful authenticated
DTLS handshake. Generations increase within a boot, are limited to 32 bits for
lock-free C6 atomics, and cannot be supplied by a request. Reconnection never
restores remote motion. An active remote session that loses its connection stops
and loses position validity. The portable [local ownership core](local-ownership.md)
does not use remote connectivity as local authority. Generations and message
sequences must not be reset in place.

`SessionInput.fast` must come from a successful, source-stamped physical sample.
`SessionInput.power` must be the result of the actual gauge/charger
[power assessor](motion-power-evidence.md), including its separate conversion-age
bounds. Zero/default or failed observations are not ready. The pack binding must
match the local reference record. A worker must publish a failed capture as
invalid immediately, replacing its last good result. Passing old good readings
after a known bus failure is not supported. The [C6 runtime](c6-motion-runtime.md) supplies the worker/publication bridge;
qualified continuity during a gauge refresh remains a separate integration gate.

The clock snapshot must be the last accepted, boot/session-bound four-timestamp
assessment with a physically qualified clock model. Retain a still-valid prior
assessment while a new exchange is in flight; do not treat a pending exchange
as fresh evidence. The session rejects stale, reversed or excessively uncertain
snapshots. It fixes one offset projection for the entire motion: requalification
may widen uncertainty or shorten permission, but cannot step trajectory time.
The model remains unqualified in the shipped C6 application.

## Command lifecycle

1. A trusted local physical-reference workflow supplies a fresh, independently
   observed count, boot, calibration revision, record ID and pack binding.
   No remote message can establish this record. The session additionally requires
   a qualified motor profile and qualified passive holding/guard behavior.
   Unknown boot, manual intervention or a fault invalidates the reference.
2. Prepare checks the common physical-height origin and target without clamping,
   source age, current clock/probe, power, connection and duration. It installs
   a new internal counter epoch, verifies parked/OFF hardware, keeps the motor
   inhibited and warms the encoder. The epoch is independent of the remote ID.
   An accepted prepare is **not** ready. A sample captured before the counter
   starts cannot arm the motor.
3. A subsequent actual count establishes the controller's referenced measurement,
   prepares its trajectory and arms the supervised motor request with inputs
   `00`. Readiness is published only after another fresh control iteration has
   applied the first checked heartbeat. That iteration still coasts.
4. Commit requires matching command, calibration, probe, connection, fresh source
   time, unexpired permission and the ready phase. The scheduled start is rounded
   upward to a common millisecond boundary; the uncertainty budget includes an
   extra millisecond for integer conversion. Prepared/committed states coast.
   A missing/late commit cannot begin motion.
5. Leases renew from authenticated **source send time**, not local receipt.
   Pack, encoder, current, fault, clock and transport checks continue each cycle.
   Completed endpoint motion enters controlled settling before the encoder is
   gated. A new command needs a larger command sequence and a new counter epoch.

The source timestamp may be at most 100 ms old including uncertainty; queued
work may wait at most 40 ms. The 300 ms lease uses the earliest possible source
time, reserving more than 20.5 ms for the next control deadline and I/O margin.
Clock uncertainty is projected over an additional 400 ms, covering a permitted
100 ms old message plus the whole lease. A newly wider bound may shorten an
outstanding lease; only a new authenticated source timestamp can extend it.
This means clock exchanges must refresh more often than the one-second absolute
clock-age limit. A proposed 400 ms refresh cadence leaves model-age headroom;
real seven-device scheduling and radio energy still need measurement.

The source sequence is monotonic within the boot, across connections. Identical
or older messages are rejected rather than executed twice. An uncertain response
requires reading status, never blind replay. `Status.last_message` is the last
ordinary message processed by the control task; the ingress also consumes STOP
and discarded message sequences, so it is not a reconnect sequence allocator.
The coordinator must retain its increasing sequence for that boot. Boot change
requires new synchronization and physical reference.

## STOP, settling and reference retention

Any raw button press during a remote session, or a valid authenticated STOP,
bypasses a full command queue. The consumer discards older queued work and
inhibits the motor before further command processing. A held button continues
to discard incoming commands. STOP does not need a valid clock or a lease to
turn an already-active motor off. Its ingress still requires the right boot,
current authenticated connection, canonical frame and a new message sequence.

Controlled settling turns motor request OFF, forces both inputs LOW, holds WDI
HIGH and keeps charging OFF. It retains the awake lock and encoder/counter, with
**no further watchdog pulses or PWM**. It requires 100 ms of unchanged count
and current below the qualified reversal-current threshold, with fresh health
samples throughout. Any count movement or higher current restarts the quiet
interval. A 500 ms total limit, missing sample, fault, I/O error or cleanup error
prevents a retained-position result. The quiet times are provisional software
thresholds, not measured stopping or holding guarantees.

Only a successful quiet interval, complete teardown and actual parked/OFF
readback yield a final count for the next command. This also requires independently qualified no-backdrive/no-slip
holding and guarded manual access; an incremental encoder cannot prove fabric
position after chain slip. Immediate fault cleanup always invalidates reference.
STOP during early encoder warmup also falls back to immediate inhibition and
reference loss because no continuously observed settling interval is available.
Unknown reset and manual intervention retain the existing reference interlock.
See the [reference/recovery comparison](2026-10-19-reference-and-recovery.md).

## Radio and application boundary

An accepted motion sets `Status.awake_required` until inhibited settling/cleanup
finishes. Its hard duration limit is 240 seconds, independently of lease refresh
and the radio-only ten-second wake window. A slower trajectory that exceeds this
limit is rejected. An application must keep the selected radio receiver and appropriate
PM locks active while that flag is true, and supply the actual awake/attached
state. Merely extending the radio-only wake timer does not satisfy this contract.
The implemented test moves for more than 15 seconds to check this distinction.

The portable session also implements [local endpoint ownership](local-ownership.md)
through the same controller/executor, with distinct internal execution epochs.
C6 applications still supply raw local STOP only: their gesture and admission
paths do not construct local endpoint intents. The [C6 runtime](c6-motion-runtime.md) wires
the authenticated callback, one owning worker and source-stamped status to this
session. Production remains disabled through empty qualification records.
Pack/clock/physical-reference commissioning and actual callback/worker timing
remain explicit application gates.

## Binary request

Exactly 80 bytes, network byte order; unknown version, kind, length, reserved
bytes and noncanonical unused fields are rejected. Signed height is micrometres
above the shared datum, not a percentage or each blind's own travel fraction.

| Offset | Bytes | Value |
|---|---:|---|
| 0 | 1 | Version `1` |
| 1 | 1 | Kind: `1` prepare, `2` commit, `3` lease, `4` STOP |
| 2 | 2 | Reserved zero |
| 4 | 4 | Calibration revision |
| 8 | 8 | Boot nonce |
| 16 | 8 | Monotonic message sequence |
| 24 | 8 | Motion command sequence |
| 32 | 8 | Accepted clock probe sequence |
| 40 | 8 | Coordinator monotonic send time, µs |
| 48 | 8 | Scheduled coordinator start, µs; prepare only |
| 56 | 8 | Signed shared origin height, µm; prepare only |
| 64 | 8 | Signed shared target height, µm; prepare only |
| 72 | 4 | Speed, µm/s; prepare only |
| 76 | 4 | Acceleration, µm/s²; prepare only |

All trajectory fields must be zero for commit/lease/STOP. STOP may omit the
calibration/probe fields, but its boot, message, command and send fields remain
nonzero. Authentication is supplied by the transport callback and is never a
payload boolean. Transport resources are described by the separate [C6 runtime](c6-motion-runtime.md);
this portable protocol does not define their URI or response encoding.

## Checks

Run the repository firmware CMake build and CTest suite. Tests cover the
actual controller/executor with a nonlinear synthetic plant, readiness ordering,
completed motion and a second counter epoch, delayed-source lease expiry,
clock-age/drift rejection, a motion beyond the radio-only wake interval, immediate
STOP with a full inbox, retained coasting counts, held STOP, malformed/old work,
unknown references, unqualified defaults and injected live health/I/O failures.
The executor tests inject every settling inhibit and teardown failure and reject
unending coast or missing evidence. The eighteen portable targets, the same
suite under ASan/UBSan, 59 native transport/clock/motion/bridge checks and pinned
C6 Wi-Fi default/bench and Thread builds pass locally. These checks are not
physical motor, RF or battery proof.
