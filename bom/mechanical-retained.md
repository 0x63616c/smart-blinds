# Retained enclosure additions

This supplements [the compact drive/button BOM](mechanical-compact.md). It is a
digital prototype allocation, not a purchasing or fabrication release. Electrical
parts, carrier PCBs, holders, cells and the final harness remain in the electrical
BOM. Exact supplier quotes are still needed; do not turn nominal hardware
dimensions into an asserted total project cost.

| Hardware | Per unit | Eight units | Purpose / modeled dimensions |
|---|---:|---:|---|
| M3×60 ISO4762 socket screws | 4 | 32 | Independent cassette closure; 5.5 mm head diameter, 3 mm head height |
| M3×10 ISO4762 socket screws | 4 | 32 | Front cover; in addition to existing drive screws |
| M3×6 ISO4762 socket screws | 1 | 8 | One accessible cassette lock screw; two integral printed cleats carry the lower attachment |
| M3×6 ISO10642 countersunk screws | 2 | 16 | Controller-frame feet; heads flush below the Z8 PCB edge |
| M3 ISO4032 hex nuts | 11 | 88 | Four cassette, four cover, three mounting nuts; pockets reserve 6.6 mm circumscribed diameter / 2.8 mm height |
| M2.5×8 ISO4762 socket screws | 2 | 16 | Controller edge clamps; same length as existing bearing-retainer screws |
| M2.5 ISO4032 hex nuts | 2 | 16 | Controller frame; inspect actual nut height against its 2 mm pocket |
| M2×6 ISO4762 socket screws | 2 | 16 | Adjustable button tips; additional to the two existing guide-bar screws |
| M2 ISO4032 hex nuts | 4 | 32 | One captive nut and one jam nut per adjustable button |
| Nylon cable ties, nominal 100 × 2.5 mm | 4 | 32 | Two protected pigtail ties and two inline motor-connector tray ties; actual locking head and pull/insulation qualification required |
| 1.0 mm unclad insulating sheet | 1 cut shape | 8 | Approx. 83 × 101 mm blank; electrical/temperature material specification not yet frozen |
| M4 flat washers, maximum 9 mm outside diameter | 3 | 24 | Fit 10 mm wall recesses; combined washer + screw-head height ≤5.0 mm under the revised central cassette pocket |
| Wall screws and anchors accepting approx. 4 mm screw shank | 3 sets | 24 sets | Wall-specific selection and proof load required; 4.8 mm slotted plate holes and combined head/washer height ≤5.0 mm |

The retained exporter supplies ten printed types: backplate, cover, cassette
rear, cassette front with inline-connector tray, cassette spacer, controller
frame, controller edge clamp, adjustable button plunger, cosmetic button face,
and revised rear guide bar. Print two clamps, two plungers and two faces: **13
retained pieces per unit**. Reuse the eight compact drive types (four clamp
halves, bearing pod, bearing retainer, wheel and guard), giving **18 file types /
21 printed pieces per unit**, or **168 pieces for eight units**, plus the separate
insulating sheets. Do not reuse the earlier fixed plunger or guide bar. The
retained source implements only the 71 mm trimmed-pin variant.

The integrated holder end-comb ribs add no installed parts or screws. A separate
reusable service-fixture candidate adds **three workshop print pieces and four
M3×30 screws/four M3 nuts per fixture**, shared across the build rather than
multiplied by eight. Its fit, load path and final cell-insertion sequence remain
unqualified; it is excluded from the installed-piece count and unit mass below.
Its checked solid model is **122.84 g of PETG**; see the separate
[workshop volume table](mechanical-workshop-volume.csv).

The checked meshes total **322.271 cm³ per unit**, equivalent to **409.28 g of
fully solid PETG**, or **3.274 kg for eight** at the [Prusament PETG data sheet's
1.27 g/cm³ density](https://prusament.com/wp-content/uploads/2022/10/PETG_Prusament_TDS_2021_10_EN.pdf).
The reproducible [per-part volume table](mechanical-print-volume.csv) and
[estimate evidence](mechanical-print-estimate.json) bind this calculation to
the checked source and STL hashes. This is not a slicer prediction or a filament
purchase quantity: infill, supports, brims, purge and failed prints change usage.
Purchased parts and the separate insulating sheet are excluded. The cover and
wall plate dominate this initial printed volume; structural weight and print-time
optimization remain work for the prototype design.

The cassette has 4 long closure screws, two integral cleats and 1 separate mounting screw. Cell
insertion/removal is controlled service, not a routine battery swap. The main
benefit of the holders is avoiding welding or soldering cells; the extra cassette
hardware and 96 lead-trimming/inspection operations across eight units remain
real assembly work. No free factory trimming or harness assembly is assumed.

The 96 trimming operations are the holder leads alone. The retained candidate
uses a permanent protected pigtail rather than an opposed carrier header, so it
adds no pack-connector tails to that stack. All remaining opposed features still
must satisfy the 1.5 mm envelope. The controller's Micro-Fit tails sit in an open
frame region and require their own actual board/print clearance check.

The Molex 2147561061 pigtail supplies one finished six-way connector and six loose
ends. It avoids owner crimping; it does not avoid identifying and permanently
terminating those six protected wires, or securing two cable ties. Its electrical
BOM and priced assembly alternatives belong in the electrical sourcing record.
The inline motor pair and encoder cable are in the electrical harness sourcing record. The exact inline male housing variant, signal cable route retention and optional home-sensor mount remain qualification/design work.

Fastener dimensions are nominal standards-based allocations. Verify purchased
heads, nut thicknesses, screw length tolerances and a suitable locking method.
Do not force screws into cells, contacts or PCB copper. Printed strength and
temperature performance remain prototype qualification gates.
