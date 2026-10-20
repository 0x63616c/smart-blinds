# Main controller placement

Updated 2026-10-20. Preliminary source-generated placement; no routed copper or
manufacturing acceptance. The board is 54 × 68.5 mm, with a small USB-C extension.
The coordinated enclosure study remains 115 × 174 × 71 mm.

The explicit placement source is `hw/placement/blind-main/placement.json`.
Mechanical anchors and clamp lands are in `cad/parameters/retained-interfaces.json`.
Local u/v maps to KiCad x = 100 + u and y = 175 − v, in millimetres.

The C6 antenna overhangs the top edge. Three all-copper rule areas reserve the
antenna and its sides; only the module itself may use its central body exception.
The independent checker rejects unrelated pad copper in that exception. Two bare
clamp lands and eight PicoBlade plastic-foot regions are also preserved in the PCB.
Atopile drops footprint-local rule areas, so the reviewed source regions are
explicitly restored as board-level areas and checked after compilation.

The main motor connector uses two soldered, separately retained 18 AWG tails to
an inline keyed disconnect in the upper bay. That avoids a tall board-mounted
motor plug. Encoder and home headers have their own cable corridors. The home
header is dry-contact only: pin 2 remains isolated. Cable bend, pull, insertion
and owned-motor compatibility remain physical qualification gates.

## Current checks and outstanding work

- 196 placements and 609 circuit pin identities survive normal and frozen builds.
- Manufacturer land checks cover the charger, motor driver, radio and USB input.
- Actual KiCad DRC reports no courtyard overlap or keepout infringement in this placement.
  However, 98 inherited footprints currently lack front courtyards, so that overlap
  result has incomplete coverage. Their clearance outlines must be added and checked
  before routing or a full component-clearance claim.
- The board has no routed tracks/vias. Hundreds of unrouted connections remain.
- Default DRC still reports the eFuse's 0.19 mm pad spacing against a 0.20 mm
  default, USB NPTH/edge clearances, 0.20 mm thermal drill size against a 0.30 mm
  default, and imported silkscreen collisions. These are not waived or called clean.
  Final manufacturing rules and silk cleanup remain separate reviewed work.
- Component proximity is preliminary. Switching loops, analog sensing, antenna
  ground, high-current copper and thermal spreading must govern routed refinement.
  Compact placement does not establish the resistor bank's continuous power rating.

The four-layer descriptor is a study using JLC's published 1.6 mm JLC3313 table,
not a selected manufacturing stackup. USB impedance needs a field-solver geometry
for the eventual quote. Black mask/four layers/ENIG presently implies Standard
assembly rather than the Economic comparison used in the early cost sensitivity.
The narrow board also needs assembly rails/panel review.

[Published stackup reference](https://cart.jlcpcb.com/client/template/placeOrder/impedance.html) ·
[Published capabilities](https://jlcpcb.com/capabilities/pcb-capabilities).

## Reproduction

Run `tools/apply_main_placement.py` with KiCad's Python runtime. It refuses tracks,
vias and copper zones. It places the explicit source coordinates, rebuilds the
outline and rule areas, resolves existing local model paths, then converts only
reviewed KiCad 10 defaults to the pinned compiler's KiCad 9 representation.
`tools/normalize_placement_pcb.py` rejects circuit changes, routed copper and
unsupported via-process overrides. Normal/frozen atopile builds and independent
net checks follow the replay. This helper must not be used once routing begins.

The `hw/layouts/parts` symlink resolves inherited model paths for both the old
two-level layout folders and new three-level build folders. It points to the same
tracked parts library; no component model is substituted. The renderer fails if
any referenced model file is absent and records hashes of all models it uses.
