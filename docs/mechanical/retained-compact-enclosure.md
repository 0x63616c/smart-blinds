# Retained compact enclosure candidate

The new source is `cad/source/compact_retained.scad`. It continues the compact
shared-shaft study with a load-bearing wall plate, independently closed battery
cassette, removable controller frame and front-fastened cover. The case remains
**115 × 174 × 71 mm**; the two button faces add 1.2 mm locally. This is a digital
fit candidate, not a fabrication release. The controller and carrier boards have
separate electrical placement work; the envelope model remains a simplified representation, and the purchased motor has not been measured.

## Construction and dimensions

| Interface | Modeled construction | Remaining qualification |
|---|---|---|
| Wall plate | 3 mm base, 6 mm motor deck and three recessed 4.8 mm slotted wall holes | Wall-specific anchors, screw/washer fit, printed creep and proof load |
| Cover | 2.4 mm shell, four front-access M3 screws into captured nuts, four integral plate columns | Printed fits, screw torque, cover/button stiffness and temperature |
| Cassette | Rear tray and front lid, four M3×60 compression screws, central spacer and separate 1 mm insulating sheet | Carrier placement, solder protrusion, holder force/current/polarity and insulation review |
| Cassette to plate | Two concealed T-head cleats and one front-access M3×6 lock screw | An 8 mm straight tool corridor, captive pocket fit, printed strength/creep and service handling |
| Controller | Edge frame, two countersunk M3×6 plate screws, two removable keyed M2.5 edge clamps | Actual board edge notches/lands, connector placement and tolerance stack |
| Drive | Existing replaceable motor clamps, shared motor shaft/outboard bearing and screwed guard, shifted 2 mm upward | Actual motor dimensions, radial load, axial retention, chain force and wear |

The central wall-screw recess seats its washer at Z3 and now has a cassette-pocket
ceiling at Z8.2, with a 1.2 mm roof above it. Reserve at most **5.0 mm combined
washer/head height** and 9 mm washer diameter. The pocket covers the complete
±2 mm wall-slot adjustment and 2.5 mm cassette release slide; its capsule centres
span Y98.5–105. A 15.6 × 1.5 mm relief in the front edge of the raised motor deck
clears that larger pocket during release. These are internal changes; the case
exterior, drive fasteners and PCB anchors are unchanged. Wall-specific anchor
selection and proof load remain unresolved.

The cosmetic cover is not the battery or motor support. The complete closed
cassette can be removed from the wall plate without removing its four closure
screws. Only the protected pigtail crosses the cassette wall; the raw cell-group connections,
solder tails and insulating barrier stay inside. The outer cover's chain opening
is open towards its rear edge, so the cover can move forwards off a continuous
chain while the separate drive guard remains installed.

The trimmed-pin stack retains the earlier 5 mm separation between carrier PCB
backs. The maximum inspected pin-and-solder protrusion remains 1.5 mm on each
board. A separate 1 mm insulating sheet is captured in a 1.2 mm slot, leaving
nominal 0.5 mm clearance to each pin envelope; the extra slot tolerance is a fit
allowance, not extra electrical clearance. Use a specified unclad insulating
sheet with documented electrical and temperature properties; the provided
outline is a cutting template. A printed thin sheet is not treated as equivalent.
The earlier 78 mm untrimmed packaging study remains the fallback. This retained
source currently implements only the 71 mm, trimmed version.

The cassette walls fit by moving both boards 1.8 mm right. Their new origin is
(4.8, 6), size 86 × 104 mm, corner radius 4 mm. Four 3.4 mm mounting holes are at
local (4,4), (82,4), (4,100), (82,100). Reserve 7.6 mm diameter support lands without
copper, pads or components at these holes. Holder centres are at global
X19.8/45.8/71.8, with their long bodies beginning at Y14. The rear carrier's outward/component-side lower support at global Y8–11 is
interrupted over 8 mm spans centred on each holder (local X15/41/67); its upper
Y100–103 support remains. Two 3.2 mm-wide bridges join the interrupted middle
lands to the lower cassette wall; the companion board reserves bare local
rectangles X26.4–29.6 / X52.4–55.6, Y0–2.2. These bridges do not appear on
the primary carrier, whose lower strip contains electronics. The front carrier's lower support is removed over
local X9–77 so the actual fuse/protection placement can occupy the end strip.
Corner posts and end lands remain. These support lands are on the **component
faces**, not the opposing solder-tail faces. Use a separate backing fixture for
cell insertion: the installed supports do not establish a qualified insertion
force path around each holder's solder joints. The holders' maximum modeled metal/cell extent
is X84.55, before the reserved antenna region beginning at X85.6, leaving 1.05 mm beyond
the modeled 15 mm clearance zone.
Both carrier boards must also keep copper, vias and other metal out of local
X80.8–86, Y50.5–87 on every layer: their FR4 enters the radio reservation even
though the holders do not. The global coordinates in `retained-interfaces.json`
govern this clearance.

The companion's upper outward support still contacts its F.Cu face, which remains
bare. The central spacer also formerly touched B.Cu in that band. It now has a
0.3 mm deep, rounded recess over global X13.3–82.3, Y99.5–103.5, Z31.6–31.9.
Only covered B.Cu tracks may cross local X9–77, Y94–97; no vias, exposed pads,
lead tails or copper pours are permitted there. The recess extends 0.5 mm beyond
that permitted rectangle, retains 1.6 mm of spacer below the insulating-sheet
slot, and leaves corner posts, the edge frame and outward F.Cu support intact.
Print/PCB tolerance, abrasion, structural and dielectric qualification remain
separate; solder mask is not the sole insulating barrier.

The actual primary wire pads exposed a separate integration conflict: six Ø4 mm
protected-harness pads at local X47/53/59/65/71/77, Y94.8 and six Ø2.5 mm NTC
pads at X10/14/18/22/26/30, Y94.5 occupied its former upper spacer crossbar.
That **primary-facing crossbar is now removed**, preserving the full four Ø7.6 mm
corner posts and outer perimeter frame. The primary upper board loads therefore
reach those corner/perimeter supports, without an intervening crossbar; stiffness
and assembly-force qualification must assess that changed path. No thin roof is
left beneath the solder joints. The companion-facing rail retains its 1.6 mm
section below the insulating-sheet slot.

The twelve actual pad anchors are represented by conservative cylinders using
the complete pad diameter and the maximum 1.5 mm solder-tail/fillet protrusion.
Their lowest Z35.1 extent leaves **0.5 mm nominal separation** from the barrier's
Z34.6 upper surface. Dedicated tail-to-spacer/barrier and preserved-corner-material
checks supplement the broader PCB-allocation tests. This separation is not a
dielectric rating or a complete print/PCB/solder tolerance budget. All other
actual parts, vias and solder geometry still require integration review.

The four cassette screws compress posts and board/spacer lands. They do not
press the cells. Smooth ribs in the lid sit 0.7 mm above the conservative loaded
holder envelope. Their geometry limits motion if a cell escapes its holder; the
gap and force on the actual cell wraps require inspection. The drawing does not
prove that a reversed flat-top 21700 cell is mechanically rejected. Only a matched,
qualified six-cell set with controlled, depowered service is contemplated.
The holder drawing additionally shows two diagonal 3.2 mm mounting bores,
concentric 5.0 mm features, two recommended 4.0 mm PCB holes and a locating
feature. It does not clearly dimension the screw-seat section/height. Their PCB
holes must be preserved. A nominal 5.5 mm M3 socket head cannot be assumed to fit
a 5.0 mm recess; equally, the concentric feature alone does not establish that
it is such a recess. This candidate therefore uses the separate plastic-rim
capture described below, without treating those features as qualified screw
seats. Any future backside fastener must respect the 1.5 mm protrusion limit
beside the insulating sheet. The cassette
and board posts do not by themselves prove that insertion force bypasses every
holder solder joint.

## Holder capture and service fixture

Two integral end-comb ribs in each cassette half now provide four plastic-only
capture feet per holder. They add no installed parts or fasteners. Each foot is
3 × 1.6 mm, at X offsets −9.5…−6.5 and +6.5…+9.5 from the holder centre,
and global Y15.6–17.2 / Y94.6–96.2. The supplier model places these on broad
plastic end-wall flats, outside its central contact strip and the cell ends.
That model omits the mounting-hole details shown in the drawing; it is supporting
geometry evidence, not proof of the purchased holder's contact surfaces.

The drawing gives a 15.6 ± 0.5 mm rim height. The current candidate uses the
16.1 mm upper envelope and an independent 0.2 mm gap: rear capture faces are
at Z13.7 and front faces at Z54.5. Consequently the supplier's nominal rim has
0.7 mm free movement and the drawing's low end has up to 1.2 mm. This is **bounded
capture, not preload or a verified solder-force bypass**. Actual contact settings,
holder motion, printed stiffness and temperature must be qualified before the
ribs are relied on for load retention. The parameter makes the fit explicit;
it does not convert an uncertain surface into a manufacturing tolerance.

`cad/source/holder_service_fixture.scad` supplies a separate reusable workshop
fixture: one backing base, two removable end combs, four M3×30 screws and four
M3 nuts. Its three backing lands are local X11–19 / X37–45 / X63–71, Y25–75,
on the inward face of either carrier. Exposed pads, vias, test points, solder and
tails are excluded from these lands. Covered traces require contact/wear review.
The underside stands 6 mm above the base, leaving 1.5 mm nominal clearance to
the drawing's maximum 4.5 mm untrimmed holder tails. The end combs sit behind
the holder ends and reach only the plastic corner flats; the cell channel is
open. The fixture has the same explicit rim/gap parameters as the cassette.

First dry-fit an empty carrier and dimensional cell surrogates. The screw stops,
actual end-rim contact, seating without FR4 bending, tail clearance and insertion
trajectory must be qualified before using the fixture with cells. No tightening
torque or preload is inferred from a fit check. A fitted contact setting and
approved, depowered pack-service procedure are required. The final permanent
raw-link construction and insertion sequence remain design work: this fixture
supports an individual carrier and is not claimed to service a rigidly joined
pack. Both carriers must be empty when their permanent insulated raw-link wires
are soldered and continuity-checked. Open-book handling would require a checked
slack-storage and strain-relief route; alternatively, a future spacer-backed
assembly may allow loading both outward faces after wiring. Neither complete
construction sequence has been demonstrated by this fixture. It does not
prescribe joining live raw-group wires after loading cells.

## Electrical and service reservations

The controller has a **54 × 68.5 × 1.6 mm board allocation**, plus a small USB
edge tongue. Its origin is global (99, 3, 8), with thickness
along X and components facing +X. Local board coordinates are
`(u,v)=(global Z−8, global Y−3)`. The front edge extends from Z55 to Z62, adding
525 mm² to the prior 75 mm-long allocation without enlarging the case. The
final board ends at local v68.5 (global Y71.5), removing unused upper fingers
and allowing the radio antenna to overhang the substrate. The button
faces keep their Y/Z positions and use the adjustable plungers below. Their final X centre is
101.9 after the board moved inward to make room for the connector.

Two countersunk frame screws finish flush at Z6.3, below the Z8 board edge.
Rounded 2.4 mm wide, 1.2 mm deep notches on the front edge at local v9/v64.5
positively locate the board against USB insertion/removal. The frame's front
rail is split around the button-guide bar at Z63.1–65.1. The board ends at Z62; the switches are set back 0.3 mm to improve copper-to-edge clearance. Their body fronts are Z61.7 and actuator tips Z62.45. The guide bar begins at Z63.1. Edge-clamp screws are centred at Z65.5, outside the radio
reservation. The new source checks those frame/button/board interfaces.

The retained buttons now use an adjustable M2×6 socket screw, a captive M2 nut
and a separate M2 jam nut inside each printed plunger. A removable white face
covers the adjustment socket. The screw and both nuts are larger than the rear
2.4 mm guide opening; an assembled guide captures them away from the electronics
if the adjustment loosens. The outer flange stops on the guide bar after
0.40 mm travel, with load passing through the cover bosses. The lower jam nut
has 0.3 mm nominal clearance above its pocket floor at full press, so it does
not become an unintended second stop.

The modeled screw-tip range Z62.50–62.90 covers the Z62.55–62.75 settings needed
for a positive free gap of 0.10–0.30 mm and the manufacturer's broad 0.10–0.30 mm
actuation-travel range. That closes the previous fixed-plunger reach gap without
claiming a maximum permissible overtravel. Set **first electrical closure at the
positive stop**, then verify release and repeatability. No additional screw
advance is prescribed. The switch return force must overcome printed-guide
friction; the cap can float within the free gap after contact releases. It is
not modeled as an independently spring-returned button. Printed fit, creep,
locking torque and an acceptable actuation margin still need qualification.
The [M2×6 dimensional reference](https://www.accu.co.uk/metric-cap-head-screws/152177-SSCF-M2-6-A2-BL)
has a 3.8 mm head diameter, 2 mm head height, 1.5 mm socket and 0.4 mm pitch.
The finish/price is not a selected purchasing requirement.

The [Nichicon UCM1E221MCL1GS product record](https://www.nichicon.com/en-us/part/ucm1e221mcl1gs/2514/)
gives 6.3 mm diameter and 7.7 mm nominal height. Ordinary components retain a
9 mm mounted-height reservation. The board's component face at X100.6 leaves
12 mm to the straight inner wall at X112.6. No frame rib or screw may enter the
actual routed components. The 18 × 25.5 mm radio module starts at global Z13.5,
with its antenna at the upper board end. Its reserved region ends at Z46.5,
leaving room for the battery connector along the front edge. This reservation
extends 1.5 mm behind the wall plane: nearby metal wall structure remains an
installed RF qualification issue. Bare clamp lands, radio clearance and actual
component placement are recorded in `retained-interfaces.json`.

The selected [HRO TYPE-C-31-M-12 drawing](https://datasheet.lcsc.com/datasheet/pdf/9e56b777c022540fcce7c7f67825f55e.pdf?productCode=C165948)
places the USB mouth 0.46 mm beyond the recommended PCB edge: 6.25 mm from the
locator-hole line to the mouth, minus 5.79 mm to the board edge. A 10.4 mm wide
tongue extends to global Y0.46, placing the mouth flush at Y0. The metal body is
8.94 mm wide, 7.35 mm long and 3.26 mm above the board, centred at global Z37.5.
The underside case opening accepts both connector and tongue. Electrical pad and
slot geometry is checked separately against that same drawing.

The controller uses a [Molex 430450600](https://www.molex.com/en-us/products/part-detail/430450600)
dual-row six-way Micro-Fit header and 430250600 receptacle. The inspected
manufacturer drawings are SD-43045-001 Rev H and 430250000-SD Rev A. The latter's
10.81 mm mated height and 11.0 mm latch space supersede the smaller product-page
height. Applying the drawing's general tolerances gives an 11.35 mm latch-space
reservation, leaving 0.65 mm to the nominal case wall. PCB/print alignment still
needs a tolerance review. The 12.65 mm header body and maximum 10.20 mm plug fit
between the antenna reservation and the front clamp. Its footprint origin is
local (45.675, 55.02), facing +v. The straight upper board edge at v68.5
is 7.66 mm from the retention peg, within the drawing's 10.16 mm limit.
The exact pin mapping and the parent's KiCad transform are in the interface JSON.

There is **no connector on the battery carrier** in this candidate. The protected
[Molex 2147561061 pigtail](https://www.molex.com/en-us/products/part-detail/2147561061)
is permanently terminated inside the cassette and disconnects at the controller.
Its six black 18 AWG UL1061 wires must be identified by continuity before pack
termination. The [manufacturer-generated cable sheet](https://docs.rs-online.com/86e4/A700000006949960.pdf)
specifies 1.85 mm maximum insulation diameter; that is not a measured grip size.
Only PACK+, PACK−, SDA, SCL and the independent charger-thermistor pair cross the
cassette boundary. ALERT and raw cell-group connections do not.

The model reserves 12.7 mm of relaxed wire after the housing, following
[PS-43045](https://www.molex.com/content/dam/molex/molex-dot-com/products/automated/en-us/productspecificationpdf/430/43045/PS-43045-001.pdf).
A nominal 11.71 mm radius turn then reaches the cassette's right side below its
upper corner post. The header has moved 2.2 mm upward to clear the down-button
courtyard; its wire exit is now Y76.09 and the relaxed segment ends at Y88.79.
The bend centre is X93.89/Y88.79, followed by a 1.69 mm horizontal extension
into the unchanged cassette port. The smaller bend still needs physical harness
qualification. Six wires pass in one vertical row at Y100.5, separated from
the holder end and post. Two 2.5 mm nylon cable ties fasten the wires to integral
cassette-lid bars. The bars carry cable load into the closed cassette; their
compression, abrasion resistance and pull retention need physical qualification.
The placed primary carrier now assigns six Ø4 mm/Ø1.5 mm-hole protected pads at
local X47/53/59/65/71/77, Y94.8 (global Y100.8), in harness-contact order. The four
raw pads stay exactly on the modeled channels. The final internal fan from the
protected row to both ties is unfinished: simply extending six straight wires
would either cross another wire or miss a tie. The simplified CAD still shows
component reservations rather than all placed electrical parts. The model does
not claim a completed electrical harness.

The motor power wires leave permanent controller solder lands at local
(u42,v34.5) and (u48,v34.5), pass into a backside channel at global X94.2, and
rise at Z61.8/64.0 above the protected battery cable. They join an inline two-way
Micro-Fit pair above the cassette. The primary housing drawing gives 24.77 mm
mated length; a conservative 25.5 × 8.5 × 11.2 mm family envelope is modeled
until the cable's exact male ear variant is confirmed. Each end has a 12.7 mm
straight relaxed-wire region before a turn. The pair sits on an integral raised
cassette tray that stops at X72.5 to clear the upper mounting screw. It uses two removable cable ties; release those ties and separate
the inline connector before removing the cassette. The tray and wires do not
rely on the cosmetic cover for support.

The two power and four encoder wires share a single 4.2 mm square bundle
reservation near the motor rear. That narrow bay has only 0.2 mm nominal
clearance in Y to the cassette and pillar envelopes; actual insulation, bundling
and printed tolerances must be checked. Separate overlapping wire paths are not
counted as independent free space there.

The encoder uses a four-way PicoBlade row at local (u40,v43.5), facing +u.
A separate front channel passes the battery header at global X110/Z66.2.
The transition holds Y46.5 until beyond the board front. Its 2.2 mm square sweep
reaches local v44.6; the PCB corridor ends at v45.1, retaining 0.5 mm allowance
and 1.05 mm separation from the down-switch courtyard. Beyond local u51, the
wire nearest surface is X108.9, so components beneath u51–54, v42.4–44.6 must
remain below 7.8 mm mounted height for an additional 0.5 mm clearance.
The optional home connector is at (u30.5,v52), facing −v, and reserves a second
channel at Z63.7. These signal paths use a provisional 2.2 mm square bundle;
the exact 2012341356 cable drawing gives 28 AWG UL1061 without a specific
insulation diameter. The [500588000 contact specification](https://www.molex.com/en-us/products/part-detail/500588000)
accepts 0.50–1.00 mm insulation, so 1.00 mm is a conservative terminal-compatibility
planning bound. Four such wires fit a nominal 2 × 2 bundle inside the 2.2 mm
channel. Two 1.85 mm power wires alongside that four-wire group fit inside the
4.2 mm square rear reservation before bend/packing allowances. This is not a
measured cable diameter. Exact cable insulation, bend radii, connector variant
and strain retention need qualification. The home path deliberately ends in the upper service bay:
reference-sensor mounting is still design work. The eight regeneration resistors
also need actual copper placement and a thermal review; the case is not approved
as their heat sink.

Two integral T-head cleats on the wall plate engage closed pockets in the
cassette's empty lower end strip. Their centres are X32.8/X58.8, Y11.5. Each
4 × 3 mm stem supports an 8 × 4 × 1.6 mm head. The cassette catches provide
1.7 mm nominal overlap on each side and 2.2 mm capture length in Y; the catch
floor is 4.1 mm thick and its roof 1.6 mm thick. The closed roof separates the
cleats from cells and contacts. These dimensions are retention geometry, not a
strength rating. The pockets end at Y16.8/Z12; the simplified rear-holder end
housing begins at Z13.9, leaving 1.9 mm nominal separation.

One M3×6 screw at X77/Y116 prevents the cassette rising off the cleats. Its
head and an **8 mm straight tool corridor** are included in the access check.
The ordinary screw reaches a captured backplate nut. There are no side screws
hidden beneath the lid or controller. The inline tray ends at X72.5, leaving
0.5 mm nominal separation from the tool corridor. The central wall-screw pocket
is elongated by 2.5 mm so its washer does not block cassette disengagement.

For service, remove the USB cable and outer cover, unplug the protected pack
connector, release the two inline-tray cable ties and separate the motor pair.
Remove the single cassette mounting screw, raise the closed cassette **2.5 mm**,
then withdraw it forwards. The controller and four cassette closure screws stay
installed. Do not pull wires to unlatch connectors. Conservative continuous
bounds include the closed tray/lid, holders/cells, boards, closure heads and
inline housing while checking the rise and 72 mm forward removal against the
drive and controller. Actual rear-tray engagement with the cleats/backplate is
checked at 12 sampled positions. A positive capture control deliberately lifts
the cassette 1 mm forwards without the release slide and requires interference
with the cleat heads; this checks capture geometry, not load capacity.
Flexible cable handling and fingers are not
validated by those geometry checks.

## Print and assembly sequence

Use the white PETG candidate and temperature/print gates in
[material and retention](material-and-retention.md). Exported orientations put each
part on Z0, but mesh closure is not a slicer or load test. The cover, cassette
lid, button plunger and removable button face are exported face-down; the controller frame and clips lie on their broad
back faces. Use the retained exporter's plunger, face and guide bar together; they replace the earlier fixed plunger and guide. Nut pockets and port bridges need a slicer review before printing.
The backplate prints flat against the bed. Its cleat heads project 2 mm beyond
the stems; inspect those short overhangs in the slicer and qualify the resulting
layer bonding. The rear cassette prints floor-down; its closed catch-pocket
roofs bridge a 9.4 mm span. Supports, bridge sag and pocket dimensions must be
checked before loaded use. The 1.6 mm head/roof thicknesses and 4.1 mm catch
floors do not establish creep, drop or pull strength. Cell insertion is performed
with the cassette removed and its carrier supported by a fixture, so insertion
loads are not deliberately reacted by the wall cleats.
Maintain smooth cell-facing surfaces, deburr holes and remove loose debris.

1. Fit the captive nuts into the wall plate, motor clamps and controller frame.
   Check screw lengths against their modeled pockets without cells present.
2. Mount the bare backplate with three wall-appropriate anchors/screws and M4
   washers that fit the 10 mm recess. The wall type is unknown, so this project
   does not prescribe a universal anchor or claim a load capacity.
3. Assemble and align the replaceable motor clamps, wheel, bearing pod and guard.
   Verify that the guard fasteners do not obstruct the shaft or base fasteners.
   The current +7 mm shaft-offset candidate remains the supported model; the
   earlier zero-offset guard conflict has not been resolved by this enclosure.
4. Dry-assemble the unloaded carrier boards, enclosed raw-group connections,
   spacer and insulating sheet. Inspect the clipped solder tails and every clearance.
   Permanently terminate and identify the protected pigtail, dress it on the two
   lid bars and fit its cable ties before closing the cassette.
   The complete cell-loading and commissioning sequence remains a design gate:
   the one-carrier fixture does not establish how to load the permanently wired
   pair. Perform this mechanical sequence with empty holders or surrogates until
   that gate is resolved. Four M3×60 screws close the cassette; these are
   separate from the single wall-plate mounting screw.
5. Engage the closed cassette over the two cleats from 2.5 mm above its final
   position, slide it down and install its one mounting screw. Install the controller frame, then
   the controller and its two keyed edge clamps. Check no components or solder joints
   are pinched. Route the motor inline pair on the cassette tray and secure its two ties. Exact harness variant, internal pack pad route and service retention still need the electrical/physical checks described above.
6. Side-load the upper M2 nut into each plunger. Insert its M2×6 adjuster from
   the front, and fit the lower M2 jam nut before fastening the guide bar. Leave
   both cosmetic face caps off. The cover can be removed to reach the jam nuts.
7. With the cover temporarily mounted and switch continuity observed on the
   unpowered controller, hold each button gently against its independent stop.
   Adjust its screw to the first closure point; release and confirm the switch
   opens without preload. Battery and USB remain disconnected for this check;
   the electrical build must provide appropriate switch-contact test access.
   Remove the cover and its two rear guide-bar screws. Keep each plunger and
   adjuster together so the upper captive nut preserves the setting. With the
   guide removed, hold the front socket with a 1.5 mm key and snug the exposed
   rear jam nut using a 4 mm nut driver with clearance for the protruding M2
   screw. Approximately 1.3 mm of nut height is exposed below the plunger flange;
   check actual tool engagement and locking torque on a coupon. The nut cannot
   be tightened through the installed guide bar. Refit the guide and cover, then
   repeat closure/release checks because locking can move the setting. Do not
   add an invented overtravel allowance.
8. Fit the cover with the chain in its rear-open slot and install four M3×10
   screws. Recheck both buttons, then press the two cosmetic faces into their
   removable pin sockets. Their pins carry no structural or switch-retention load.

This sequence is a modeled assembly plan. There is no torque specification yet;
the actual printed parts, fasteners, wall anchors, cell/contact forces, switch
travel and hot-window environment must be tested before an eight-unit build.

## Evidence boundary

`cad/build_retained.py` records source hashes, exported mesh hashes/sizes, topology,
named nominal interference checks and the specific reservations above. Its input
snapshot must remain unchanged throughout a build. Named empty intersections do
not validate unnamed interfaces, flexible cable motion, tolerances, insulation or strength.
The service checks use conservative continuous bounding volumes for drive/controller
clearance and sampled actual geometry for cleat engagement; their scopes are separate.
The dated output record describes exactly which checks ran. No component has been
physically fitted or operated in this enclosure.
