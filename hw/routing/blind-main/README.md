# Main-controller partial power routing

This is a **partial four-layer routing study**, not a manufacturing release.
The canonical circuit and first placement remain under `hw/layouts/blind-main/`.
The derivative retains the 54 × 68.5 mm outline with its USB tab, all 196
footprints, 609 physical pin identities, 142 net partitions, 17 mechanical/thermal
anchors and 13 RF, connector-foot and clamp reservations.

The checkpoint contains 222 segments and 72 vias. It routes the local charger
switching/bypass network, motor-driver fly/pump/VM and output paths, regulator
bypass/output/sense paths, and a 3.3 V feed to the radio module. In1 remains a
continuous filled ground-return island; no signal traces use that layer. The
module power feed uses In2 beneath the permitted module body, with vias outside
its solder lands and unchanged antenna keepouts.

Actual KiCad 10 DRC reports **364 unconnected items**. No short, copper/edge/hole
clearance, track-width, courtyard-overlap, keepout, mask-bridge or dangling-route
failure is accepted. The report retains 261 silkscreen/text findings, four
library-footprint differences and five footprint-type findings. The latter
include mixed through-hole/thermal features and incorrectly classified library
attributes; they require footprint/assembly review, not a blanket waiver.
Three unrelated default-disabled DRC categories are listed in `checks.json`.

`checks.py` independently checks actual pad shapes, masks/paste settings, net
partitions, layer/rotation/placement, outline, keepouts, courtyard bounds and
encoder-wire height clearance. It also follows physical copper shapes through
24 required connection groups, including the ground fill. A matching net name
alone cannot pass. Six injected faults are rejected: moved USB connector,
changed motor pad, weakened RF reservation, cut module supply, removed
return plane, and cut charger bypass return. Both REGN and VBUS bypass
returns have two nearby ground vias, as required by the charger layout guide.
The checks remove the plane from the local graph before counting those vias. The generator is deterministic across repeated local runs.

The complete placement change list is in `checks.json`. Many support components
have moved from the first placement to make local electrical loops possible.
The critical-loop review remains incomplete: especially charger bootstrap
routing, current/return geometry, switch-node coupling and module supply
impedance. The external 100 nF and bulk radio capacitors are about 18 mm from
the module supply pin; the wide internal feed is a layout candidate, not
proof of adequate local decoupling. Geometric clearance does not establish
electrical performance.

## Rules and outstanding work

The study retains the preliminary 1.6 mm JLC3313 four-layer descriptor: 35 µm
outer and 15.2 µm inner copper. Comparative minima are 0.15 mm trace/clearance,
0.20 mm copper-to-edge and hole-to-copper, 0.25 mm hole-to-hole, 0.20 mm minimum
hole and 0.10 mm annular ring. Ordinary route vias are 0.6/0.3 mm; selected
fine-pitch escapes use 0.5/0.25 mm. Existing thermal holes require their own
mask/paste/assembly-process review. These rules are not a current rating,
impedance approval, assembly quote or final fabrication profile.

Still unfinished: USB input/protection and paired data routing, pack/charger/SYS
current distribution, regenerative-clamp and supervisor loops, complete signal
routing, thermal and transient review, sparse silkscreen, final ERC/DRC and a
manufacturing quote. A separate local 18-net digital congestion experiment is
not part of this committed power-route checkpoint. No autorouter result is
substituted for the local power-layout review.

## Reproduce

Use KiCad 10 and its distribution Python bindings, from the repository root:

```sh
xvfb-run -a /usr/bin/python3 hw/routing/blind-main/route.py
xvfb-run -a /usr/bin/python3 hw/routing/blind-main/checks.py --negative-tests
```

On macOS use KiCad's bundled Python, without `xvfb-run`. Intermediate files stay
under `work/main-route-build/`. The checked-in project template is used; no
untracked local KiCad project or global rule override is required. Never pass
this routed derivative through the unrouted-only atopile normalizer.

Layout references: [BQ25798, §8.4](https://www.ti.com/lit/ds/symlink/bq25798.pdf),
[DRV8874, §10](https://www.ti.com/lit/ds/symlink/drv8874.pdf),
[TPS62902, §8.5](https://www.ti.com/lit/ds/symlink/tps62902.pdf),
[Espressif layout guidance](https://docs.espressif.com/projects/esp-hardware-design-guidelines/en/latest/esp32c6/pcb-layout-design.html),
[official DevKit layout](https://dl.espressif.com/dl/schematics/esp32-c6-devkitc-1-pcb-layout_v1.2.pdf),
[JLC capabilities](https://jlcpcb.com/capabilities/pcb-capabilities), and
[JLC stackups](https://cart.jlcpcb.com/client/template/placeOrder/impedance.html).
These guide the study; they do not validate the finished board.
