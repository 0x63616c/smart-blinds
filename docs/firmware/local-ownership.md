# Local execution and ownership

Status: implemented portable C++17 core, exercised with injected I/O and a
synthetic motor. The C6 applications still accept **raw local STOP only**.
Their credential/admission, gesture, physical qualification and reference paths
are unchanged; this checkpoint cannot make a physical tap start a motor.
All shipped qualification records remain empty.

The implementation extends the existing `MotionSession`, `Controller` and
`MotionExecutor`. There is one control task and one executor, never competing
local and remote actuator instances.

## Three independent identities

| Identity | Allocated by | Purpose |
|---|---|---|
| Remote message and command numbers | Authenticated coordinator | Existing per-boot replay floors and exact 80-byte protocol |
| Local gesture number | Future trusted local gesture recognizer | One-use intent; rejected/cold gestures remain consumed |
| Execution epoch | Owning session | PCNT origin, executor and watchdog heartbeat identity |

The internal epoch begins at zero each boot and increments before any start
readback/setup attempt. Failed or uncertain starts consume it. It never wraps;
exhaustion fails closed. External command or gesture numbers cannot set it.
For example, remote command `UINT64_MAX` may use epoch 1 and a subsequent local
move epoch 2. Local travel leaves the remote command/message floors untouched.
Unknown reboot still requires new physical reference; an epoch is not a saved
position or permission to resume.

`ownership()` provides internal owner, last owner, execution epoch, last gesture
and last local result. `Owner::none` means no active execution; last owner still
labels its outcome. The last local result may describe a refused later gesture,
while the session's completed/STOP outcome remains available. Existing remote
JSON fields and request bytes are unchanged. Local work has `command=0` and
`ready=false`, so it cannot impersonate a coordinator job. This internal status
is not a newly commissioned remote local-control interface.

## Local admission

The control owner may supply one `LocalIntent` to `cycle()`: Up/Down endpoint,
boot, monotonic gesture number, physical-reference record, calibration revision,
original issue time and expiration. It must arrive within 40 ms, have a lifetime
of at most 100 ms and still be unexpired. The pack must match the reference.
Both default qualification and unknown reference refuse it.

The operation requires the same fresh physical evidence as remote work:
source-stamped fast observation/current/fault state, qualified pack and charger
assessment, current limits, passive holding and guarded manual access.
Gauge/temperature conversion-age rules are unchanged. The core does not invent
a clock model, lease, source timestamp or a prepared remote command.

A cold/stale/invalid tap is consumed and refused. It is not stored until warmup
finishes; a new gesture is required. This preserves the current conservative
2.8–4 s cold/unproven-idle power warmup. Prompt normal button start still needs
the separately reviewed continuity path and real wake-to-motion measurements.

Before a new execution the port must synchronously read back parked hardware:
motor, charging and encoder power OFF; PWM and counter stopped; WDI HIGH; no
executor awake hold. The default `MotionIo::parked_off()` refuses unsupported
ports. `BenchC6Io` supplies its existing pad/peripheral readback. Failed or slow
readback performs every OFF operation and latches a fault, including failure
before the first encoder setup. A later successful read cannot repair the fault.

If the independently referenced or previously settled coordinate already lies
within the existing 1 mm endpoint tolerance, the core only verifies OFF and
returns finished. It keeps that exact coordinate, with no epoch allocation,
encoder restart, motor arming or heartbeat. This relies on the same already
required qualified holding evidence; saved counts alone remain insufficient.

Otherwise the new epoch opens encoder sensing, waits for the configured encoder
startup, obtains a new valid count and arms with inputs `00`. A checked heartbeat
is applied while coasting. Only afterward does `Controller.local_move()` start
the endpoint trajectory on the actual local monotonic clock.

The local deadline is the computed trajectory duration plus the existing 2.5 s
startup/settling allowance, capped at 240 s total. It never renews. Each active
session cycle must advance and remain within 20 ms; executor sample, output and
heartbeat deadlines remain unchanged. No late/catch-up pulse is generated.
The controller stops local travel upon entering the existing endpoint tolerance
instead of driving until nominal trajectory end. Remote synchronized timing is
unchanged. Range, current, driver, power and timing checks still precede local
endpoint completion.

## Arbitration and handoff

- Physical/global faults and manual reference loss inhibit either owner and
  invalidate reference. They cannot be cleared by a gesture, network reconnect,
  STOP or a fresh-looking sample.
- Raw STOP, including either/both buttons, overrides ordinary commands. A
  coincident gesture is consumed, so release cannot restart. First-iteration
  raw STOP may bypass ADC for immediate inhibition, as before; the next settling
  iteration requires complete fresh observations.
- A valid new local gesture during preparation, movement or settling means
  STOP, not takeover. Early warmup STOP deliberately loses reference if there
  was not yet a continuously observed settling interval.
- A local intent drains the already queued remote backlog. Discarded packets
  remain consumed by the producer's replay floor. Remote prepare/commit/lease
  during local execution cannot take ownership or change its local deadline.
  Local OFF release drains the remaining backlog again. A later-published
  prepare must carry an original ingress receipt time strictly after that OFF
  handoff; delayed publication of a competing earlier frame cannot acquire the
  newly idle executor.
- An authenticated remote STOP can inhibit a local move, without acquiring
  ownership or needing a remote clock/lease.
- AP/DTLS/clock loss cancels a remote owner. Those network-only conditions do not
  cancel a healthy local owner in this portable core. A hardware/global fault
  always cancels both.

Both successful completion and controlled STOP retain ownership during inhibited
settling: motor OFF, no further PWM/heartbeat, counter and encoder retained.
The existing 100 ms quiet observation and 500 ms settling ceiling apply.
Successful final teardown is followed by another actual OFF readback. Only then
is the exact final observed count retained and ownership released. Cleanup or
readback failure prevents a new local or remote owner. No target coordinate is
substituted for an observed count.

## Remaining C6 integration

The current C6 runtime's `transport_fault()` is still a global fail-off path,
and its admission includes network credentials/clock qualification. No local
endpoint is connected to it here. Before offline physical buttons can execute,
a separate checkpoint must:

1. Split network authority loss from physical/global failure at the runtime and
   power-lock boundaries, preserving ambiguous failures as global faults.
2. Admit independently qualified local hardware without requiring Wi-Fi
   credentials or a remote clock model.
3. Add a debounced, one-use gesture recognizer and visible refusal/warming
   feedback, with raw STOP always preceding normal gesture handling.
4. Bind real board/pack/holding/calibration/reference records and prove worker,
   I/O and wake timing on hardware. No records have been manufactured for tests.

The known earlier Thread-labelled seven-peer host timing failure remains a
separate unresolved investigation. These deterministic tests do not establish
its first-fault cause or real radio, battery, motor or fabric performance.

## Checks

`local_session_tests` covers endpoint travel in both directions, a satisfied
endpoint without arming, out-of-range rejection, a near-240-second offline move,
both ownership transitions, largest remote ID, nonwrapping epoch exhaustion,
failed start consumption, stale/cold/bad-bound intents, no delayed start,
STOP during each startup state and settling, queue conflicts, network-loss
scope, simultaneous physical/global faults and missing initial/final OFF proof.
It rejects pre-handoff delayed publication and exact-release timestamps after
both settling and the already-satisfied endpoint no-op, including release at
monotonic time zero. Initial OFF readback must not reverse the session's clock.
A cadence failure
retains the first executor clock fault even when cleanup subsequently discovers
that the hardware-heartbeat interval has also expired.
The shared remote-session fixture exercises the same executor and synthetic
plant. Run the normal firmware CMake build and CTest suite; this checkpoint has
18 host targets. All eighteen also pass ASan/UBSan; the native transport, clock,
motion and group-bridge suite passes 59 checks. The default/bench Wi-Fi motion
and Thread applications cross-build with the pinned ESP-IDF 5.5.4 image. These
checks are software and build evidence only.
