# Split motor, encoder and reference connections

**UNVERIFIED assembly.** The selected PCB parts are Molex PicoBlade 532610471
(four-way encoder, **C696092**) and 532610371 (three-way optional home,
C293630). The old C240847 listing for the identical four-way MPN is unavailable
in the live snapshot; do not substitute stale search stock for current sourcing.
The original C240847 footprint import remains as provenance. Atomic symbol,
footprint and supplier metadata use the current C696092 listing.

`make_wrappers.py` rebuilds atomic parts from the imports and the manufacturer
[532610001-SD Rev E drawing, 2023-07-24](https://datasheet.lcsc.com/datasheet/pdf/eaf266ec0abfab79f30c5782540f9936.pdf?productCode=C240847).
The drawing was inspected visually. Pin1 is left of the contact-row origin,
and mating is +Y. The 1.25 mm pitch contacts use the drawing's 0.8×1.6 mm lands.
Two unnumbered mechanical solder nails use 2.1×3.0 mm lands at Y=2.9 mm. They
are neither signal pins nor assumed grounds. The corrected footprint retains
four plastic-foot keepouts against front copper, tracks, vias and pads.
Its overall courtyard also reserves space against other components.

| Geometry from contact-row origin | Four-way | Three-way |
|---|---:|---:|
| Nominal total body width | 10.15 mm | 8.90 mm |
| Width tolerance | ±0.4 mm | ±0.4 mm |
| Contact X positions | −1.875, −0.625, 0.625, 1.875 | −1.25, 0, 1.25 |
| Solder-nail X positions | ±4.425 mm | ±3.800 mm |
| All copper-pad X extent | ±5.475 mm | ±4.850 mm |
| Courtyard X extent | ±5.975 mm | ±5.350 mm |

For both: pads extend Y=−0.8..4.4 mm, central body Y=0.8..5.0 mm,
courtyard Y=−1.3..5.9 mm, nominal mated wire exit Y=6.0 mm, and nominal
mated height3.4 mm (general ±0.2 mm drawing tolerance). Mating/removal,
wire bend and service clearances are additional. The 3D models are imported
illustrations, not mechanical authority. The three-way imported filename
contains `CONN-TH` but every electrical and attachment pad is SMT.

The two-way 430450200 C122431 PCB Micro-Fit is retained only as an **unselected
packaging study**: the cable corridor does not fit the retained controller.
Its holes were corrected against SD-43045-001 Rev H, including the asymmetric
plastic locator at (−1.5,5.82). It is not in the selected harness test BOM.
Motor power instead uses retained solder tails and an upper-bay inline pair.

The source of truth for selected connections is `hw/boards/blind-harness`;
physical pin/land geometry checks are in `hw/sim/blind-harness`. Read
`docs/electrical/motor-signal-harness.md` before making cables.

Both selected PicoBlade footprints have `smd` assembly attributes, including
three-way 532610371 whose retained imported filename contains `CONN-TH`.
The generator writes matching atomic and `.pretty` copies. Atopile 0.15.9 omits
footprint-local rule areas, so run `python3 tools/apply_harness_keepouts.py BOARD`
after moving either connector. It restores the four plastic-foot copper exclusions
per header as board-level rule areas. Normal/frozen compilation retains these;
the harness check verifies their actual compiled position as well as pad geometry.
