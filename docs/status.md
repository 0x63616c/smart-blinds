# Progress

Updated 2026-10-19. [Public repository](https://github.com/0x63616c/smart-blinds).

## Foundation — implemented

The new project preserves e8s history and leaves the original repository unchanged. Current
requirements, sourced archive measurements, prototype gates and a source-generated README gallery
are recorded. The first GitHub preview run passed after the owner made this repository public.
A green preview result only confirms generation of the documented images.

## Initial design work — in progress

- The latest compact holder study reserves **115 × 174 × 71 mm**, or 78 mm deep
  with untrimmed holder pins. Two opposing three-cell carrier boards, front button
  plungers, antenna clearance and an outboard shaft bearing are modeled. The motor
  still carries part of the radial load. Case/carrier fastening, electrical placement,
  printed tolerances and owned-part fit remain open. The larger independently
  supported drive remains a comparison option.
- Charger, gauge/protection, motor driver and C6 radio candidates have sourced trade studies and
  a dated JLC catalog snapshot. The cost sensitivity is not a complete BOM or manufacturing quote.
- Portable motion/calibration code and the group coordinator pass local host tests, including
  seven different calibration maps following a shared physical-height trajectory. No motor has
  been driven and no Home Assistant integration is installed on the owner's system.
- The real Home Assistant custom component passes seven framework tests against HA 2026.10.2,
  including HA service calls through an authenticated loopback simulator to seven virtual blinds
  reaching the same 1030 mm height. The simulator is explicitly separate from real hardware;
  Thread transport and commissioning remain in progress.
- The motor-disabled C6 bring-up image cross-builds with official ESP-IDF v5.5.4. Actual board
  drivers, complete circuitry/routing and radio integration are in progress.
- A read-only MAX17320 I2C component compiles for the C6 with finite transaction requests and
  a capture deadline. The application does not call it; no battery hardware has been accessed.
- The first native KiCad motor-block schematic has 14 components and 43 pin connections
  independently checked against the atopile PCB graph. Four external-interface ERC findings
  remain explicit. A pinned atopile 0.15.9 frozen build and BOM-linked rating checks also pass
  locally; CI reruns both. It is not a routed board or a complete controller.
- The C6 interface, watchdog/reset gate and motor bridge now compose into a 61-component,
  207-pin capture with independent boundary checks. The earlier EN capacitor is removed;
  active-low requests agree with reset pull-ups. Front-button switches and an active-production
  MCU bulk capacitor replace earlier candidates. Whole-board routing/DRC and physical tests remain open.
- A second native schematic covers all 49 supervision pins, with two explicit external-power ERC
  findings. Both native schematics are checked by KiCad netlist export; vertical wire generation
  and an imported capacitor drawing were corrected without changing PCB connectivity.
- The 36-component BQ25798 charger has a 101-pin native schematic and independent
  physical-pin contract. DC-bias review added a fourth PMID capacitor. The new 12-part,
  31-pin logic supply capture uses two input capacitors and a reviewed inductor footprint.
  Both normal and frozen builds pass locally. Effective-capacitance calculations include
  typical curves, tolerance, temperature and an aging allowance; they are estimates,
  not guaranteed production limits or converter stability proof. USB-PD and protected-carrier captures now have independent checks; whole-board
  integration, regeneration handling, placement and routing remain unfinished.
- A full motor-disabled Thread/DTLS evaluation target linked successfully; startup hardening is
  verified by a fresh CI cross-build. It has no motion endpoint, commissioned credentials or measured
  C6 peer interoperability. A native libcoap host adapter passes 18 real local DTLS and clock
  tests, including seven simultaneous peers, bad credentials and encrypted-record
  replay/corruption. Its CCM8 security-policy exception is explicit and defaults off;
  production transport approval and commissioning remain open. Portable heartbeat tests cover acknowledged arming/edges,
  fresh control iterations, strict feed intervals and no command replay.
- The 33-component USB-C input has a 113-pin independent contract and native KiCad schematic.
  Five injected wiring faults are rejected. The proposed 9 V/15 V power path blocks 5 V
  fallback; factory NVM, attach/reset behavior, startup and transient immunity remain unqualified.
- The 33-component protected carrier has 103 independently checked pins, branch fuses,
  high-side disconnect FETs and separate pack temperature sensing. Its native schematic
  preserves the published 3S sense/balance mapping. Cell-contact heating, fault clearing,
  assembly insulation and commissioned protection settings still require qualification.
- A host-tested BQ25798 component proposes and reads back charger settings, checks fresh ADC
  conversions, and rejects bus/register/timer/temperature faults. It has no charging-enable
  operation; the C6 application compiles but does not call it. No cell or device was programmed.
- The partial main board now composes 190 components and 589 physical pins, including a
  reset-gated 5 V encoder supply and an independent thermal latch. Eight preserved blocks and nine integration tests
  check power-domain separation, factory-bus isolation and key control connections. Normal
  and frozen local builds pass; connectors and actual layout are next. Regeneration and
  thermal models have explicit transient and sustained-backdrive limits, not hardware approval.
- Offline STUSB4500 tooling checks documented PDO fields and full 40-byte readback. Static inspection of the pinned manufacturer GUI binary now identifies
  its above-5 V gate-policy field; unqualified discharge timers and device baseline still keep
  its output explicitly incomplete; no hardware has been accessed or programmed.
- The USB-C footprint now follows the manufacturer drawing, including its 1.14 mm signal
  lands, distinct shell slots and 0.46 mm mouth overhang. An independent pad/hole check
  covers the standalone and integrated captures. Actual connector fit remains unverified.
- The owner now prefers PCB-mounted cell holders; a separate protected holder carrier is being
  compared with main-board holders and welded construction. This may change the initial layouts.
- The exact motor listing is identified and partial seller dimensions are recorded. The owner is
  away for several weeks; design continues with allowances and replaceable fit parts.

The first complete study snapshot is `49f1d17`. Its [control/CAD-parameter/electrical-model checks](https://github.com/0x63616c/smart-blinds/actions/runs/39341111874)
and [source-generated preview workflow](https://github.com/0x63616c/smart-blinds/actions/runs/39341111797)
passed on GitHub. These checks validate the declared models and exports, not a physical product.
The subsequent [firmware freshness/gauge-tool checks and C6 cross-build](https://github.com/0x63616c/smart-blinds/actions/runs/39342005798)
also passed. The [native motor rebuild, Home Assistant framework tests and full check suite](https://github.com/0x63616c/smart-blinds/actions/runs/39350314683)
and [refreshed design gallery](https://github.com/0x63616c/smart-blinds/actions/runs/39350314795)
passed for `b01e5fb`. The [integrated cutoff/charger/Thread milestone checks](https://github.com/0x63616c/smart-blinds/actions/runs/39357729073)
and [source previews](https://github.com/0x63616c/smart-blinds/actions/runs/39357729056) passed for `28433e1`,
including the fresh hardened Thread build. The [protected-carrier milestone checks](https://github.com/0x63616c/smart-blinds/actions/runs/39361154907)
and [source previews](https://github.com/0x63616c/smart-blinds/actions/runs/39361154969) passed for
`757338e`, including all eight check jobs. The [USB-C and charger build checks](https://github.com/0x63616c/smart-blinds/actions/runs/39362944646)
passed for `495d01f` after fixing GCC signedness and ESP-IDF header warning compatibility.
The [USB-C schematic gallery](https://github.com/0x63616c/smart-blinds/actions/runs/39362552134)
also refreshed successfully. The [main-controller and encoder checks](https://github.com/0x63616c/smart-blinds/actions/runs/39364197874)
and [previews](https://github.com/0x63616c/smart-blinds/actions/runs/39364197877) passed for `9c74cb0`, including all eight jobs.
The [regenerative-clamp and captured-cost checks](https://github.com/0x63616c/smart-blinds/actions/runs/39365428219)
and [motion-executor/C6 I/O checks](https://github.com/0x63616c/smart-blinds/actions/runs/39365933426)
also passed all eight jobs. The C6 application still does not instantiate motion hardware.
Newer changes must be checked against their own runs.

## Inherited references

PD12V6 and PD12V6Mini remain under `hw/` with their original notes. PD12V6Mini is a USB-C
PD-to-12.6 V supply, not a complete charger or smart-blind controller. Prior validation claims
apply only to the recorded reference design and must be checked before reuse.

## Next gates

1. Review packaging alternatives, radio/charging trade-offs, and whole-system cost/power budgets.
2. Complete fresh circuitry, CAD retention/drive details, board port and secure radio integration.
3. Complete electrical/software/CAD checks and resolve source-model/measurement gaps.
4. Test two physical prototypes with the owner's hardware before the eight-unit build.

[Brief](brief.md) · [Verification plan](verification-plan.md) · [Recovered evidence](research/archive-findings.md)
