# Progress

Updated 2026-10-19. [Public repository](https://github.com/0x63616c/smart-blinds).

## Foundation — implemented

The new project preserves e8s history and leaves the original repository unchanged. Current
requirements, sourced archive measurements, prototype gates and a source-generated README gallery
are recorded. The first GitHub preview run passed after the owner made this repository public.
A green preview result only confirms generation of the documented images.

## Initial design work — in progress

- The second packaging comparison includes PCB-mounted holders, supported inline shafts and
  a belt alternative. The simplest single carrier currently reserves 170 × 158 × 64 mm; the
  twin carrier reserves 150 × 158 × 74 mm. Further antenna/holder placement work is aimed at
  reducing depth. Purchased motor/holder fit and the retained assembly remain provisional.
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
- The 35-component BQ25798 charger capture builds with source/BOM-linked rating checks. USB-PD,
  protected carrier, regulator and regeneration integration remain separate work.
- A full motor-disabled Thread/DTLS evaluation target linked successfully; startup hardening is
  awaiting a fresh CI cross-build. It has no motion endpoint, commissioned credentials or measured
  peer interoperability. Portable heartbeat policy tests now cover acknowledged arming/edges,
  fresh control iterations, strict feed intervals and no command replay.
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
passed for `b01e5fb`. Latest changes must be evaluated against their own workflow runs.

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
