# Paired carrier loading candidate

The current mechanical candidate loads the two outward-facing cell rows while
both carrier boards remain wired together at their fixed **5 mm separation**.
A one-piece spacer backs the three reserved inward lands and temporarily captures
the board corners. The companion row is loaded first, its rear tray is fitted,
and two broad-pad workshop clamps hold that tray to the spacer before the pair
is turned onto a broad cradle. The primary row is then loaded without another
loaded flip. The installed cassette still closes with four M3×60 screws.

This is a modeled construction sequence for evaluation with empty holders and
cell surrogates. It is **not a released battery-loading procedure**. Actual cell
insertion/retention, holder polarity/current, force paths, insulation, printed
creep and a strain-free protected-pigtail restraint remain unresolved. No raw
link is soldered after cells are loaded; both carriers must be empty for the
permanent link construction and electrical inspection.

## What changes in the installed device

The exterior remains **115 × 174 × 71 mm**, with the existing button projection.
PCB, USB, switch, motor, holder, wire-pad and barrier anchors do not move. The
spacer and two cassette shells change, adding no installed pieces or fasteners.
The installed total remains 21 printed pieces per blind.

| Feature | Candidate geometry | Limit |
|---|---|---|
| Inward backing | Three 8 × 50 mm lands on each carrier: local X11–19 / 37–45 / 63–71, Y25–75 | Existing electrical reservations; no exposed copper, vias, pads, test points or tails. Covered tracks need contact/wear review. |
| Backing layers | Z31.6–33.5 and Z34.7–36.6, with cross-links recessed 0.3 mm from the PCBs | Preserves the separate barrier and existing upper wire-tail relief. Does not establish that every holder insertion load bypasses solder. |
| Temporary corner catches | Four 24 mm arms, 1 mm nominal thickness, 5 mm axial width; 0.2 mm nominal face gap | Kinematic release model only. Print direction, strain, temperature and repeated use are unqualified. |
| Catch release | Tips displaced 1.3 mm outwards, with 0.2 mm nominal clearance beyond the board edge | The model moves all four together. A practical retained or sequential release method is unfinished. |
| End registration | Two 5 mm-wide spacer edge stops | Also contacted by temporary clamp jaws; their narrow roots need physical load review. |
| Shell fit | 0.4 mm per-side cavity allowance near the board stack; 0.2 mm outward seam band | Retains 1.2 mm nominal wall locally; does not establish an FDM tolerance. |
| Pigtail port | Open to the joining seam, continuing the existing side exit | Permits a prewired pigtail to enter during closure. Final internal fan and restraint remain unfinished. |

The fit comparison matters: a 0.2 mm allowance retains a 1.2 mm wall without a
band, while 0.3/0.4 mm would reduce it to 1.1/1.0 mm. The selected 0.4 mm candidate
adds a 0.2 mm seam band instead. Its local bounds become X3.2–92.4,
Y4.4–111.6. A whole-case check covers the band against the fixed cover, wall plate,
controller, drive and service envelope. The earlier 0.2 mm candidate is not
assumed to fit an unqualified printer.

Four local scallops admit the catches. With each shell separated 8 mm, the model
leaves side approach space for 3 mm-class insulated tools. That corridor
does not establish the required outward actuation or a usable gripper shape. Front and rear approaches
are checked through continuous 35 mm translation envelopes. These establish
nominal space, not comfortable finger access or a completed catch-release tool.
The installed screwed shells remain the electrical-safety restraint; temporary
printed catches do not replace them.

## Reusable workshop pieces

Print one set for the eight-unit project. These **eight pieces are not installed
in each blind**. The older single-carrier fixture remains a historical study;
it is not an additional required set.

| Piece | Quantity | Function / print orientation |
|---|---:|---|
| Raised paired-fixture base | 1 | 106 × 124 × 6 mm base with corner posts, locating pegs and comb pillars; base flat |
| Lower and upper removable combs | 1 each | Index to primary or companion holder positions; upper broad faces down |
| Lower and upper temporary C-clamps | 1 each | Hold the rear tray to existing spacer end stops; broad X faces down |
| Captive pressure pads | 2 | 13 × 10 × 2 mm pressure plates with retaining skirts/hooks; broad tray-contact faces down |
| Broad tray-bearing cradle | 1 | Supports the rear tray floor and relieves its feet/ear; broad bearing face down |

Workshop hardware is **four M3×16 socket screws, two M3×10 socket screws and six
M3 nuts**. Screw/nut dimensions remain nominal allocations requiring purchased
part and print-fit checks. The combs move 4 mm between indexed P/C settings;
the marking and pins distinguish the two mirrored holder rows. Remove the combs
for the modeled insertion/removal path, then use them only under a qualified
contact-setting procedure. The existing rim gap does not supply preload.

Each temporary clamp carries a captive pressure pad, so its screw tip is not
modeled against the 1.2 mm tray floor. The pad has a blind locating seat, a
remaining 1 mm top thickness, and nominal 0.8 mm hook engagement under the jaw.
Loosening by 0.4 mm clears the tray while retaining screw-to-pad locating
engagement. Deliberate further withdrawal permits pad removal. The modeled
screw-head stop allows nominal 0.2 mm additional travel; it is **not a safe-force
or tightening-torque specification**. Pad bending, tray deflection, stop-root
loads, thread friction and screw tolerances need physical checks.

The upper pad bears at global Y81–91, below the wall-head pocket beginning at
Y92.2. The lower pad lies between the cleat pockets. The cradle has open channels
for both clamps and recesses the cassette's lower corner feet and mounting-ear
ramp. Its broad face carries the tray; the cell wrappers are not intended
supports. The 1.2 mm floor remains a thin printed load-spreading surface whose
stiffness and creep are unqualified.

## Modeled sequence and reverse paths

1. With both carriers empty, construct and inspect every permanent insulated
   raw-group link and identify/terminate the protected pigtail. Preserve the
   fixed board gap and separate insulating sheet. Verify actual tail/fillet
   protrusion against the 1.5 mm limit. No open-book raw-link slack is assumed.
2. Place the wired pair companion-face-up on the raised fixture. Its four bare
   corner lands meet the posts and its opposite holder row clears the base.
   Select the companion comb index, then remove the combs for the loading-path
   evaluation. Keep the disconnected protected pigtail within its parking
   reservation using a separately qualified strain-free restraint.
3. After surrogate loading evaluation, fit the rear tray from above. The
   intended eventual cell-loading step still requires a separately reviewed
   electrical and physical procedure. Install the two temporary clamps and
   broad pressure pads without relying on an invented torque setting.
4. Lift 100 mm before turning about the modeled axis. Do not rotate on the
   locating pegs. Place the rear tray onto the broad cradle with the primary
   face upward. The companion row is now enclosed, and the primary row is
   still empty. The conservative turn box clears the remaining fixture by
   approximately 13.86 mm.
5. Evaluate primary loading/removal while the cradle supports the tray. The
   intended force path passes through the backing/frame and corner/tray lands
   to the cradle. It is not proof of solder unloading or holder load capacity.
6. With the assembly still supported, loosen and remove the temporary clamps,
   complete the protected harness dressing and fit the front lid. The final
   four M3×60 screws replace temporary handling retention. The internal harness
   must be finished and inspected before this can become a real assembly step.

The lower clamp has a 30 mm endwise access path. The upper clamp approaches from
above the top end while offset 25 mm to the left, then slides sideways into
place. Reverse sweeps cover removal, including loosened pads and screw heads.
The route avoids the fixture pillars, tray feet and space-only pigtail envelope.
Cell removal is represented by reversing the same assumed loading envelope;
actual spring compression, hand/tool grip and contact engagement are unverified.

For later cassette opening, the shells separate and the temporary catches can
remain engaged while the independent screw restraint is removed. Releasing the
boards requires the unfinished catch-release method described above. The model
does not authorize handling a loaded exposed pair solely by those catches.

## Protected pigtail reservation remains unfinished

Six continuous 1.85 mm diameter insulated paths run from the existing protected
pad row to a **54 × 55 × 36 mm** workshop parking box beginning at global
(32,130,26). Conservative bounds enclose each entire curved segment, rather
than checking only sampled centre points. The box reserves space for the loose
stock pigtail and disconnected plug; it is not a printed retainer or a wire-cut
schedule.

Exact trim length, strip/fillet details, minimum bend/straight lengths at soldered
ends, inspection access, the final installed fan, and a strain-free restraint
through the lift/turn remain open. The turning clearance is conditional on that
restraint keeping the harness inside its box. Uncontrolled loose wires do not
satisfy the modeled sequence. All raw links remain within their insulated
channels throughout; no exposed raw-group connector is introduced.

## Printing and evidence

Use the white PETG candidate and heat limits in
[material and retention](material-and-retention.md). A 1.2 mm wall is compatible
with three nominal 0.4 mm extrusion widths only as a slicer planning observation;
actual line widths, walls, bridges, supports and strength still need review.
The one-piece spacer includes hooks extending on both faces and needs supports;
it is not a support-free part. Remove all support debris, inspect smooth
cell-facing surfaces and qualify the temporary arms with surrogates first.
The clamp print orientation keeps its C-frame in the broad layer plane, but
does not establish resistance to opening, creep or impact.

Sources are `cad/source/holder_pair_handling.scad`, included by the retained
case, and `cad/source/holder_pair_fixture.scad`. Reproduce the evidence with:

```sh
python3 cad/build_retained.py --export --render --intersections --jobs 4
python3 cad/build_holder_pair_fixture.py --export --render --intersections --jobs 4
python3 cad/print_budget.py --verify-stls
```

The retained builder checks the installed geometry, continuous shell approach,
release corridors and positive corner-capture witnesses. The workshop builder
checks both face orientations, conservative holder/cell envelopes, loading,
clamp access/removal, pressure-pad travel, cradle support, parking and the
turn-box containment. Pad travel checks the nominal and 0.4 mm released positions; it is not a
continuous screw-motion or force analysis. Positive pad controls show hook
capture, locating-seat interference and screw-head stop contact. Reports bind inputs and exported
mesh hashes, and are published only if the source snapshot stays unchanged.

Closed meshes and empty nominal intersections do not qualify force, repeated
release, FDM tolerance, actual cell insertion/retention, flexible-wire handling,
insulation or thermal performance. The report names exactly which checks ran;
this document is not evidence of a completed run by itself.
