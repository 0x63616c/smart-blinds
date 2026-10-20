# Retained carrier routing assessment — 2026-10-20

Read-only assessment of the frozen canonical carriers at commit8975687. No routing/fabrication acceptance. The primary PCB SHA is fecc56c96206151d1abf174f17da5756d6655759b423a150b72ef37fc5cad8c6; companion629badeee425db788ad6c0246485f998eafa8df5b7ab3ce49790716f5382a712. All coordinates below are assembly-local millimetres, not the mirrored companion's native PCB axes.

## Findings that change the implementation

1. **Companion upper support blocks routing.** The existing BOTH-layer UPPER_SUPPORT rectangle x4–82,y94–97 separates all cell terminals (y≤89.9) from the four raw links(y100). Its endpoints overlap the corner-boss exclusions centred(4,100)/(82,100), radius3.8. The board corner radius4 leaves only0.2mm nominal around those bosses, less than the proposed0.3mm copper-edge margin even before track width. This is not solved by sending four current rails around the ends. Mechanical additionally found a spacer touching the B.Cu face. Parent approved a trial0.3mm spacer relief over x9–77,y94–97, retaining F.Cu support and corners/edges. Only covered B.Cu traces may cross this exact window: no vias, pads, tails, exposed copper or pours. Mechanical will own the contract/relief. This was a routing blocker at the initial assessment; the dated implementation checkpoint below records its later resolution.

2. **Rotate nonpolar fuses180° in the derivative.** All three current fuse pin1 lands sit at y1.545, while unfused holder+ is y9.9. Fused pin2 at y6.455 lies between. Rotating the fuses180° puts pin1 toward the holder and shortens the unfused centre-to-centre span from8.355mm plus detour to3.445mm. Same part, pads, nets, body and courtyard; sole currently authorized component-placement delta. No equal-current-sharing claim follows from similar copper lengths.

3. **Primary gauge/shunt placement needs a routing pass.** CSP/CSN at approximately(28.25,5.91)/(28.75,5.91) are42–48mm from current shunt pad centres(70.145,4.5)/(75.855,4.5). A broad raw-ground fill would electrically satisfy the netlist but defeat the intended Kelvin connection if it joined CSP early. Reserve two unbranched sense traces from inner shunt-pad edges, prohibit same-net plane shortcuts into them, and attach IC GND/EP separately to the raw-ground current path. Ground identity alone is insufficient to verify this.

4. **Thermal proof cannot come from trace widths.** At4A total, the existing scoped model gives0.1616W shunt,0.336W FET-pair cold maximum or0.672W doubled-resistance planning value, and0.5448W nominal fuse dissipation across six equal2A branches. Holders add2.4W if100mΩ is a full holder path, or4.8W if per contact. Those assumptions dominate copper refinement and remain unqualified. The failed-short protection-FET case and parallel-cell equalization are still unresolved, irrespective of routing.

## Proposed two-layer construction and numerical bounds

Start with1.6mm FR-4, two external1oz copper layers, all components on the outward F.Cu face. Prefer0.25mm signal widths/clearances,0.3mm copper-to-edge planning clearance,3mm long current rails and2mm minimum short fanout where pad geometry requires it. A0.20mm trace/clearance escape can be reviewed at the0.5mm-pitch gauge if0.25mm will not fit. These are design choices, not a blanket4A trace rating.

JLC currently lists1/2oz two-layer options, minimum1oz width/space0.10/0.10mm,2oz0.16/0.16mm, track-width tolerance±20%,1.6mm-board thickness±10%, and18µm *average* hole plating. Use a conservative0.9mm via land/0.4mm finished hole for the1oz study (0.25mm nominal annular ring). Do not treat the listed average plating as a minimum barrel thickness. A2oz alternative needs its own cost and annular-ring/rule review; it is not selected merely to rescue a narrow track. [JLC capabilities](https://jlcpcb.com/capabilities/pcb-capabilities), accessed2026-10-20.

TI's square-count approximation is0.5mΩ/square for1oz copper,0.25mΩ/square for2oz at25°C; it gives0.7/0.35mΩ/square at125°C. Applying it to a single100mm segment gives the table below. These are resistance/loss estimates, not simulated or measured temperature rises. [TI PCB layout for SMPS](https://www.ti.com/lit/pdf/sszp640), indexed primary table; [TI square-count explanation](https://www.ti.com/document-viewer/lit/html/SSZTAT5).

| 1oz width | R at25°C for100mm | Drop at4A | Loss at4A | Loss at2A |
|---|---:|---:|---:|---:|
|1mm|50mΩ|0.200V|0.800W|0.200W|
|2mm|25mΩ|0.100V|0.400W|0.100W|
|3mm|16.67mΩ|0.0667V|0.267W|0.0667W|
|4mm|12.5mΩ|0.050V|0.200W|0.050W|

At80% nominal width these values increase25%; at70°C use approximately1.18 times25°C resistance for copper as a planning estimate. A3mm100mm rail then reaches about24.6mΩ/0.393W at4A. Do not calculate total pack loss by multiplying every segment by4A: branch and middle-link currents depend on imbalance. Extract lengths and run a resistor network once routed; also check one-parallel-cell-absent paths separately.

A geometric0.4mm barrel,1.6mm length,18µm wall gives about1.22mΩ at20°C. Four such vias in parallel give0.305mΩ and4.9mW at4A, excluding necks/pads. This arithmetic is not a via-current qualification because plating distribution, spreading and heat removal are unverified. Use multiple vias at power transitions, outside solder lands; do not quietly introduce open via-in-pad that can wick solder from fuses/FETs.

The AON7400A published steady-state75°C/W maximum uses a1in² FR-4,2oz test board. Applying it to each0.168W cold FET would suggest12.6°C rise only **on that test condition**; the actual narrow cassette strip cannot inherit it. The hot planning0.336W/FET would double that illustrative rise. The shunt is1W at70°C but neighboring-cell/contact/fuse heating still matters. [AOS AON7400A](https://www.aosmd.com/sites/default/files/res/datasheets/AON7400A.pdf), Rev4.1 pp1–2, local `work/datasheets/aon7400a.pdf`; [Vishay WSL](https://www.vishay.com/docs/30100/wsl.pdf), p1.

## Exact companion topology and route order

Preserve four distinct current nodes, even though the middle links may carry little net current under ideal sharing:

| Node | Required physical terminals |
|---|---|
|RAW_GND|holder1 negative, link_raw_ground|
|J1|fuse1 output, holder2 negative, link_junction1|
|J2|fuse2 output, holder3 negative, link_junction2|
|RAW_TOP|fuse3 output, link_raw_top|
|Three unfused branches|each holder positive directly to its own fuse pin1; no bypass|

Use F.Cu for the three short unfused holder-to-fuse links after rotation. Transition fused outputs through outside-pad via banks into B.Cu vertical rails beneath the insulated holder bodies. Route J1/J2 up separate corridors, joining each next-cell negative near its through-hole terminal; keep RAW_TOP separate. Route the upper four link connections across the approved B.Cu window at x15.2,33.2,51.2,69.2. Their3mm widths fit entirely within x9–77. No copper should cross the existing RF strip or any still-bare support/corner region. Bottom bridges atx26.4–29.6 and52.4–55.6,y0–2.2 remain untouched.

Do not start with blanket ground pours: there are multiple raw current potentials, and a generic GND plane can create an accidental fuse/shunt bypass on the primary. Use explicit named traces/polygons and DRC after fill. The companion needs no fill to establish a first complete deterministic hand route. Keep optional covered bottom-side fixture lands free of exposed pads/vias/test points; they do not prohibit masked tracks unless the next mechanical contract says so.

## Primary route priorities and candidate delta

ADI's guide requires small REG2/REG3 and CP bypass loops, separate unbranched Kelvin traces to the shunt's inner pad edges, a distinct GND return, and adequate balance-current trace width. It also recommends directing communication-line transient current away from the IC. Apply those constraints before minimizing total track length. The guide's example is a four-layer handheld pack, not evidence that this two-layer placement is automatically adequate. [MAX17320 pack implementation guide](https://www.analog.com/media/en/technical-documentation/user-guides/max17320-battery-pack-implementation-guide.pdf), pp3–6.

At the initial assessment, a concrete **canonical-unapplied** four-part alternative cuts the gauge/shunt span to roughly16–22mm without moving holders or FETs:

| Part | Candidate xy/rotation | Candidate courtyard |
|---|---|---|
|shunt|(47,4),0°|x43.05–50.95,y1.9–6.1|
|r_balance4|(73,4.5),90°|x71.85–74.15,y2.15–6.85|
|r_charge_gate|(51,1),0°|x50–52,y0.45–1.55|
|c_charge_gate|(51.6,7.1),0°|x50.65–52.55,y6.55–7.65|

The shunt has0.20mm courtyard-to-courtyard gap from fuse2; the moved gate capacitor has0.10mm to the charge-FET courtyard and0.10mm to holder2's courtyard. The gate resistor remains outside the lower support at that x. The relocated balance resistor is far from the gauge, but its upstream/balance connection can tolerate a longer trace more readily than a shared current-sense branch. At the initial assessment this candidate still required actual PCB replay/DRC and trace escape review. The dated checkpoint below records the completed work-only replay; it remains no proof that a 16–22 mm sense connection is sufficiently quiet.

Route order after placement decision: gauge bypass/EP; shunt Kelvin pair; FET common drain and gates; separate raw/PACK power trunks; balance sense/filter chain; NTC/I2C/alert. IC pin15 CSP must not attach directly to the adjacent same-net GND/EP copper before the shunt. Route all charger/motor negative current through the shunt, including any thermal/ESD connections that could otherwise bypass it.

## Assembly and validation consequences

- All SMD assembly is outward-facing. Holder insertion loads need the mechanical clamp/backing fixture; neither solder joints nor the0.2mm nominal holder-to-boss gap is validated.
- The opposed-board5mm gap contains a1mm barrier. All holder/solder-pad tails must stay within the1.5mm board-relative protrusion budget. Finish/cut/inspect soldered wiring before enclosing the two boards; cell insertion follows complete continuity/polarity verification with an appropriate controlled pack procedure.
- Wide power copper at holder and wire pads raises soldering heat demand. Use explicit qualified thermal spokes if required; their combined widths enter the voltage-drop calculation. Do not leave KiCad default reliefs as an unnoticed current choke.
- Keep raw link pads accessible before enclosure closure. The primary's protected harness fan and NTC wires need their already-allocated strain relief. Gauge/fuse settings, fuse clearing, holder ratings, reverse insertion, exact NTC attachment and failed-short isolation remain release gates.
- Clean the six fuse-edge silkscreens before manufacturing output. Current DRC findings are recorded, not waived.

## Derivative authority and next implementation

Use `hw/routing/blind-pack-companion/` for an explicitly experimental native KiCad10 board, project rules and route-source record. The canonical atopile layout remains the circuit/placement authority; do not send this routed derivative through the placement normalizer/replayer, both of which correctly reject copper. Record canonical PCB/parts/manifest/mechanical hashes and the only authorized deltas: three fuse rotations and the reviewed companion B.Cu support window.

Reuse the existing physical pin/net graph contract and outline/NPTH/side checks, but a route-aware variant must allow tracks/vias and validate their geometry against the mechanical contract, rather than stripping them. Require actual KiCad10 all-severity DRC on the final saved board, zero unconnected items, no shorts/clearance/keepout/edge/hole failures, and inspection of any filled zones (the first companion route can use no pours). Count crossings of the B.Cu window and reject pads/vias there. Record actual lengths/widths/necks and inspect fuse bypass paths in the copper connectivity, not only source net labels. No fabrication files or order will be issued from the experiment.

## Implementation checkpoint — 2026-10-20

The companion experimental route now crosses the coordinated, recessed B.Cu
window specified by mechanical contract SHA256
`bc67cfa48bf2719dd567bf6f0341244dfb0ad02026c8ea6d6882630177c0f330`.
Its exact implementation and current results are in
[`hw/routing/blind-pack-companion/`](../../hw/routing/blind-pack-companion/README.md).
There are 35 segments, 12 vias, no fills, and zero unconnected items in actual
KiCad 10 DRC. Six inherited silk findings remain. Explicitly enabled courtyard
checking additionally reports the four board-only mounting holes; those errors
are retained, not suppressed. The ten purchased-component outlines pass the
independent envelope checks. Physical current, thermal and insulation acceptance
remain open.

The four-part primary candidate above was replayed **only in a work copy**,
with SHA256 `0c1ec3f60c1a4e3f47c553e9ecbda98c719f3a78d631cb6d9d65058817fede6a`. Its actual DRC has
zero courtyard-overlap, keepout, copper, edge or hole violations, with the same
26 inherited silkscreen findings and 77 unconnected items as the unrouted
canonical capture. Parent review accepted these four moves for the next
experimental routing derivative only. Neither the canonical primary PCB nor
its anchors changed. The primary's current paths, Kelvin geometry, bypass
loops and assembly clearances still require route-aware implementation and
verification.
