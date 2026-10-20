# Retained pack partition checks

`python3 hw/sim/blind-pack/checks.py --check` verifies the two compiled PCB
graphs joined by four explicit permanent wire links. It compares all 136
physical pins with the earlier independently audited MAX17320 carrier
contract plus the holder and pigtail assignments. It also verifies the
unchanged protection-core source, the six holder/fuse branches, the holder's
terminal slots and preserved mechanical holes, and exclusion of wire pads
from the local generated BOM when that build artifact exists.

Six negative controls cover swapped middle links, either board's bypassed
cell fuse, raw-ground bypass of the protected output, the wrong 3S CELL2
connection and an incorrectly grounded charger-NTC return.

This does not simulate lithium-ion cells, contact heating, short-circuit
interruption, insertion equalization, lost-interconnect behavior, MOSFET SOA,
or gauge/protection configuration. In particular, a physical open middle
link can leave companion cells unmonitored. Source hashes and the semantic
graph digest are recorded in `results.json`; this is an unrouted checkpoint.
