# Battery holder and carrier comparison

Status: user requested PCB-mounted holders, 2026-10-19. Prefer a separate protected carrier with one keyed controller cable. Holder current suitability and final geometry are not qualified.

| Construction | Assembly and service | Size/cost consequence | Main unresolved issue |
|---|---|---|---|
| Six holders on main controller PCB | One assembled board, no pack cable | At least the six-holder footprint plus motor/control/antenna regions; large expensive board replacement | Cells constrain RF, thermal layout and enclosure; removal leaves electronics exposed |
| Separate protected carrier, six holders on one face | Screw carrier into case; insert matched cells once; one keyed protected connector to controller | Broad shallow footprint; retains single-side assembly | Larger wall footprint, holder current qualification |
| Compact two-face carrier or two outward-facing three-holder PCBs | A compact removable protected cassette | Two-face SMT requires Standard; twin single-side TH boards add fixed insulated interconnect and mechanical parts | Opposing pin/peg clearance; raw group rails must remain inaccessible inside cassette |
| Welded 3S2P pack | Smallest cell envelope; one finished protected pack connection | Requires qualified pack assembly/spot welding and insulation; price not quoted | More assembly work; individual cells are not conveniently replaceable |

The controller connector should expose only protected PACK+, system GND, SDA, SCL and a separate two-wire charger thermistor. MAX17320, its shunt, high-side protection FETs, balancing, pack fuse and gauge thermistor stay with the cells. Protection must work while disconnected from the controller. No external loose cell-tap connector is proposed. The six-way assignment is an interface allocation, not a selected connector: contact rating, keying, sequencing and premade cable availability need review.

## Sourced holder candidates

| Part | Geometry from manufacturer drawing | JLC observation | Eight-device holder subtotal |
|---|---|---|---:|
| MYOUNG BH-21700-A5BJ001, C20606809 | TH,83±0.8 ×25±0.5mm body;15.6±0.5mm unloaded height;4±0.5mm tails | Economic and Standard, manual/wave;278 overseas,219 presale,min6;48-piece tier$1.2246 | $58.78, or$7.35/device |
| MYOUNG BH-21700-B1BJ001, C20606791 | SMT,82.5±0.8mm body;92.6±1.5mm tab span;25±0.5mm width;93.6mm land extent | Standard Only,2078 overseas,1938 presale,min10;$0.9079 | $43.58, or$5.45/device |
| Keystone1121 TH /1122 SMT | Manufacturer explicitly lists20700/21700; nylon UL94V-0 | Current JLC assembly eligibility and purchase price not verified | Unpriced alternative |

The [dated sourcing snapshot](../../bom/electronics-sourcing-snapshot.json) records public metadata; overseas stock is not in-house allocation. [A5 manufacturer drawing](https://datasheet.lcsc.com/datasheet/pdf/ea18f085f5f9b6da9d587816ecf7f47a.pdf), [B1 manufacturer drawing](https://datasheet.lcsc.com/datasheet/pdf/f19fdde684eed5e7f56342763817f937.pdf), [Keystone1122](https://www.keyelco.com/product.cfm/product_id/14551). Body height excludes the protruding loaded cell; use a complete loaded-holder envelope.

JLC lists THT work at$3.50/order plus$0.0173/joint in its September FAQ. Six two-pin holders ×8 devices =96 joints, giving$5.1608/batch or$0.6451/device, before extra board setup/parts. Its October cost article has slightly different exchange-rate-adjusted fees; obtain an actual quote. THT does not automatically force Standard, while the observed SMT holder itself is Standard Only. Do not charge a feeder fee to each individual holder; THT pricing is separate. A two-board design adds setup and may duplicate feeder fees. [Assembly FAQ](https://jlcpcb.com/help/article/pcb-assembly-faqs), [October fee explanation](https://jlcpcb.com/blog/reduce-pcb-assembly-cost-prototype).

## Electrical acceptance criteria

Both MYOUNG drawings specify100mΩ maximum contact resistance without an ampere rating or clear whole-holder versus per-contact definition. **This is not evidence of suitability for this motor.** At3A pack current with perfect sharing, each of six holders carries1.5A. If100mΩ is a complete holder path, the total is6×1.5²×0.1 =1.35W. If it applies to each of two contacts, total is2.7W. With one missing/poor-contact parallel cell, the remaining holder carries3A and dissipates0.9–1.8W. Thus a holder cannot be rated from an ideal1.5A sharing assumption. Verify contact drop, heating, spring relaxation, vibration, insertion cycles and loaded voltage sag using bounded test loads. Include aged/contaminated contacts and the missing-cell case.

Parallel-cell equalization occurs upstream of the pack FETs, so the gauge cannot stop an insertion surge between mismatched cells. A cell-level fuse can limit fault energy but does not establish safe insertion current. Before cells are paralleled, verify exact chemistry/condition and close open-circuit voltage matching using an approved assembly procedure. Do not offer this as a drop-in-any-cell pack. Service means USB unplugged, controller disconnected and the whole carrier removed; do not replace one live parallel cell in the installed product. Recessed positive contacts/reverse-insertion blocking must be physically verified with the actual flat-top cells, plus conspicuous polarity marks inside the service area. A printed cradle must retain the cells and carry insertion forces to case screws rather than relying on solder pads.

Preferred direction is a protected carrier because it simplifies the user's final assembly while preserving a compact independently testable controller. Compare the broad single-face and compact twin-board cassette mechanically before selecting the outline. The previously modeled bare-cell welded pack remains the size baseline, not an accepted holder model.
