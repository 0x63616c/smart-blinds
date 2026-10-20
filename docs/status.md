# Progress

Updated 20 October 2026. [Public repository](https://github.com/0x63616c/smart-blinds).

**Prototype design in progress.** The enclosure, circuit captures and control software
are reviewable. An experimental companion-carrier board is connected, and the primary carrier
has its power and isolated current-sensing routes; the canonical captures remain
unrouted. No unit has been fabricated,
powered, charged or installed. The next physical milestone is two prototypes,
followed by an eight-unit build only after their tests pass.

## Current design

| Area | Implemented and checked | Still required |
|---|---|---|
| Enclosure | 115 × 174 × 71 mm retained case; 72.2 mm maximum at buttons; removable six-cell cassette, controller supports, cable paths, adjustable buttons and replaceable motor-fit parts | Exact holder retention, internal wire fan, home-sensor mount, tolerances, strength, creep and assembly tests |
| Motor fit | Documented JGB37-520 family envelope with allowances; replaceable cradle and shaft adapter | Fit to the purchased Recfountik 111 RPM motor, encoder wiring, current, torque and load measurements |
| Main controller | Native eleven-sheet schematic and partial four-layer power route; 537 segments, 162 vias, 64 physical connection groups, preserved circuit and mechanical anchors | 275 unconnected items; finish local loops and current/signal routing, thermal/process review and ERC/DRC |
| Battery carriers | Two opposing 86 × 104 mm boards, six PCB holders, branch fuses, protected pack outputs, sensing and gauge | Complete primary/main routing, holder load path, insulation and qualified protection settings |
| Control software | Physical-height calibration and coordinated preparation/commit/leases; bounded device motion session, settling and portable local ownership; Wi-Fi binding with raw button STOP/wake and physical OFF checks | Physical reference/commissioning, local endpoint gestures, final hardware qualification and installed radio tests |
| Home Assistant | Seven framework tests against HA 2026.10.2 using an authenticated simulator; shared physical height across different calibration maps | Bind the qualified real transport adapter to the live HA service |
| Radio transport | C6 Wi-Fi automatic-light-sleep evaluation and separate default-unqualified motion target; six real localhost DTLS tests; Thread target and seven-peer group adapter remain | Actual RF/power tests, physical qualification, temperature continuity, commissioned configuration and unattended recovery |
| Costs | Dated parts inventory and component demand for two/eight units, sourced harness candidates and a source-bound print-volume estimate | Final board/assembly quote, slicer-based filament use, hardware totals, shipping, tax and stock refresh |

The owner is away for several weeks. Design continues with the documented motor
family dimensions; an exact motor measurement is **not required to continue the
CAD study**. Fit-critical cradle/coupler parts remain replaceable and provisional.

## Latest verified checkpoint

[All twelve Design checks jobs passed for `25c4c01`](https://github.com/0x63616c/smart-blinds/actions/runs/39393679149),
including the charger-distribution extension's nineteen injected failures,
seventeen portable firmware targets, the C6 gauge adapter, and the separate
Wi-Fi motion target's default/bench builds against the pinned real SDK.
Its [source-generated previews also passed](https://github.com/0x63616c/smart-blinds/actions/runs/39393679663).

The new [portable local ownership core](firmware/local-ownership.md) passes
all eighteen host targets, the same suite under ASan/UBSan, 59 native transport,
clock, motion and group-bridge checks, and pinned C6 Wi-Fi default/bench and
Thread cross-builds locally. Its next published CI run remains pending.
One executor owns local and remote motion, with fresh single-use local intents,
independent internal epochs and actual OFF readback at admission and handoff.
C6 applications still provide raw button STOP only; physical gesture/admission
wiring and qualification remain unfinished. Exact dependency pins and
modified-source rejection remain enforced.

The retained-enclosure artifact contains 35 named empty-intersection checks, a
positive cleat-capture control and ten closed printable mesh types. Its seven CAD
source hashes match the checked source. The service tests include a conservative
2.5 mm cassette release and 72 mm forward removal envelope. These results establish
what the nominal model does; they do not establish printed fit or load capacity.
The 21 installed printed pieces total 321.975 cm³ per unit: about 408.91 g of
solid PETG at 1.27 g/cm³. This is a CAD estimate, before infill, supports and waste;
CI recalculates it from the freshly checked meshes. A separate three-piece
workshop fixture adds about 122.84 g once for the eight-unit build. Its three
clearance checks and closed print meshes pass; holder contact, insertion forces
and the complete wired-pack loading sequence remain unqualified.

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

The [experimental companion route](../hw/routing/blind-pack-companion/README.md)
preserves the circuit graph, footprint pads and mechanical anchors. It has 35
segments, 12 vias and zero unconnected items in actual KiCad DRC, with no copper,
edge, hole, courtyard-overlap or keepout failures. Six inherited silkscreen
findings and four explicitly enabled mounting-hole courtyard errors remain.
Four injected failures are rejected. Covered inward-face tracks pass through a
coordinated 0.3 mm spacer recess; current, temperature and insulation wear remain
physical qualification gates.

The [partial primary route](../hw/routing/blind-pack-primary/README.md) has 102
segments and 32 vias. Its ten current-path groups and two separate shunt-sense
branches pass physical copper-shape checks, including deliberate shortcut/open
failures. Actual KiCad DRC has no copper, edge, hole, keepout or overlap failures,
but retains 55 unconnected signal/bypass items, 26 silk findings and four mounting
hole courtyard errors. Its conservative copper-only loss estimate is 1.73 W at
4 A pack current; width, parallel-layer and 2 oz alternatives need review. The
primary and main routes remain unfinished.

The [partial main power route](../hw/routing/blind-main/README.md) preserves all
196 footprints, the 609-pin/142-net graph, 17 mechanical/thermal anchors and 13
reservations. Its 537 segments and 162 vias connect 64 checked copper groups,
including local charger/motor/regulator paths, radio power, USB input/CC/bypass
connections, negotiated-enable/divider/discharge chains, the charger input and
PMID/SYS capacitor banks, and ground return. Nineteen injected geometric/copper
failures are rejected, including same-net via-to-solder-land intrusion. All 38 new
distribution vias retain a 0.20 mm drill-to-solder-land margin.
Actual DRC retains 275 unconnected items, 260 silk/text findings, four library differences and five
footprint-type findings. This is a reproducible partial checkpoint; critical-loop,
current/thermal, USB, supervisory and full-routing work remain.

The CAD checks now use the twelve actual primary wire-pad positions and remove
the central support that would intersect their solder tails. Corner supports,
the perimeter and separate barrier remain; 0.5 mm nominal tail clearance still
needs tolerance and assembly qualification.

The new [Wi-Fi evaluation](firmware/wifi-evaluation.md) passes its full pinned C6
build, all twelve portable test targets and six actual localhost DTLS tests.
It uses existing encrypted configuration, authenticated ownership and bounded
awake periods; its default image joins no network, and configured outputs stay
held OFF. It has no motion worker or physical qualification. Automatic light
sleep leads the radio comparison, with Thread retained as a separate target.
The radio-only 1.5-second preflight aim does not yet include the current
2.8–4-second temperature-monitor warmup. A separately tested, default-unqualified
[gauge continuity model](firmware/gauge-continuity.md) preserves measurement history
across qualified MCU light sleep while requiring a complete fresh guarded read.
The read-only C6 bus adapter brings the suite to sixteen passing portable
targets in CI, including task/epoch loss at all 52 read positions and both
disabled and enabled build gates. Pinned C6 builds also pass, including the
normally excluded attachment branch compiled separately against the real SDK.
No application instantiates the adapter. Local response and physical conversion continuity still require
qualification.

The separate [Wi-Fi motion target](firmware/wifi-motion.md) binds authenticated
requests to the existing owned control runtime. Raw button STOP precedes ADC
sampling; revocation and request generations prevent stale readiness or parking
reports from surviving a disconnect or newly queued command. Physical OFF
readbacks and independent control power locks govern sleep. The eighteen-target
portable suite passes locally, as do pinned default/bench C6 builds and the
existing Thread target after the shared runtime changes. The application supplies
empty qualification records, so it cannot initialize motor I/O or establish a
physical reference. It has no local endpoint gesture, charge-enable, commissioning
or OTA path. The gauge continuity adapter remains separate.

The [host group bridge](firmware/thread-group-bridge.md) joins the coordinator to
seven real localhost DTLS sessions with synthetic motors and calibration records.
Its latest local batch passes 59 transport/schema/clock/bridge tests, including a
deliberate 30 ms control stall that verifies motor-off and lost reference. An earlier
batch had two intermittent timing failures; their exact cause remains unresolved,
and retained first-fault diagnostics now make a recurrence inspectable. No deadline
was relaxed or test retried automatically. This is a correctness fixture, not radio
qualification: about 109 kB/s of application bodies exceeds the intended Thread
PHY's raw capacity before overhead. That result informed the Wi-Fi-first evaluation; real-device timing and power
measurements remain required before deployment or a battery-life claim.

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
- Wi-Fi is the leading evaluation path. Thread remains a separate fallback study;
  HomePod/Thread-border-router compatibility has not been established.
- The 60-day runtime target and 90-day stretch depend strongly on measured motor and
  standby current. With 1.5 A motor-branch current, an assumed 150 mA awake MCU/radio at 3.3 V
  and 0.5 mA whole-pack standby, the updated energy scenario estimates about
  55.6 days. It is a planning calculation, not a measured runtime.
- Current component demand is **$363.08 for eight units** (about $45.38 each), excluding
  boards, assembly, cells, motors, cables, mechanics, shipping and tax. This is not a quote.
- USB transients, charge/protection behavior, regenerative energy, sustained back-drive,
  current limiting, thermal performance and fault clearing remain qualification gates.
  Simulation and datasheet calculations cannot prove the finished hardware works.

## Next work

1. Establish manufacturing rules and route/review critical power and sensing paths.
2. Finish holder retention, wiring details and a complete print/fastener budget.
3. Complete temperature continuity, C6 local gesture/admission wiring and commissioning, then test actual C6 timing/power.
4. Complete all three routed boards, manufacturing outputs and an assembly quote.
5. Test two physical prototypes before committing to the eight-unit build.

The original e8s repository is preserved. Inherited PD12V6 designs are labelled
references: the USB-C PD-to-12.6 V board is not a battery charger or complete blind
controller. Archived architecture and validation claims are not authoritative for
this fresh design.

[Brief](brief.md) · [Verification plan](verification-plan.md) ·
[Assembly study](mechanical/retained-compact-enclosure.md) · [Shopping list](../bom/README.md)
