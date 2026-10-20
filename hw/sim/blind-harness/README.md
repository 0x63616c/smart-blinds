# Harness checks

`python3 hw/sim/blind-harness/checks.py --check` checks the standalone compiled
PCB's nine contact assignments, exact selected JLC IDs, two PicoBlade pad
patterns and their front-copper rule areas. Independent contact geometry is
derived from the visually inspected manufacturer drawing, not simply accepted
from the supplier import. Mirrored pin1 and encoder power/ground swaps are
negative controls. Results include source hashes and placement dimensions.

This does not prove motor lead identity, current capacity in the enclosure,
signal integrity, cable retention, mating access or mechanical fit. It does
not include the unselected two-/eight-way Micro-Fit PCB connector studies.

The check also requires SMT assembly metadata in both selected headers and eight
correctly transformed, board-level plastic-foot keep-outs. These were restored
using `tools/apply_harness_keepouts.py` because atopile omitted the footprint-local
areas. A subsequent normal and frozen build preserved all eight exclusions.
