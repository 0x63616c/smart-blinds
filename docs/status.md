# Progress

Updated 20 October 2026. [Public repository](https://github.com/0x63616c/smart-blinds).

**Prototype design in progress.** The enclosure, circuit captures and control software
are reviewable. The three boards remain unrouted; no unit has been fabricated,
powered, charged or installed. The next physical milestone is two prototypes,
followed by an eight-unit build only after their tests pass.

## Current design

| Area | Implemented and checked | Still required |
|---|---|---|
| Enclosure | 115 × 174 × 71 mm retained case; 72.2 mm maximum at buttons; removable six-cell cassette, controller supports, cable paths, adjustable buttons and replaceable motor-fit parts | Exact holder retention, internal wire fan, home-sensor mount, tolerances, strength, creep and assembly tests |
| Motor fit | Documented JGB37-520 family envelope with allowances; replaceable cradle and shaft adapter | Fit to the purchased Recfountik 111 RPM motor, encoder wiring, current, torque and load measurements |
| Main controller | 196 circuit features, 609 pin identities and 142 net partitions; native eleven-sheet KiCad schematic; 54 × 68.5 mm four-layer placement with USB tab | Route copper, refine critical loops, resolve manufacturing/thermal rules and ERC/DRC findings |
| Battery carriers | Two opposing 86 × 104 mm boards, six PCB holders, branch fuses, protected pack outputs, sensing and gauge | Routing, holder fastening, insulation and qualified protection settings |
| Control software | Physical-height calibration and coordinated preparation/commit/leases; bounded device motion session and settling; source-timed faults and supervised motor-off path | Physical reference/commissioning, final hardware qualification, idle local-button wake and installed radio tests |
| Home Assistant | Seven framework tests against HA 2026.10.2 using an authenticated simulator; shared physical height across different calibration maps | Bind the qualified real transport adapter to the live HA service |
| Radio transport | Pinned C6 Thread evaluation build; seven-peer localhost DTLS group adapter, durable sequence reservations and source-timed failure propagation | Compact radio protocol and airtime budget, commissioned identities/keys, RF power measurements and hub compatibility |
| Costs | Dated parts inventory and component demand for two/eight units, sourced harness candidates and a source-bound print-volume estimate | Final board/assembly quote, slicer-based filament use, hardware totals, shipping, tax and stock refresh |

The owner is away for several weeks. Design continues with the documented motor
family dimensions; an exact motor measurement is **not required to continue the
CAD study**. Fit-critical cradle/coupler parts remain replaceable and provisional.

## Latest verified checkpoint

[All ten Design checks jobs passed for `8975687`](https://github.com/0x63616c/smart-blinds/actions/runs/39376671584):
control/parameter tests, electrical models, native schematic rebuilds, Home Assistant,
real local transport tests, both C6 cross-builds, both mechanical-fit jobs and the
source-bound print material budget. The newer group bridge below awaits its own CI run.
New changes must be checked against their own source revision.

The retained-enclosure artifact contains 27 named empty-intersection checks, a
positive cleat-capture control and ten closed printable mesh types. Its seven CAD
source hashes match the checked source. The service tests include a conservative
2.5 mm cassette release and 72 mm forward removal envelope. These results establish
what the nominal model does; they do not establish printed fit or load capacity.
The 21 installed printed pieces total 320.167 cm³ per unit: about 406.61 g of
solid PETG at 1.27 g/cm³. This is a CAD estimate, before infill, supports and waste;
CI recalculates it from the freshly checked meshes.

The complete main native schematic independently matches the compiled PCB graph.
Seven explicit ERC findings remain documented. Main and carrier circuits also have
physical-pin contracts and injected-fault checks; the first placement checkpoint
preserves all circuit connections across normal and frozen builds.

All 256 electrical footprints across the three boards have clearance outlines
that contain their actual pads. The 45-family source review corrected 178 main,
30 primary and three companion instances. The larger envelopes required 13 small
main-board moves, six fuse moves and five small carrier-part adjustments; board
sizes and mechanical anchors are unchanged. Actual KiCad DRC reports zero
courtyard/keepout findings on all three boards. Four package families still use
explicit molding/outline allowances. Copper routing and the remaining manufacturing
findings are separate unfinished work. See the [clearance record](electrical/footprint-clearances.md).

The [host group bridge](firmware/thread-group-bridge.md) joins the coordinator to
seven real localhost DTLS sessions with synthetic motors and calibration records.
Its latest local batch passes 59 transport/schema/clock/bridge tests, including a
deliberate 30 ms control stall that verifies motor-off and lost reference. An earlier
batch had two intermittent timing failures; their exact cause remains unresolved,
and retained first-fault diagnostics now make a recurrence inspectable. No deadline
was relaxed or test retried automatically. This is a correctness fixture, not radio
qualification: about 109 kB/s of application bodies exceeds the intended Thread
PHY's raw capacity before overhead. Compact traffic and real-device timing remain
required before deployment or a battery-life claim.

## Decisions and limits that affect the build

- Group percentages select a shared **physical bottom-edge height** in the common
  reachable range. Equal percentages of each blind's individual travel are not used.
- Six Samsung 50E cells form one 3S2P pack per device. Cell inventory, condition and
  matched-pack suitability remain unverified.
- The 71 mm retained case requires holder tails and solder protrusion of no more
  than 1.5 mm. The untrimmed 78 mm comparison is not an implemented retained variant.
- The current drive shares radial load between the motor and an outboard bearing;
  it does not isolate the gearbox from chain force.
- The firmware defaults have no qualification records and do not configure motor or
  battery I/O. Charger tooling remains OFF-only; no cell or device has been programmed.
- Thread is not Matter. HomePod/Thread-border-router support and the Home Assistant
  network/commissioning path remain to be confirmed.
- The 60-day runtime target and 90-day stretch depend strongly on measured motor and
  standby current. At the current assumptions, 1.5 A moving current and 0.5 mA standby
  estimate about 57 days; 5 mA standby reduces that to about 25 days.
- Current component demand is **$363.08 for eight units** (about $45.38 each), excluding
  boards, assembly, cells, motors, cables, mechanics, shipping and tax. This is not a quote.
- USB transients, charge/protection behavior, regenerative energy, sustained back-drive,
  current limiting, thermal performance and fault clearing remain qualification gates.
  Simulation and datasheet calculations cannot prove the finished hardware works.

## Next work

1. Establish manufacturing rules and route/review critical power and sensing paths.
2. Finish holder retention, wiring details and a complete print/fastener budget.
3. Reduce group-control airtime and test the transport on actual C6 radios.
4. Complete all three routed boards, manufacturing outputs and an assembly quote.
5. Test two physical prototypes before committing to the eight-unit build.

The original e8s repository is preserved. Inherited PD12V6 designs are labelled
references: the USB-C PD-to-12.6 V board is not a battery charger or complete blind
controller. Archived architecture and validation claims are not authoritative for
this fresh design.

[Brief](brief.md) · [Verification plan](verification-plan.md) ·
[Assembly study](mechanical/retained-compact-enclosure.md) · [Shopping list](../bom/README.md)
