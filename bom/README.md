# Parts and cost tracking

The current [component ledger](captured-components.json) totals **$99.27 for two sets or $379.94 for eight**, including both battery carriers, from 19–20 October 2026 catalog observations. These are component-demand totals, excluding boards, assembly/setup/feeder fees, procurement minimums, cells, motors, mechanics, cables, shipping and tax. Stock, assembly eligibility and the completed manufacturing package still need verification.

Budget for eight complete units: seven installations plus one spare. The first prototype gate uses two.

| Item | Per unit | Two prototypes | Eight total | Current status |
|---|---:|---:|---:|---|
| Samsung INR21700-50E cells | 6 | 12 | 48 | Owner has cells; count, condition and matching to verify |
| Recfountik JGB37-520 encoder motor, 12 V / 111 RPM | 1 | 2 | 8 | Archived purchase reports six; current inventory to verify |
| Integrated populated controller PCB | 1 | 2 | 8 | 204 purchased parts placed; routing unfinished |
| Protected 3S2P pack assembly | 1 | 2 | 8 | Two holder carriers; 39 purchased parts captured |
| Printed enclosure/drive pieces | 22 | 44 | 176 | Current v2 candidate; 21 shapes, physical fit untested |
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

The main controller and two holder-carrier graphs contain **243 purchased
components across 71 unique part numbers per device**. The dated catalog calculation
gives **$99.27 for two** or **$379.94 for eight** ($47.49 per device at eight).
This includes six holders, six branch fuses and captured board connectors per unit.
Bare solder landings are explicitly excluded from purchased quantities.

These are raw component-demand costs only. Fabrication, assembly/setup/feeders,
wire harnesses, procurement rounding/attrition, mechanics, cells/motors, shipping
and tax remain outside this total. It is not the complete device price.

[Line-item CSV](captured-components.csv) · [Source and calculation evidence](captured-components.json).
Regenerate with `python3 bom/captured_components.py`; `--check` detects stale
board counts or catalog inputs. Demand is aggregated across three captures;
separate assembly jobs may have different procurement prices and minimums.

## Current printed parts and hardware

Use the [v2 inventory](../cad/enclosure-v2/inventory.md) and
[print list](../cad/enclosure-v2/print-list.csv). The 22 installed pieces total
369.23935 cm³ of solid geometry per unit. At the recorded PETG density this is
468.9 g per unit, or 3.751 kg for eight; it is not a slicer or filament-purchase
estimate. Perimeters, infill, supports and waste remain to be selected.

Two cosmetic plugs per blind are optional. One button assembly nest is shared
tooling. The earlier eight-piece battery-loading fixture is separate and has
not been requalified for the revised cable restraint. Do not add the historical
case's installed-piece budget to this one. Cable lengths, fasteners and cut
insulation are listed with their outstanding fit and sourcing limits.
