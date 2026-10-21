# Progress

Updated 21 October 2026. [Public repository](https://github.com/0x63616c/smart-blinds).

**Prototype design in progress.** The enclosure, circuit captures and control software
are reviewable. Both experimental battery-carrier routes are fully connected;
the main controller route is partial and the canonical circuit captures remain
unrouted. No unit has been fabricated,
powered, charged or installed. The next physical milestone is two prototypes,
followed by an eight-unit build only after their tests pass.

**Current layout: [54 × 80 mm source-driven controller](../hw/routing/clean-main/).**
The larger draft has 206 gridded footprints, outward-facing connectors, rounded
corners, black mask and sparse markings. The current capture and eleven-sheet
schematic agree on 649 physical pin identities. Normal and frozen builds preserve
the reviewed placements and corrected watchdog/eFuse lands.

The partial route contains 516 segments and 120 vias. Its native saved board has
352 open connections and three explicitly retained hybrid-footprint type findings;
no library, copper-clearance, courtyard, silkscreen or keepout findings were added.
The reviewed USB-C input protection, local power/PD routes, finite return copper,
model contents/transforms and mechanical/RF reservations are checked on actual
saved geometry. See the [source and routing review](reviews/2026-10-21-clean-layout/source-driven-route.md).
These checks are not current, thermal, surge, RF or physical qualification.

The maintained emitter starts from the current unrouted capture and explicit
per-part/routing records. The old 196-part 54 × 68.5 mm route remains historical;
its passing checks are not reused as acceptance of this layout. The controller checkpoint
[`51cd391` passed all thirteen design checks](https://github.com/0x63616c/smart-blinds/actions/runs/39605316054),
and CI published its refreshed README gallery. The consolidated enclosure candidate below is now included; its
Linux rebuild is a separate check, not inherited from the earlier case.

Local native KiCad automation now runs through the
[isolated Linux runner](../tools/kicad-linux/README.md), following a macOS
embedded-Python crash. Load/save-copy, DRC and rendering succeeded while the
canonical board stayed unchanged; six live isolation probes and six host fault
tests pass. This avoids the crashing host automation path without claiming the
underlying KiCad defect is repaired. Model review also found that paired WRL and
STEP files have different origins. The first offset candidate was rejected;
corrections must be verified against the exact model used by the viewer.

## Current design

| Area | Implemented and checked | Still required |
|---|---|---|
| Enclosure | [Current 118 × 196 × 77 mm package](mechanical/enclosure-v2.md), inward PCB, 22 installed printed pieces and 17 source-bound local geometry checks; four original overlap controls retained. | Physical motor/holder fit, print strength, cable restraint, loaded handling and optional home-sensor path. |
| Motor fit | Documented JGB37-520 family envelope with allowances; replaceable cradle and shaft adapter | Fit to the purchased Recfountik 111 RPM motor, encoder wiring, current, torque and load measurements |
| Main controller | Source-driven 54 × 80 mm four-layer partial route: 206 parts, 649 pins, 516 segments, 120 vias; native schematic and corrected lands reconciled | 352 open connections and three retained hybrid type findings; finish remaining power/signal routing and qualify current, thermal, transient and manufacturing behavior |
| Battery carriers | Two opposing 86 × 104 mm boards, six PCB holders, branch fuses, protected pack outputs, sensing and gauge | Complete main routing, carrier electrical/thermal review, holder load path, insulation and qualified protection settings |
| Control software | Physical-height calibration and coordinated preparation/commit/leases; bounded device motion session, settling and portable local ownership; Wi-Fi binding with raw button STOP/wake and physical OFF checks | Physical reference/commissioning, local endpoint gestures, final hardware qualification and installed radio tests |
| Home Assistant | Nine HA 2026.10.2 framework tests pass locally and in CI, including authenticated HTTP/DTLS diagnostics; simulator retains shared physical height across different calibration maps | Sole physical movement owner, periodic idle gauge policy and hardware qualification |
| Radio transport | C6 Wi-Fi automatic-light-sleep evaluation and separate default-unqualified motion target; six real localhost DTLS tests; Thread target and seven-peer group adapter remain | Actual RF/power tests, physical qualification, temperature continuity, commissioned configuration and unattended recovery |
| Costs | Dated parts inventory and component demand for two/eight units, sourced harness candidates and a source-bound print-volume estimate | Final board/assembly quote, slicer-based filament use, hardware totals, shipping, tax and stock refresh |

The owner is away for several weeks. Design continues with the documented motor
family dimensions; an exact motor measurement is **not required to continue the
CAD study**. Fit-critical cradle/coupler parts remain replaceable and provisional.

## Earlier published checkpoints

[All thirteen Design checks jobs passed for `0a148d2`](https://github.com/0x63616c/smart-blinds/actions/runs/39429106462),
including the battery/source telemetry path through Home Assistant, monitored-PD
circuit/runtime, both carrier routes, the partial
main route, mechanical assemblies and material estimate, all 23 host firmware
targets and pinned real-SDK builds. The five battery-energy checks also pass.
The [source-generated previews from `8e57dc4` passed](https://github.com/0x63616c/smart-blinds/actions/runs/39498320367).
All 34 entries were reviewed after publication in `2e14978`: 247 input-file,
52 output-file and 125 locally available model-file hashes match. The four
external KiCad library model hashes are unchanged from the previously verified
`b6e2558` publication; those library files were not reopened in this check. Actual KiCad
images show the specified black board finish.
Preview publication revalidates source inputs
when another commit arrives during rendering.

The subsequent [parked telemetry implementation](firmware/parked-telemetry.md)
passes an independent fresh local run of all 23 host targets, 12 native
DTLS/HTTP checks and nine Home Assistant framework tests. The physical-mode
integration presents battery, USB and charging diagnostics from the original
observations; HTTP refresh cannot make old battery data fresh. It provides no
physical movement controls yet. The candidate also passed focused sanitizers,
39 existing transport regressions and pinned default/bench C6 builds.
CI builds both the telemetry fixture and a client-only library, verifying
that synthetic peer symbols do not enter the latter. All thirteen jobs passed
in the run linked above, including the actual default/bench C6 builds.

The subsequent [motion-to-idle correction](firmware/motion-handoff.md) passes
an independent fresh build of all 23 host targets. The normal C6 worker test
forces both diagnosed ingress orderings, including a message arriving during
a successful charger read. A control-owned OFF transaction keeps ordinary
movement requests queued until sensing finishes; Stop and fault handling
continue. Seven held-event cases and four restored-bug controls cover the
boundary. Focused sanitizers and both pinned default/bench builds also pass.
The original 22/23 failure and its diagnosis remain preserved. In
[CI for this correction](https://github.com/0x63616c/smart-blinds/actions/runs/39498320401),
twelve jobs passed, but the control job reached its ten-minute limit while running
`c6_runtime_owner_tests`. The subsequent
[sensor-request lifetime correction](firmware/sensor-request-lifetime.md)
addresses a deterministically reproduced lost wake request and a test-assertion
shutdown deadlock. All 24 host targets pass in Linux and an independent fresh
macOS build; focused sanitizers and both pinned C6 builds also pass. Actual OFF
age and motion timing limits are unchanged. In the
[fresh CI run for `313c35d`](https://github.com/0x63616c/smart-blinds/actions/runs/39502050091),
the control job passed and twelve of thirteen jobs succeeded. The transport job
failed in a seven-peer test with an I/O timing fault; diagnosis is isolated from
production timing limits. The original timeout log does not reveal its first
assertion. The last thirteen-job success above remains the earlier checkpoint.
Physical movement controls in Home Assistant and hardware qualification remain
unfinished.

The following [diagnostic-only fixture checkpoint, `3ae5c76`](https://github.com/0x63616c/smart-blinds/actions/runs/39542952966),
retains production timing limits and adds first-failing-operation evidence.
Eleven of thirteen jobs pass. The control job fails at the handoff-request test;
the transport job passes 61 of 62 tests but a group peer rejects an operation as
invalid. Its executor/I/O diagnostic fields are zero, so this failure is not
evidence of the earlier I/O overrun. Both failures remain under investigation;
the earlier all-green run is not presented as current-head validation.

The subsequent [ordered timestamp fixture correction](firmware/transport-timing-diagnostics.md#ordered-request-observations-in-the-host-fixture)
fixes ten calls whose receive/send clock reads had unspecified evaluation order.
Both the candidate and a fresh owning-checkout runtime test pass once; a reversed
capture control fails as expected. The actual radio handler and production
timing limits are unchanged. Fresh CI and the separate transport rejection
were still open at that checkpoint. The subsequent
[CI run for `7b2264f`](https://github.com/0x63616c/smart-blinds/actions/runs/39546114350)
passed all thirteen jobs, including transport and all four embedded builds.
The historical rejection's exact guard remains unknown.

A separate [inbox/cycle-clock regression](firmware/transport-timing-diagnostics.md#inbox-publication-and-cycle-time)
reproduces a fresh command being consumed against a timestamp captured before
it arrived. Copying one eligible command before sampling cycle time fixes that
ordering while retaining STOP priority, queue bounds and every timing limit.
The owning checkout passes all 24 host targets on its first run; candidate
sanitizers and deliberate restored-bug controls also pass. Fresh CI for this
production correction has now [passed all thirteen jobs at `33cc04a`](https://github.com/0x63616c/smart-blinds/actions/runs/39547483287),
including transport and all four embedded builds. No hardware timing is yet qualified.

Native populated-PCB export exposed a [confirmed enclosure orientation error](mechanical/pcb-orientation-review.md):
the old allocation reflected the component side. The current preview and the
joint-service study therefore do not establish physical PCB fit, despite their
passing modeled-volume checks. The correction keeps PCB copper and local anchors
unchanged and places components inward with a proper rotation. Frame, button,
connector, wire and service-path checks are being repeated for that pose.

The monitored-PD checkpoint also passes six local behavioral fault controls. The
sensor owner now monitors USB source events and reconciles parked/stationary
cable changes while keeping charging inhibited. Its board revision shares the
existing bus and adds one bypass capacitor and one interrupt pull-up, removing
two resistors; all three SKUs already occur in the design. The maintained route
rebuild preserves 1268 surviving copper items and 194 existing footprint geometries,
removing only nine obsolete segments and two vias. All 47 physical routing fault
controls, 23 integrated circuit controls and nine native schematic controls pass.
New PD supply/bus/interrupt routing remains open. CI caught a stale standalone-USB
pin-count expectation; its correction and the full 37-test native schematic suite
pass in the run above.

The subsequent [transient and motor-energy review](electrical/transient-review.md)
identifies unresolved input clamp coordination, dump-load thermal capacity and
continued back-drive after thermal isolation. A higher-voltage input cutoff
revision is being captured; it is not yet on the published board. The original
blind must also [hold independently of motor power](mechanical/existing-blind-holding.md).
The owner confirms the existing blinds stay in place when the chain is released;
the added drive still needs to preserve that behavior on each installation.
These findings prevent a fabrication or unattended-wall-operation claim despite
the passing automated checks.

The carrier silkscreen cleanup passes both native routing checks locally and in
the CI run above, including all sixteen injected-fault controls. It preserves
all copper, pads, polarity marks and mechanical geometry.

The new [portable local ownership core](firmware/local-ownership.md) passes
all eighteen host targets, the same suite under ASan/UBSan, 59 native transport,
clock, motion and group-bridge checks, and pinned C6 Wi-Fi default/bench and
Thread cross-builds locally. The published CI run above also passes.
One executor owns local and remote motion, with fresh single-use local intents,
independent internal epochs and actual OFF readback at admission and handoff.
C6 applications still provide raw button STOP only; physical gesture/admission
wiring and qualification remain unfinished. Exact dependency pins and
modified-source rejection remain enforced.

The revised retained-enclosure artifact passes 40 named empty-intersection checks,
three positive capture controls and ten closed printable mesh types locally and in CI. Its
eight CAD source hashes match the checked source. The service tests include a conservative
2.5 mm cassette release and 72 mm forward removal envelope. These results establish
what the nominal model does; they do not establish printed fit or load capacity.
They also do not resolve the PCB handedness defect described above.
The 21 installed printed pieces total 326.435 cm³ per unit: about 414.57 g of
solid PETG at 1.27 g/cm³. This is a CAD estimate, before infill, supports and waste;
CI recalculates it from the freshly checked meshes. The separate eight-piece
[paired-loading workshop set](mechanical/paired-loading.md) adds about 227.46 g
once for the eight-unit build. Its 22 clearance checks, three positive controls
and eight closed print meshes pass locally and in CI. The modeled sequence fits the rear
tray before turning the carrier pair, with broad captive clamp pads and a
supporting cradle. Practical catch release, protected-pigtail restraint, holder
contact, insertion forces and actual loaded handling remain unfinished.

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
edge, hole, courtyard-overlap, silkscreen or keepout failures. Four explicitly
enabled mounting-hole courtyard errors remain.
Five injected failures are rejected, including a same-net via intrusion into a
fuse solder land. All twelve vias retain a 0.20 mm drill-to-SMD-land margin. Covered inward-face tracks pass through a
coordinated 0.3 mm spacer recess; current, temperature and insulation wear remain
physical qualification gates.

The [primary route](../hw/routing/blind-pack-primary/README.md) now has
451 segments and 129 vias, with all 35 nets physically connected and zero
native unconnected items. Ten load-path groups, two isolated Kelvin branches,
quiet gauge/NTC returns and connector-side communication clamps pass independent
copper-shape checks. Eleven injected faults are rejected. All 129 ordinary via
drills clear all 109 SMD solder lands by 0.20 mm, including same-net lands.
The [six-pin circuit correction](electrical/pack-communication-clamps.md) places
the three Zeners on the external side of their resistors and returns them to
PACK−. The corrected frozen circuits and native 103-pin schematic pass locally;
the standalone schematic retains twelve explicit external-interface ERC findings.
Native PCB DRC retains four exact board-only mounting-hole courtyard findings;
silkscreen and footprint-library comparisons pass. The nominal balanced-current copper estimate is 1.410 W
at 4 A pack / 2 A per cell, excluding components and contacts; it is not a
thermal result. Both carriers still need electrical, assembly and physical
qualification; the main board remains partially routed. This battery checkpoint
passes locally and in the native-circuit job of the [corrected CI run](https://github.com/0x63616c/smart-blinds/actions/runs/39403449107).
The first run caught a stale source hash in the captured parts list; refreshing it
changed no quantities or prices. All thirteen jobs in the corrected run passed.

The [partial main power route](../hw/routing/blind-main/README.md) preserves all
196 footprints, the 609-pin/139-net graph, 17 mechanical/thermal anchors and 13
reservations. Its 1013 segments and 255 vias connect 70 checked copper groups,
including local charger/motor/regulator paths, radio power, USB input/CC/bypass
connections, negotiated-enable/divider/discharge chains, the charger input and
PMID/SYS capacitor banks, ground return, VAC/BATP sensing, TS/ILIM and PROG networks.
The [monitored-PD migration](electrical/monitored-pd-revision.md) updates the
circuit and every maintained routing stage. VSYS is no longer grounded; the
old two factory pull-downs are removed. Its two new staged components and shared
bus/interrupt connections are not yet routed. This explains the increase in
open connections despite preserving all surviving previous copper.
The local regenerative-clamp extension adds 19 connected local nets and eight load
groups. The subsequent [supervision stage](../hw/routing/blind-main/local-supervision.md)
adds 59 checked local branches, including watchdog timing/reset and encoder
regulator returns. It moves fourteen previously unwired small parts and preserves
all incoming copper. The USB extension connects both reversible data pairs through their
protection pads and module resistors. Forty-seven injected geometric/copper failures
are rejected locally,
including same-net via-to-solder-land intrusion. All 255 ordinary
route vias retain a 0.20 mm drill-to-solder-land margin, including same-net lands.
The assembly pass moves twelve vias and preserves their connections with
adjusted traces and five short stubs; components remain fixed. The control extension moves six electrical parts
and one bootstrap via; all mechanical anchors remain fixed. The preceding 178-via
assembly-clearance pass is covered by the CI run linked above; the new 218-via
clamp and USB extensions are covered by the CI run above.
Actual DRC retains 122 unconnected items, 258 silk/text findings, four library differences and five
footprint-type findings. The maintained clamp stage rebuilds identically twice and preserves the prior
copper except twelve explicit low-current segment replacements and one obsolete
NTC via. The selected power feed and actual filled-plane return corridor are
checked geometrically. The longer PROG/NTC branches, NTC proximity to the PACK
solder land, startup/noise and pulse/thermal behavior remain qualification limits.
The clamp extension passes an independent parent rebuild, all 34 earlier fault
controls and the CI run above. The subsequent USB stage preserves saved ground
fills, checks actual signal paths and rejects a protection bypass. It has six
additional fault controls and two identical builds. Its CI and preview refresh
have passed. D-minus still has two extra layer transitions; matched planar
lengths do not establish delay equality or 90 Ω impedance. Critical-loop,
current/thermal, USB performance, supervisory and full-routing work remain.
The local supervision extension also passes all 47 controls after composition
with USB, with two byte-identical builds and exact comparison to the frozen
study copper. Long bypass/pull-up paths, upstream feeds and the roughly 27 mm
separation between the ADC filter and MCU pin remain layout limits.
The preview renderer now explicitly uses the board's stored solder-mask color;
local and published KiCad output confirm the requested black finish.

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
The later sensor runtime integration below instantiates the adapter. Local response
and physical conversion continuity still require qualification.

The [joint power mailbox](firmware/power-mailbox.md) commits charger
and gauge reports with one accepted serial. Healthy refreshes retain the previous
fresh pair; a first detected fault or clean window close invalidates it. Readers
receive immediate, single-use snapshots. A fresh parent build passes all nineteen
portable targets; the source-bound checkpoint also passes three focused sanitizer
targets, competing readers under ThreadSanitizer, nine restored-bug controls and
both pinned real-SDK Wi-Fi builds. The nineteen-target suite and pinned builds
also pass in the [corrected CI run](https://github.com/0x63616c/smart-blinds/actions/runs/39403449107), along with all its geometry jobs.
The subsequent [sensor runtime integration](firmware/sensor-runtime.md) now
instantiates it on the actual C6 sensor task, with separate control/status reads,
OFF-only charger parking and owner acknowledgment before sleep. Expired sleep
continuity creates a fresh cold monitoring session without rebooting. All 21 host
targets pass in a fresh independent parent build; the source-bound checkpoint
also records Linux GCC, focused sanitizers, five restored-bug controls and pinned
default/bench C6 builds. All 21 host targets and both pinned SDK configurations
also pass in the [published CI run](https://github.com/0x63616c/smart-blinds/actions/runs/39411405488). No physical
qualification records are supplied; hardware permissions remain disabled.
Physical critical-section, acquisition and sleep timing remain unmeasured.
An independent board/profile audit also corrected the OFF-only input-current
request to 100 mA so it fits the board's low startup clamp. The external limit
remains enabled; clamp-aware tests reject the former 1.5 A request. Normal
charging and USB source-change handling remain unfinished.

The subsequent [parked source-reconciliation helper](firmware/charger-source-reconciliation.md)
accepts only a documented autonomous voltage-threshold change while charging and
motion remain inhibited. It preserves the exact current/protection settings and
first fault history, and requires the same live owner and session. All 22 host
targets pass in an independent parent build; the source-bound record also includes
Linux GCC, focused sanitizers, six restored-bug controls and both pinned C6 builds.
All thirteen jobs also pass in the published CI run above. This helper is not yet called by the application. Cold-session transfer, normal
cable recovery and actual charging remain unfinished.

The separate [Wi-Fi motion target](firmware/wifi-motion.md) binds authenticated
requests to the existing owned control runtime. Raw button STOP precedes ADC
sampling; revocation and request generations prevent stale readiness or parking
reports from surviving a disconnect or newly queued command. Physical OFF
readbacks and independent control power locks govern sleep. The eighteen-target
portable suite passes locally, as do pinned default/bench C6 builds and the
existing Thread target after the shared runtime changes. The application supplies
empty qualification records, so it cannot initialize motor I/O or establish a
physical reference. It has no local endpoint gesture, charge-enable, commissioning
or OTA path. The gauge continuity adapter is now connected through the sensor
runtime above; a cable-change policy and physical qualification remain.

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
- The current enclosure is 118 × 196 × 77 mm, with plain buttons reaching 78.8 mm.
  The historical 71 mm case and its material budget are separate; actual holder
  tails, solder, cable and printed tolerances still require prototype checks.
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
- Current study component demand is **$379.94 for eight units** ($47.49 each), or
  **$99.27 for two**, using catalog observations from 19–20 October. The [dated ledger](../hw/studies/clean-main/dated-components.json) includes both carriers. It excludes
  boards, assembly/setup/feeder fees, minimums, cells, motors, cables, mechanics, shipping
  and tax; stock and assembly eligibility need refreshing. This is not a quote.
- The current 206-part circuit replaces the earlier USB input front end, whose
  suppressor exceeded both 28 V input limits. Remaining routing and
  transient/current qualification are unfinished.
- A stuck dump switch dissipates about32 W, and thermal cutoff removes the
  absorber while coasting. Sustained back-drive needs a complete holding/braking
  solution; these are design gaps, not passed simulation or prototype checks.
- Charge/protection behavior, current limiting and physical thermal/fault testing remain open.
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
