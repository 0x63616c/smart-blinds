# Parts and cost tracking

Budget for eight complete units: seven installations plus one spare. The first prototype gate uses two.

| Item | Per unit | Two prototypes | Eight total | Current status |
|---|---:|---:|---:|---|
| Samsung INR21700-50E cells | 6 | 12 | 48 | Owner has cells; count, condition and matching to verify |
| Recfountik JGB37-520 encoder motor, 12 V / 111 RPM | 1 | 2 | 8 | Archived purchase reports six; current inventory to verify |
| Integrated populated controller PCB | 1 | 2 | 8 | 190 components captured; placement/routing unfinished |
| Protected 3S2P pack assembly | 1 | 2 | 8 | Opposed holder carriers; 33 protection components captured |
| Printed enclosure/drive pieces | set | 2 sets | 8 sets | Four original packaging studies and provisional fit meshes available |
| Buttons, cables, terminals, fixings | set | 2 sets | 8 sets | Design dependent |

Count cells separately from pack construction to avoid double-charging their cost. Record existing
inventory separately from purchases still needed. Include USB charger/cable requirements, crimp
contacts/tools, insulation, strain relief, fasteners, wall anchors, filament and prototype waste.

For every electronic line record manufacturer part number, JLCPCB/LCSC part ID, quantity,
footprint, assembly class, stock date, unit cost and source. Do not infer assembly availability from
an LCSC retail listing. Compare complete quoted single-sided/economic and alternatives with setup,
stencil, feeder/loading, hand insertion, finish, shipping and tax shown separately. Prices are
estimates until a dated actual quote exists; no quote or order has yet been placed.

[Electronics cost sensitivity](electronics-cost.md) · [Dated component snapshot](electronics-sourcing-snapshot.json) ·
[Mechanical quantities](mechanical.md)

The owner prefers PCB-mounted cell holders to reduce assembly work. Compare a separate protected
holder carrier with holders on the main PCB and a welded pack. Holder contacts, retention, reverse
insertion, assembly fees and the extra interconnect must be included in this comparison.

## Captured electronic parts

The current main/controller and carrier graphs contain **223 components across
63 unique part numbers per device**. The dated catalog calculation gives
**$76.22 for two** or **$294.88 for eight** ($36.86 per device at eight) for
those captured parts only. This excludes fabrication, assembly/setup/feeders,
connectors and holders still being integrated, quantity rounding/attrition,
mechanics, cells/motors, shipping and tax. It is not the complete device price.

[Line-item CSV](captured-components.csv) · [Source and calculation evidence](captured-components.json).
Regenerate with `python3 bom/captured_components.py`; `--check` detects stale
board counts or catalog inputs. Demand is aggregated across the two captures;
separate assembly jobs may have different procurement prices and minimums.
