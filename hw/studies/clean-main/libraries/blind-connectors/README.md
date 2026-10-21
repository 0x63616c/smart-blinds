# Protected-pack connector capture

Selected **Molex 430450600, JLC C127367**, right-angle two-row six-way tin
header. **UNVERIFIED for manufacture:** source dimensions and pin numbering
are checked; sample mating, retention, installed temperature and fit remain
open. `436500600` files preserve an evaluated single-row alternative; they are
not selected or instantiated by the connector test.

Recreate the selected atomic wrapper with `make_wrappers.py` in the atopile
Python environment. The combined library and `.pretty` retain EasyEDA import
provenance (easyeda2kicad 1.0.1, upgraded by KiCad 10.0.4). The atomic copy fixes
imported signal drills from approximately 1.2 mm to **1.02 mm**, changes its
single plastic locator from plated to **3 mm nonplated**, marks pin 1 and adds
complete body/courtyard outlines. Pads are 1.8 mm, a project annulus choice.
The supplier 3D shape is illustrative and is not dimensional authority.

## Independent source audit

Manufacturer **SD-43045-001 Rev H, 2024-06-05** was visually inspected from a
[distributor mirror](https://store.comet.bg/download-file.php?id=29300).
It lists the exact 43045-0600 finish and six-circuit pattern. Local work copies
are `work/datasheets/molex-43045-drawing.pdf` and `.png`; these are not claimed
to be the newest drawing revision.

Component-side view, mating toward +Y, coordinates in millimetres:

| Contact | X | Y |
| --- | ---: | ---: |
| 1 | 3 | 1.5 |
| 2 | 0 | 1.5 |
| 3 | -3 | 1.5 |
| 4 | 3 | -1.5 |
| 5 | 0 | -1.5 |
| 6 | -3 | -1.5 |

The one locator is (0, 5.82), 4.32 mm ahead of the front signal row. Six-way
numbering is sequential across each row; a generic alternating 2×3 footprint
would be wrong. Finished-hole tolerances are 1.02 ±0.05 mm and 3.00 ±0.05 mm.
Body is 12.65 mm wide, from Y=0.51 to 10.42; rear tails extend to Y=-1.82.
Tail and locator extension below seating is 3.18 mm nominal. A 1.6 mm board
leaves 1.58 mm nominal plus fillet, so no 1.5 mm underside clearance claim.
The 10.16 mm maximum locator-axis-to-board-edge requirement gives an edge
at Y≤15.98 to clear the mating receptacle. A notch must preserve peg/pad
annulus, route clearance and board strength.

The [Molex 430250000-SD Rev A housing drawing](https://www.molex.com/content/dam/molex/molex-dot-com/products/automated/en-us/salesdrawingpdf/430/43025/430250600_sd.pdf)
was independently rendered from a [manufacturer-authored mirror](https://static.maritex.eu/file/display/byVFWC0B1L2j0n10Z6Yv_MBP6mNQYIro/43025-0600.pdf).
It gives six-way housing width 9.85 +0.35/-0.25 mm, mated axial length 17.56 mm
from the header body rear (wire exit Y=18.07), **10.81 mm mated height** and
**11.0 mm for latching**. These supersede the smaller 10.29 mm product metadata
for enclosure planning. General metric tolerances imply conservative 11.06 mm
mated / 11.35 mm latch envelopes before PCB and printed-part variation.

`check.py` checks physical pads independently. `hw/sim/blind-connectors/checks.py`
checks the compiled physical pin names and geometry, plus source hashes.
These are not routing DRC, native schematic ERC or a physical acceptance test.
