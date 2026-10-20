# Owned USB source monitor and cable lifecycle

The experimental C6 motion runtime now services STUSB4500 status on the **same
sensor task and bus as the charger and gauge**. It reconciles normal stable USB
insertion/removal while parked or awake and physically stopped. Motor and charge
qualification defaults remain empty. This is compiled and host-tested source;
there has been no hardware access, flashing, cable test or measured battery life.

The board revision uses direct always-on 3.3 V to STUSB VSYS, shared SDA/SCL,
and STUSB ALERT joined to BQ INT on GPIO17 with an external 10 kΩ pull-up. The
firmware's existing `Pins::charger_int` is this shared `power_interrupt_n` signal.
ST is 0x28, BQ is 0x6B and MAX is 0x36/0x0B. No new GPIO or active IC is required.
Factory pogo use must hold the MCU reset and all enables inhibited; it is no
longer an isolated second bus. Supply, reverse-current, unpowered-pack bus
behavior, rise time and interrupt/wake timing remain physical qualification gates.
The supply/dual-rail basis is [ST DS12499 Rev8](https://www.st.com/resource/en/datasheet/stusb4500.pdf),
§§2.2,3.3–3.4 and the MCU application diagrams.

## What is actually established

`pd::Monitor` and `c6::PdMonitor` implement a status monitor **with explicit alert
setup**, not an unrestricted read-only driver. The sole data write is register
0x0C: unmask documented port/monitor/fault/protocol bits 6,5,4,1 while retaining
all other bits. Clear-on-read fault evidence is inspected before that write and
again afterward; mask readback is mandatory. There are no PDO, NVM, command,
forced-reset, discharge or RX-buffer write paths. The C6 adapter enforces its
address/length allowlist, owner and nonwrapping bus epoch before and after each
synchronous transfer, with the existing 10 ms transfer timeout. Wrong-task
teardown cannot remove a handle.

The source is [ST UM2650 Rev2](https://github.com/usb-c/STUSB4500/blob/55d1109e7ef0cffc2ffef2494095d23306594601/Doc/User_manuals/um2650-the-stusb4500-software-programing-guide-stmicroelectronics_v2.pdf),
§§1.7–1.8,3.6–3.17,3.25 and3.60–3.76. Its documented registers take precedence over
old upstream C header comments: ALERT0x0B is an aggregate read, bit7 is reserved,
and hard-reset evidence comes from PD_TYPEC0x14/PRT0x16. The monitor never uses
undocumented0x21 or the short-lived Source_Capabilities RX buffer.

A current-qualified report requires:

- An explicitly supplied factory record whose board binding must be enforced
  by the trusted local provisioner. The runtime checks boot and qualification;
  it has no independent expected board identity. The record includes verified
  NVM/above-5V gate, REQ_SRC_CURRENT=0, source path, exact accepted live PDO words
  and supported silicon ID. The admission path remains unfinished; both
  application defaults are empty.
- Three fixed sink PDOs: 5 V/1.5 A,9 V/2.5 A,15 V/2.5 A, with the approved USB
  flags; live policy observed twice and matching the approved record exactly.
- Attached sink/UFP/Type-C state, VBUS_READY+VALID_SNK without vSafe0, PE_READY
  before and after RDO inspection, and RDO operating current exactly2.5 A,
  maximum current at least that, no capability mismatch, GiveBack or reserved
  bits. RDO object position is a **source** PDO index; it is not a local PDO index.
- Stable observations and no attach/monitor/reset/message history in that
  acquisition, then at least500 ms of quiet qualification. The complete
  operation is bounded to100 ms, and evidence expires250 ms from its original
  start, not its publication or receipt time. All fields must match the sole
  completed report; a caller cannot relabel or restamp it.

This proves constrained **current policy**, not an exact negotiated voltage or
permission to charge. BQ voltage measurements must independently establish a
safe operating window in a later charging policy. BQ PG/ADC/REG05 never create a
PD contract. The old `charger::SourceEvidence`/`assess()` exact-voltage evaluation
is not fed by this new monitor. No CE/EN_CHG enable or external-limit lifting
exists here: REG06 remains100 mA and EN_EXTILIM remains enabled.

A PD hardware-reset/attach event revokes current evidence and requires fresh
qualification. Unexpected silicon/policy/mask change, bus error, clock failure,
operation overrun or overflow is terminal for that monitor. First detected fault
reason, original timestamp and clear-on-read bytes survive later calls. Clean
sensor-owner replacement adopts the previously verified alert mask without
rewriting it: a POR restoring the mask in that gap cannot be silently repaired.

## Actual runtime handoff

The existing control owner alone configures GPIO/interrupts and owns PM locks.
The ISR only advances an atomic, nonwrapping source-event generation and wakes
control. GPIO17 is ambiguous: **both** PD and charger owners must be serviced.
Raw button STOP and fast motor sampling still precede any power snapshot.

While parked, an IRQ or the5 s fallback requests source-only service. Control
holds its two PM locks, publishes fresh actual OFF and a bounded request, and
waits for sensor closure. The sensor checks the bound parked charger and PD,
then acknowledges the serviced generation only after both histories are read
and the shared line clears. A new event invalidates any older source snapshot
immediately; in-progress polling, bus retirement and qualification loss also
invalidate it. A normal reasserted PD interrupt can be drained without turning
the first reassertion into a fault. A line remaining asserted for500 ms after
first observation fails; events do not renew that deadline. Each synchronous
operation retains its own bound, so fault detection can include the final
bounded operation. A stuck/failed bus retains PM locks and never grants OFF
closure or motion readiness.

Source-only service **does not resume/read the gauge, extend the whole parked
interval or renew gauge evidence**. It runs at the same parked cadence on
battery or attached USB because charging is inhibited in both cases. Active
monitoring retains the existing100 ms sensor cadence. Status reads are copies
and cannot acquire/release PM or restart acquisition.

The existing exact motion JSON schema is unchanged; adding extra fields would
break the strict Python motion client. `source_status()` currently supplies an
internal, source-stamped queue snapshot with event and owner-epoch checks.
Informational parked battery/source telemetry and a versioned network exposure
are subsequent work. A source snapshot is not an output-enable capability.

The BQ lifecycle is now wired to real guards. Awake stationary acquisition uses
the same exact-image/history predicate as parked reconciliation **before** the
ordinary watchdog service; unexplained changes cannot be repaired after a
published failure. Guards bind boot, pack, qualification, bus epoch and sensor
task identity and compare fresh physical OFF against ingress/revocation state
around every transfer. REG05 is retained as an opaque observed code, never
converted to contract voltage. All other protections stay exact.

For a clean cold gauge-session replacement, the old BQ object issues an immutable
exact parked-image descriptor and relinquishes authority. After old readers are
closed, the actual mailbox retirement advances the existing bus epoch. The new
object requires exactly its immediate successor, the same other identities,
physical OFF, retained history and exact readback; it performs no configuration
rewrite. Failed owners cannot issue a descriptor or revive. Cable chatter across
that narrow handoff is refused rather than guessed. Before warm sensing resumes,
the unchanged2 s charger watchdog is restored and verified. Actual source
discontinuity outside a settled OFF boundary requests the global STOP path;
ordinary PD message receipt alone does not cancel motion. Unexpected active
configuration drift still faults through the joint mailbox.

## Timing and energy limits

A healthy parked pass performs56 BQ reads/95 payload bytes plus14 PD reads/75
payload bytes. At100 kHz, counting address-write, pointer, repeated-start
address-read and ACK bits gives a **34.2 ms wire-clock floor** for70 reads. This
excludes clock stretching, START/STOP timing, SDK scheduling, guards, ISR and PM
handoff; it is not measured awake duration. The independent BQ observation bound
is250 ms and PD observation bound100 ms. Those ceilings are refusal limits,
not expected performance. First setup/cold restart has separate guarded setup
work; a fault may retain locks indefinitely pending recovery.

Using the repository's illustrative model (86.4 Wh usable,10.8 V nominal,
305.8 s/day at1.5 A motor branch,20 s preflight,150 mA awake3.3 V rail at90%
efficiency and0.5 mA total pack idle),5 s fallback sensitivity is:

| Additional awake time per service | Estimated days |
|---|---:|
| None |55.56|
|34.2 ms wire floor only |52.55|
|50 ms assumption |51.27|
|100 ms assumption |47.59|
|350 ms refusal-budget sensitivity |35.03|

These are assumptions, not a lifetime claim. The whole-board awake/idle figures
must include PD and other rail loads once, not double-count components. Attached
USB service should not be charged to a battery-only lifetime once an actual
power-path measurement establishes external supply. Future enabled charging
needs the100 ms freshness schedule, not the5 s parked fallback. Measurement may
justify a different parked cadence; this checkpoint does not widen any evidence,
lease, control, thermal or current limits to meet an energy target.

## Startup and remaining gates

USB-only/depleted-pack operation is **not proved**. At the corrected100 mA
hardware/software startup limit,9 V supplies at most0.9 W before loss; C6 Wi-Fi
TX peaks may exceed that. The later charging state machine must keep radio and
motor loads inhibited, obtain stable system power, verify factory policy and
live PD authority, validate commissioned pack/protection/temperature and fresh
charger readback, set and verify the intended conservative limits, and only then
permit charging and radio operation. The current Wi-Fi association ordering has
not been changed by this monitor checkpoint.

Real record admission, pack protection programming/verification, charge-enable
ordering/revocation, measured voltage-window policy, dead-pack bootstrap,
unpowered bus behavior, VSYS/VDD reverse current and physical validation remain
unfinished. No registered artifact proves a manufactured board safe to charge.
