# Battery monitoring in the control runtime

The experimental C6 motion runtime now owns the joint charger/gauge monitor.
Control and status take separate fresh snapshots; raw STOP and fast motor I/O
precede the control snapshot. The default application still supplies no physical
qualification records and cannot enable motor I/O. Charging remains inhibited.

## Normal idle and wake

The control task first reports fresh physical motor OFF. Closing its sensing
request immediately withdraws published readings. The sensor task completes any
outstanding synchronous transfer, checks motor and charge inhibition, reads the
charger's fault and temperature history, and verifies its complete configuration.
It then disables only the charger watchdog while OFF and verifies the result.
Control keeps its power locks until that owner acknowledges the matching closed
request. Radio parking uses the same acknowledgment.

The whole parked interval survives unrelated radio and status wakes. A real
sensing wake verifies the parked charger before writing, then restores and
verifies the existing two-second watchdog. A qualified short sleep retains the
gauge's conversion history, but still requires a complete new guarded acquisition.
An expired ticket or incomplete prior warmup creates a new monitoring identity
and repeats the full cold conversion-history warmup, roughly 2.8–4 seconds.
Ordinary hours-long idle therefore does not require a reboot.

One fixed session slot holds the immutable mailbox and adapters. Short reader
pins prevent destruction while a snapshot is being copied. Replacement first
withdraws the selector and retires the epoch, then waits boundedly for readers
before owner-only handle removal and reconstruction. A timeout or real fault
keeps the runtime failed; cold reconstruction cannot clear it. No bus access,
clock call, formatting or wait occurs under the selector gate.

The charger register changes are explicit: active `REG10=0x93`, OFF park
`REG10=0x90`, and active watchdog service `REG10=0x9B` with self-clearing reset.
Watchdog expiry would reset other charger settings, so it is not treated as
ordinary sleep. The register behavior is documented in
[TI's BQ25798 datasheet](https://www.ti.com/lit/ds/symlink/bq25798.pdf),
§7.4.1 and Tables 7-20, 7-26, 7-27 and 7-32 through 7-34.

## Verification

The [source-bound record](sensor-runtime-checkpoint.json) identifies the tested
sources, immutable SDK/dependency versions and local evidence hashes:

- All 21 host targets passed with native Clang and Linux GCC; a fresh independent
  parent build also passed all 21.
- Three focused targets passed ASan/UBSan; two passed ThreadSanitizer.
- Five restored bugs were rejected: posting a sensor request before fresh OFF,
  releasing power locks before sensor closure, retaining an expired monitoring
  session, ignoring active reader pins, and leaving the watchdog disabled on wake.
- Actual pinned C6 default and bench builds passed. The bench build compiles both
  motion and gauge attachment branches without supplying physical records.

The runtime fixture runs the actual control/sensor functions on separate host
threads through fake SDK and peripheral seams. It covers eight-hour idle, fresh
cold warmup, independent status and blocked charger/gauge operations while STOP
remains runnable and sleep is denied. An initial sanitizer run exposed the
request-before-OFF ordering bug; the final code corrects the order and a
deterministic scheduling test rejects the original behavior.

These results are software and compile evidence. C6 scheduling, interrupt-mask
duration, actual OFF readback, I²C timing, current consumption and conversion
continuity remain unmeasured. The existing Thread group timing investigation
is separate and remains unresolved.

The subsequent input-limit audit corrected an independent board/profile
inconsistency: an exact 1.5 A request exceeded the board's low startup clamp.
The OFF-only profile now requests 100 mA and retains external limiting.
Clamp-aware charger and runtime fakes reject the prior source; the final
21-target suites, focused sanitizers and both C6 builds pass. See
[charger configuration](charger-configuration.md) for the circuit and limits.

## Remaining behavior

The owned PD/cable checkpoint now integrates shared-bus source monitoring,
source-only parked service, guarded awake-stationary REG05 reconciliation and
exact parked-image handoff across cold owner replacement. See
[owned USB source monitoring](pd-source-runtime.md) for the implemented boundaries,
5 s idle cadence and unresolved charging/startup gates. Unexpected configuration
changes, chatter and faults still cannot revive a retired owner. Legacy
watchdog-expiry recovery remains absent.

Physical qualification, pack commissioning, local endpoint gestures, persistent
calibration, homing, charge permission, live Home Assistant transport binding and
firmware update/recovery remain unfinished. No unit has been flashed or tested.
