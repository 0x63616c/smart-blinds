# Companion retained carrier

**UNVERIFIED, unrouted circuit checkpoint.** Three MYOUNG 21700 holders each
have a positive-branch fuse. Four solder landings permanently join the primary
carrier's raw ground, junction1, junction2 and raw top. This creates three
parallel cell pairs across the two boards, followed by the primary protection
and current shunt. The companion is not an independently protected battery.

The BOM has six purchased components; four wire landings are PCB features.
The compiled board has ten electrical footprints and sixteen physical pins,
plus four board-only NPTH mounting holes. Normal compilation and isolated circuit-only
frozen atopile 0.15.9 checks pass. Board-only holes are restored and checked
separately because the pinned compiler removes them during a direct build. Combined independent checks are in
`hw/sim/blind-pack`; see the primary README for wiring, limitations and gates.

Do not populate cells until the entire cassette's wiring has been inspected
and tested. The raw links must be permanently retained and insulated; there
is no exposed raw tap connector for the user to unplug. Loss of a middle link
can defeat individual monitoring of companion cells and is not a tolerated
single fault. The [placement study](../../placement/blind-pack/README.md) puts
components on the outward rear face of the cassette; its KiCad component view
is mirrored horizontally relative to the primary. Routing and physical fit
remain unqualified.
