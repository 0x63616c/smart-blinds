# Current enclosure candidate

118 × 196 × 77 mm case with an inward-facing 54 × 80 mm controller, protected
battery cassette and integral front buttons. This is prototype geometry;
physical fit and electrical qualification remain open.

[Inventory](inventory.md) · [Print list](print-list.csv) · [Service sequence](service.md) ·
[Parameter and mesh limits](dependencies.md) · [Reviewed handoff](handoff.md)

The imported local checkpoint passed 17 geometry checks against native board
`03a6b3dc…`: 206 footprints and 120 rear vias. It preserves four original
cassette-overlap witnesses. Only the front and rear cassette shapes changed;
the other 28 export roles retain their prior geometry. There are 22 installed
pieces per blind, plus two optional cosmetic plugs and a shared button nest.
The older holder-loading fixture has not been requalified for this revision.

CI first compares its newly built native PCB with this package's explicit board
and source bindings. A changed board must be deliberately reviewed and rebound;
the copied old board cannot silently approve a newer route.

Use Python with `numpy==2.3.5`, `manifold3d==3.3.2` and OpenSCAD on the path:

```sh
python cad/enclosure-v2/rebuild.py
```

This sequentially checks parameters, exports parts, runs all 17 checks, computes
the inventory and renders four local cutaways. Linux needs Xvfb for rendering.
The central preview workflow separately renders closed, cover-off and service
views from `source/assembly_v2.scad`. Those views use envelopes for prominent
PCB parts; the native KiCad view shows the populated controller.

`evidence/reviewed-checkpoint.json` preserves the original local review's file
hashes. `evidence/promotion-delta.json` records subsequent integration edits,
including the black board display color. Fresh CI reports are new evidence;
they do not restamp that human review. `freeze.py` is an explicit one-time
review operation and is excluded from the ordinary rebuild.

Two exact inherited cassette meshes remain Boolean source operands. The
cassette is not arbitrarily resizable. Motor/holder fit, insulation, print
strength and creep, wire bending, catch release and loaded handling still need
physical tests. The optional home-sensor path remains unfinished. No purchase
or fabrication is authorized by a geometry pass.
