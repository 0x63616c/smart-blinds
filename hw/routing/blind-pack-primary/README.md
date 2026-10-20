# Experimental primary-carrier route

This KiCad 10 derivative has **451 segments, 129 vias, 35 physically connected nets and zero native DRC unconnected items**. It is a completed connectivity study, not a fabrication release or accepted transient/thermal design. The canonical circuit and first placement remain under `hw/layouts/blind-pack-primary/`; this derivative preserves their physical pin/net graph and the documented placement changes.

The three communication Zeners now return to **PACK−**, with cathodes on the external side of their 150 Ω resistors. This is the exact six-pin correction documented in [the communication-clamp review](../../../docs/electrical/pack-communication-clamps.md). Purchased parts, footprints, outline, holder/harness/mechanical anchors and the previously reviewed electrical placement deltas are unchanged.

![Actual front and back copper](copper.svg)

The return uses a 6 mm front-layer spine and a 9.307 mm back-layer branch, both 0.8 mm wide, with a 0.9 mm-long / 0.6 mm-wide front escape to one 0.60/0.30 mm via into the protected-ground harness landing. The Zeners no longer discharge through the approximately 96 mm NTC/gauge quiet return. This shorter topology is checked from the saved copper geometry; it is **not** a measured ESD impedance, pulse-survival or EMC result. The selected BZT52C4V7 parts still have unresolved leakage at 3.3 V, capacitance, negative-pulse and surge qualification.

`checks.py` compares every physical pad/net identity with the corrected capture, the fifteen recorded small-part moves and three nonpolar-fuse rotations, mechanical anchors, clearance envelopes, both-face support/RF areas, fixture lands, twelve tail anchors, unique UUIDs and exact route inventory. It independently checks ten load-path groups, both Kelvin branches with their shunt land removed, twelve quiet-return pad groups, and the three clamps' actual protected-ground connection. Each of all 35 nets must form one copper-shape component; equal net names alone cannot pass. All 129 via drills must also clear every one of the 109 external SMD lands by 0.20 mm on either face, regardless of net identity. Tenting is not treated as filled/capped via-in-pad process approval.

Eleven deliberately injected faults are rejected, including a same-net via drilled into a diode solder land, a cut clamp return, cut sense and bus routes, an early Kelvin/load join, an early quiet-ground/CSP join, incorrect via geometry, a narrowed load trace and a moved holder. Two repeated generations preserve PCB, project, rule and route-record bytes exactly.

KiCad 10.0.4 DRC includes errors, warnings and exclusions, retaining **15 silk-over-copper, three silk-edge and four exact board-only mounting-hole missing-courtyard findings**. No copper, edge, hole, short, keepout, electrical-footprint courtyard, dangling-via or unconnected finding remains. Three unrelated categories keep their default disabled state: track-not-centered-on-via, tuning-profile geometries and symbol-footprint filter mismatch. This is not an all-checks-enabled claim.

Ordinary signal clearance is 0.20 mm, with 0.30 mm copper-to-edge clearance. Sixteen 0.50/0.25 mm signal vias remain confined to the gauge escape region; ordinary signal vias are 0.60/0.30 mm and load vias are 0.90/0.40 mm. The long low-current IN feed alone uses a 0.15 mm trace. Fine-hole price/process acceptance remains subject to a real manufacturing quote.

The load copper is unchanged by the clamp correction. Saved-copper arithmetic remains **1.410 W nominal** at a provisional 4 A pack / equal 2 A parallel-cell split, using nominal 35 µm copper. A 70 µm comparison is about 0.717 W including unchanged via estimates; no copper process has been selected. The 70°C / 20% narrower sensitivity is 2.046 W in traces alone. These calculations do not predict temperature or guarantee current sharing. Cells, contacts, fuse elements, FETs, shunt, solder and harness losses are excluded.

Remaining gates include the long NTC return, gauge bypass/common-return impedance, bus margin and transients, fuse/holder/fault heating, matched-cell assembly, reverse insertion, retention, tail/barrier clearance, thermistor placement and protection commissioning. No hardware has been fabricated or powered for this route.

## Reproduce

From the repository root, with KiCad 10 Python on PATH (Linux: system Python with `pcbnew` and `wx`, under `xvfb-run -a`):

```sh
/Applications/KiCad.app/Contents/Frameworks/Python.framework/Versions/3.9/bin/python3.9 hw/routing/blind-pack-primary/route.py
/Applications/KiCad.app/Contents/Frameworks/Python.framework/Versions/3.9/bin/python3.9 hw/routing/blind-pack-primary/checks.py
python3 hw/routing/blind-pack-primary/estimate_losses.py
```

The generator uses finite coordinates from `route.py`, `signals.py` and `gates.py`. Search helpers and rejected intermediate routes are not part of the frozen implementation. `checks.json` includes source hashes and native DRC results. Repeated local runs were byte-identical after relocation to this maintained package. The maintained route/check records bind the source and dependency hashes. Do not run this routed derivative through atopile or the unrouted-format converter.
