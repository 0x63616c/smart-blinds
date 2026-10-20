# Main-controller partial power routing

This is a **partial four-layer routing study**, not a manufacturing release.
The canonical circuit and first placement remain under `hw/layouts/blind-main/`.
The derivative retains the 54 × 68.5 mm outline with its USB tab, all 196
footprints, 609 physical pin identities, 142 net partitions, 17 mechanical/thermal
anchors and 13 RF, connector-foot and clamp reservations.

The checkpoint contains 636 segments and 178 vias. It routes the local charger
switching/bypass network, motor-driver fly/pump/VM and output paths, regulator
bypass/output/sense paths, and a 3.3 V feed to the radio module. In1 remains a
continuous filled ground-return island; no signal traces use that layer. The
module power feed uses In2 beneath the permitted module body, with vias outside
its solder lands and unchanged antenna keepouts.

Actual KiCad 10 DRC reports **257 unconnected items**. No short, copper/edge/hole
clearance, track-width, courtyard-overlap, keepout, mask-bridge or dangling-route
failure is accepted. The report retains 260 silkscreen/text findings, four
library-footprint differences and five footprint-type findings. The latter
include mixed through-hole/thermal features and incorrectly classified library
attributes; they require footprint/assembly review, not a blanket waiver.
Three unrelated default-disabled DRC categories are listed in `checks.json`.

`checks.py` independently checks actual pad shapes, masks/paste settings, net
partitions, layer/rotation/placement, outline, keepouts, courtyard bounds and
encoder-wire height clearance. It also follows physical copper shapes through
72 required connection groups, including the ground fill. A matching net name
alone cannot pass. Twenty-six injected faults are rejected: moved USB connector, changed motor pad,
weakened RF reservation, cut module supply, removed return plane, cut charger
bypass return, cut PD bypass, cut USB input, removed quiet return via, and an
extra connection from the quiet return to the input-capacitor return, plus open
PD enable, UV divider, raw discharge and address-ground branches. The new controls
also cut the charger input, PMID and SYS bulk branches and input-capacitor return,
and place a same-net solder land over an ordinary open via. All 38 new distribution
vias preserve at least 0.20 mm from their drill edges to top solder lands; native
same-net clearance alone does not check this assembly condition. Both REGN and VBUS bypass
returns have two nearby ground vias, as required by the charger layout guide.
The checks remove the plane from the local graph before counting those vias. The generator is deterministic across repeated local runs.

The USB addition connects both VBUS contacts to the eFuse and its output
reservoir, with local input capacitance and a shunt TVS. It also connects the PD
supply diode and three separate bypass branches, and both CC/protection/dead-battery paths. The two MCU data resistors
have short local stubs; the USB data pair itself is **not routed**. The eFuse's
current-setting, slew and divider-endpoint components return through an isolated
same-face branch to one ground via. An independent plane-free copper check
requires exactly those five quiet-ground pads and that one via; it rejects the
input-capacitor return joining this branch even though the net names agree.

The PNP enable stage, both voltage dividers, raw/output discharge chains and
PD address/reset/bus resistor branches are now connected. Their explicit
coordinates are replayed from `usb-control-routes.json`; reproduction performs
no route search. Five separate local ground vias serve the address and factory
bus resistors without joining the eFuse quiet-ground branch.

The USB data pair and factory access pads remain open.
The completed control connections do not establish negotiated startup or
detach/discharge timing; the PD configuration and electrical tests remain
required. The 0.3 mm central-pad escapes and 0.8 mm back-layer power trunks
need current/temperature review; the present geometry is not a current rating.
The input TVS's specified pulse clamp can exceed downstream DC limits; placement
does not resolve that separate transient qualification issue. The eFuse layout
uses a quiet return, but loop impedance and coupling still need review.

The eFuse output now reaches the charger VBUS pins and input capacitors. The four
PMID and five SYS bulk capacitors connect to their existing local fast-bypass
branches through explicit two-via fanouts and In2 distribution traces. Input and
bulk-capacitor grounds join the uninterrupted In1 return. The replay coordinates
in `charger-power-banks.json` and `distribution.py` require no routing search.
The previous 581 copper items are retained. Fifteen previously unwired parts move
to make room, including the encoder supply block; all mechanical anchors remain.
These distributed reservoirs still need ripple-current, return-loop and thermal
review. The 0.6–0.8 mm In2 traces use 15.2 µm copper, so geometric clearance is not
a demonstrated continuous-current rating. Pack feed and onward SYS distribution
remain open.

The next extension connects both VAC inputs, BATP feedback, TS and ILIM networks,
PROG and their local returns. Six previously unwired control parts move; no
mechanical anchor changes. Its explicit paths in `charger-control-routes.json`
are replayed by `charger_controls.py`. A bootstrap via moves 0.25 mm to provide
two adjacent sensing escapes; its two incident traces follow it. The other 696
previous copper items are retained exactly. Seventeen control-area vias
(sixteen added and that relocated via) pass the same 0.20 mm drill-to-solder-land
margin, including same-net lands. Five new deliberate opens and a same-net
control-via intrusion are rejected. These connections need switch-noise,
feedback accuracy, thermal and transient review; full charger control, bus and
charge-permission wiring remain unfinished.

A subsequent assembly-clearance pass moves twelve ordinary vias by at most
0.35 mm and adjusts their sixteen incident traces. Five short top-layer stubs
preserve connections that previously relied on via copper touching a solder
land. No component moves. All 178 routed via drills now remain at least 0.20 mm
from every top solder land, including lands on the same net; the ordinary
KiCad same-net clearance check alone does not ensure this. A deliberate
same-net intrusion at the USB input capacitor is rejected. The explicit
`via-land-clearance.json` changes replay through `via_lands.py`; this is not a
filled/capped via-in-pad process. Thermal holes inside library footprints still
require their separate solder/paste and assembly-process review.

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

Still unfinished: USB factory access and paired data routing, pack feed and onward SYS
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
[STUSB4500](https://www.st.com/resource/en/datasheet/stusb4500.pdf),
[TPS25947, §8.4](https://www.ti.com/lit/ds/symlink/tps25947.pdf),
[JLC capabilities](https://jlcpcb.com/capabilities/pcb-capabilities), and
[JLC stackups](https://cart.jlcpcb.com/client/template/placeOrder/impedance.html).
These guide the study; they do not validate the finished board.
