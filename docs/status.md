# Progress

Updated 2026-10-19. [Public repository](https://github.com/0x63616c/smart-blinds).

## Foundation — implemented

The new project preserves e8s history and leaves the original repository unchanged. Current
requirements, sourced archive measurements, prototype gates and a source-generated README gallery
are recorded. The first GitHub preview run passed after the owner made this repository public.
A green preview result only confirms generation of the documented images.

## Initial design work — in progress

- Original parametric enclosure alternatives, provisional assembly/exploded views and fit-part
  meshes are being compared. Purchased motor/pack envelopes remain provisional.
- Charger, gauge/protection, motor driver and C6 radio candidates have sourced trade studies and
  a dated JLC catalog snapshot. The cost sensitivity is not a complete BOM or manufacturing quote.
- Portable motion/calibration code and the group coordinator pass local host tests, including
  seven different calibration maps following a shared physical-height trajectory. No motor has
  been driven and no Home Assistant integration is installed on the owner's system.
- The embedded C6 bring-up build, complete circuitry/routing and radio integration are in progress.

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
