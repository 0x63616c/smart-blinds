# Parked charger source reconciliation

The portable BQ25798 helper can reconcile an autonomous input-voltage-threshold
change after USB insertion or removal while the charger remains parked and
charging is inhibited. The [owned PD/cable runtime](pd-source-runtime.md) now
calls it through actual physical OFF and owner guards, including awake-stationary
capture. Unexpected configuration changes and ambiguous handoffs remain terminal;
this is not a charging implementation.

The policy follows [TI BQ25798 SLUSDV2C](https://www.ti.com/lit/ds/symlink/bq25798.pdf),
Table 7-17 and §§7.3.4.4–7.3.4.5: REG05 can change independently of the host image
on a cable event; automatic input detection is disabled, so the existing
100 mA current setting must remain exact. The operation does not write REG05
or infer a negotiated voltage/current from it.

## Explicit authority and lifetime

The new `park_off(ParkGuard&)` overload records the successful park's existing
boot, pack, qualification, owner and bus epoch identities. `ParkGuard::hold_off()`
must verify fresh actual settled motor OFF with no active, settling or queued
command authority. Its identity and OFF guard are checked around every
synchronous transfer. These are interfaces to real owner evidence, not defaults
that declare an unknown board safe.

Only that same live charger object can call `reconcile_parked(ParkGuard&)`.
The original `Inhibit` park and enum-only `adopt_parked()` do not grant this
authority. There is no new generation allocator. Clean cold replacement now uses
a BQ-issued immutable exact parked image, bound to the immediate successor of
the existing owner epoch and the same boot/pack/qualification/task. The old
object relinquishes authority; the new owner verifies actual OFF, history and
exact readback without rewriting configuration.

The matching `resume_off(ParkGuard&)` overload requires the same identity through
watchdog restoration. An unbound resume cannot bypass a bound park. A fresh edge,
changed image, wrong identity or lost OFF guard refuses the transition.
Ordinary existing users of the unbound API retain their current behavior.

## Operation and result

Reconciliation reads current status and clear-on-read history before inspecting
the complete parked image. It retains the first history bytes across subsequent
reads. All fields remain exact except the separately observed REG05 value:
REG06 stays `0x000A`, EN_EXTILIM remains on, REG10 stays `0x90`, and charge,
automatic input detection, HVDCP, OTG, backup and MPPT remain disabled.

Two complete image observations, intervening/final status and event reads, and
fresh physical guards must agree. A changed threshold needs a captured VBUS edge
or a changed observed VBUS-present state. Removal requires REG05=`0x24` and no
power-good assertion. A connected legal code (`0x24..0xDC`) is retained as an
**opaque OFF-monitor value**; its exact unloaded-voltage provenance is not proved.
PG alone cannot excuse a changed threshold. Poor-source history is refused.

Acceptance updates only the in-memory expected REG05 and last source observation.
Future ordinary verification compares that exact value; there is no permanent
mask. A cable event with an unchanged threshold is still reported. The returned
`ParkReconciliation` contains raw status/history, observation times, previous and
observed threshold and an event flag. It has no `SourceEvidence` or charge grant.
The original voltage enum remains a selected profile label, never a measured
contract. The separate current-policy monitor cannot feed this enum into the
legacy exact-voltage assessment or grant charging permission.

Chatter or an incoherent observation fails terminally. There is no retry loop,
implicit configure, watchdog/POR recovery or revival of a failed object/epoch.
First-cause diagnostics and a separate inhibit failure survive later calls.
The existing 10 ms adapter transfer limit, 750 ms total operation ceiling and
250 ms OFF-observation limit remain unchanged. There are no changes to gauge
freshness, control deadlines, command floors or physical qualification defaults.

Only after accepted reconciliation may bound resume restore REG10=`0x93`.
It checks the source and history before and after that write. Reconciliation
itself performs no writes. Neither operation enables charging or the motor.

## Verification and remaining integration

`charger_source_tests` uses an independent stateful register fake with autonomous
plug/unplug effects and first-read-clear history. It covers exact fields,
same-threshold events, absent edge evidence, every read failing, identity/OFF
loss, late faults, clock/deadline boundaries, bound park and resume, and original
first-cause retention. Existing charger and runtime tests remain applicable.

The [source-bound checkpoint](charger-source-checkpoint.json) passed all 22 host targets on Clang and Linux GCC,
three focused ASan/UBSan targets, six restored-bug controls, and actual pinned
C6 default/bench builds. That historical helper-only checkpoint did not instantiate
a `ParkGuard`; the newer owned-runtime checkpoint does so behind the unchanged
empty qualification defaults. No hardware I²C, USB event, timing, charging or
power measurement has been performed.

The newer runtime closes old readers, retires the actual bus epoch and adopts
the exact descriptor only in its immediate successor. It reconciles stationary
changes before normal capture, preserves STOP priority and independent status,
and holds PM until sensor closure. Source-only service does not renew gauge
continuity or expired commands. Complete charging and informational telemetry
remain separate implementation work.
