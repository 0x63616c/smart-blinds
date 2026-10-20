# Drive prototype reference parts

Dated source check: 2026-10-19. USD manufacturer list prices, excluding tax, shipping and discounts. This is a research BOM, not a purchase instruction or eight-unit release. Commercial robotics hardware provides documented envelopes; the compact direct-support candidate avoids much of this cost.

| Item | Manufacturer reference | Per device | For eight | Price basis |
|---|---|---:|---:|---:|
| Flexible 6-to-6 mm coupling | [goBILDA 4002-0006-0006](https://www.gobilda.com/4002-series-flexible-clamping-shaft-coupler-6mm-round-bore-to-6mm-round-bore/) | 1 | 8 | $6.99 each |
| Flanged bearing, 6×14×5 mm | [goBILDA 1611-0514-0006](https://www.gobilda.com/1611-series-flanged-ball-bearing-6mm-id-x-14mm-od-5mm-thickness-2-pack/) | 2 | 8 packs of 2 | $3.99 / pair |
| 6 mm D shaft, 70 mm | [goBILDA 2101-0006-0070](https://www.gobilda.com/6mm-d-shaft-stainless-steel-70mm-length/) | 1 | 8 | $3.59 each |
| 6 mm clamping collar | [goBILDA 2910-0919-0006](https://www.gobilda.com/2910-series-aluminum-clamping-collar-6mm-id-x-19mm-od-9mm-length/) | 2 | 16 | $4.49 each |
| 6 mm ID, 8 mm OD, 2 mm spacer | [goBILDA 1521-0008-0020](https://www.gobilda.com/1521-series-6mm-id-spacer-8mm-od-2mm-length-4-pack/) | 2 | 4 packs of 4 | $2.29 / 4 |
| 6 mm ID, 9 mm OD, 1 mm shim | [goBILDA 2807-0609-1000](https://www.gobilda.com/shaft-spacers-shims) | 2 | 2 packs of 12 | $2.49 / 12 |

This purchased shaft stack is **$25.11 per device at prorated pack prices, or $202.54 for eight after pack rounding**, before screws, printing and delivery. These prices are a comparison, not an optimized quote. The coupling page does not state a torque or insertion-depth limit, and the bearing page does not state a load rating. Those are open qualifications.

The collar drawing has a 19 mm body, **22.6 mm screw sweep**, 9 mm body length and 0.5 mm axial boss. The coupling drawing has a 20 mm body and 23 mm screw sweep. The CAD includes these distinctions; a body-diameter-only collision check would be insufficient.

| Prototype fastener | Per device | Purpose |
|---|---:|---|
| M3×10 socket screw | 4 | Motor lower clamps to base |
| M3×12 socket screw | 4 | Motor upper clamp halves |
| M3×12 socket screw | 4 | Bearing blocks to base |
| M3×10, 90° countersunk screw | 4 | Bearing retainers; recessed to clear rotating collars |
| M3×12 socket screw | 4 | Guard to bearing blocks |
| M3 hex nut | 21 | Twenty structural positions plus wheel grub-screw nut |
| M3×6 grub screw | 1 | Wheel against 5.5 mm D-shaft flat |
| Cartridge-to-enclosure fasteners | 4, length pending | Final backplate interface not frozen |

Check actual screw-head/nut dimensions against printed coupons and the selected standard. A washer, locking method or insert can alter length and clearance. The list is for the cartridge source, not a complete product BOM.

The compact shared-shaft candidate instead uses an 8 mm printed wheel, one **NSK MR106ZZ1-family 6×10×3 mm bearing**, its printed pod/retainer and a guard. [NSK's miniature bearing catalog](https://www.nsk.com/common/data/ctrgPdf/bearings/e126h.pdf) is the dimensional reference; exact suffix, distributor availability and price are not yet quoted. Do not substitute the open MR106, which the current NSK product page lists at 2.5 mm width. The motor shaft itself and its gearbox bearings still carry part of the chain load. No complete low-cost BOM is claimed yet.
