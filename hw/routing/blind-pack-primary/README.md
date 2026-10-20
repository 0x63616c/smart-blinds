# Experimental primary-carrier current routing

This is a **partial two-layer routing study**, not a complete PCB or fabrication
release. The canonical circuit and placement remain under
`hw/layouts/blind-pack-primary/`. The derivative has 102 copper segments,
32 tented vias and no copper pours. **55 signal and bypass connections remain
unrouted.**

![Actual partial front and back copper](copper.svg)

Red is the outward component face; blue is the inward face. The route includes
the three individually fused cell branches, four retained raw links, the
common-drain protection-FET path, protected output trunks, the shunt, and its
two separate sense traces.

Actual KiCad 10 DRC reports no shorts, copper/edge/hole-clearance,
keepout or courtyard-overlap failures on this partial copper. It retains all
55 unconnected items, 26 inherited silkscreen findings, and four explicitly
enabled missing-courtyard errors on the board-only mounting holes. These are
reported, not waived. Three unrelated KiCad categories retain their default
disabled state and are listed in `checks.json`.

`checks.py` compares the complete physical pad shapes, masks/paste settings,
placements, side, net identities, outline, mounting holes and support/RF
reservations with the canonical capture. It separately checks the twelve fixed
solder-pad anchors and diameters against the coordinated primary spacer relief.
The primary upper crossbar is removed around those tails; the perimeter,
corner posts and barrier remain. The 0.5 mm tail-to-barrier gap is nominal and
needs tolerance and assembly qualification.

The derivative changes only these electrical placements:

| Part | Local xy, rotation |
|---|---|
| Three nonpolar fuses | Existing centres, 90° → 270° |
| Shunt | (47, 4), 0° |
| Fourth balance resistor | (73, 4.5), 90° |
| Charge-gate resistor | (51, 1), 0° |
| Charge-gate capacitor | (51.6, 7.1), 0° |
| PFAIL pulldown | (33.5, 1), 0° |

The PFAIL move frees the two gauge sense-pin escapes without moving any
holder, mounting feature, wire pad or board edge. Its signal route is unfinished.
All geometry deltas are checked independently; canonical sources are untouched.
Export order and item UUIDs are deterministic, and repeat generation produces
byte-identical PCB and project files.

The Kelvin check uses actual copper shapes rather than net names. It first
requires each sense pin to reach its correct shunt landing. It then removes
that landing from the physical connectivity graph and checks that the sense
branch reaches no other pad or load-current trace. Negative controls insert an
early same-net connection and cut a sense trace; both are rejected. The ten
required current-path groups, including every duplicate drain land, are also
checked for physical connectivity. This does not yet validate the unfinished
gauge ground return or bypass loops.

Long power traces are generally 3 mm. Short transitions use 2 mm, while the
fixed six-way wire-pad row requires short 1.5 mm raw-link necks. Those middle
links have zero net current only under ideal equal sharing; their geometry is
not permission to ignore imbalance or faults. FET pin fanouts and source buses
are narrower and need explicit thermal review. The signal-clearance rule is
0.20 mm; copper-to-edge is 0.30 mm. Power vias use 0.9/0.4 mm land/drill;
signal vias use 0.6/0.3 mm. These are planning dimensions, not current ratings.

The conservative 4 A pack / 2 A per parallel-cell calculation gives about
**1.73 W in this primary copper**, or 2.52 W in traces alone under the
70°C / 20% narrower-width sensitivity. It deliberately overcounts shared
source/drain paths and both sides of via banks. It is not a temperature
prediction and excludes cells, contacts, fuse elements, shunt, FETs, solder and
harnesses. The long trunks and narrow FET buses deserve widening or comparison
with 2 oz copper before acceptance; holder heating remains a separate major
unknown. The exact assumptions and saved-copper dimensions are in
`copper-losses.json`.

Reproduce on Linux with KiCad 10 and its distribution Python bindings:

```sh
xvfb-run -a /usr/bin/python3 hw/routing/blind-pack-primary/route.py
xvfb-run -a /usr/bin/python3 hw/routing/blind-pack-primary/checks.py --negative-tests
python3 hw/routing/blind-pack-primary/estimate_losses.py
```

On macOS use KiCad's bundled Python for the first two commands. Do not run the
derivative through atopile or the canonical placement/hole-restoration tools.
Next work is the close gauge bypass/ground-return layout, remaining sensing and
communication routes, copper-loss refinement, full DRC, and physical thermal,
protection and assembly testing.
