# Trade Study: Complete wall-mounted packaging

**Date:** 2026-10-19
**Status:** OPEN

## 1. Context

Fit six Samsung INR21700-50E cells, the purchased Recfountik JGB37-520 12 V 111 RPM encoder motor, one integrated controller/charger PCB, a retained bead-chain drive, underside USB-C and two physical buttons into a white wall-mounted enclosure. Seven units are needed; budget and release quantities are eight. Minimize the whole product's cost and size, not just PCB area.

The only carried-forward geometry is the owner's **4.5 mm bead diameter and 6 mm pitch**, approximately 1 mm linking cord, and chain plane perpendicular to the wall. The direct-drive shaft must therefore run horizontally, parallel to the wall. The selected motor's exact length, shaft offset, screw pattern and encoder/cable envelope have not been measured. The CAD deliberately uses an original **39 mm diameter × 64 mm body + 18 mm shaft** envelope; it is not a model of the purchased motor. A different 100 RPM motor's old STEP file was not reused.

Cell maximum dimensions of 21.25 × 70.8 mm come from a [Samsung-authored specification](https://files.batteryjunction.com/frontend/files/samsung/datasheet/SAMSUNG-50E-21700-Datasheet.pdf). The study expands each cell to a provisional **23 mm diameter × 76 mm insulated pack envelope**, allowing for wraps, spacers and terminal insulation. Actual welded pack construction must set the final dimensions. Electrical ratings, charge profile and cell revision need their own review.

## 2. Options

### Option A: Broad and shallow

Six vertical cells across one depth layer. The motor is horizontal above them; the PCB sits in front of the lower part of the cells. This gives the pack straightforward access, but produces a broad object. Cells behind the radio require extra stand-off: the board sits 44 mm from the wall, leaving 15.5 mm above the insulated cells and increasing shell depth to 58 mm.

### Option B: Compact direct drive

Three cell columns and two depth layers. The motor stays horizontal above the pack. One 75 × 35 mm board sits parallel to the front face, with its antenna at the right edge, USB-C on the underside and front button actuators. This is the initial engineering candidate. Its width was increased from an early 108 mm bound to **114 mm** to preserve a **15.5 mm nominal lateral gap** between the insulated pack and the 15 mm PCB antenna band. The selected radio's actual clearance instructions still control.

### Option C: Narrow, with a right-angle transmission

The cells lie horizontally in three rows and two depth layers. A vertical motor drives a horizontal chain shaft through a bevel pair. This reduces the width, but introduces two gears, an output shaft and at least two bearings, plus retention and another alignment interface. Gear geometry in the study is explicitly an envelope, not a functioning transmission. The rotated radio faces the bottom-right corner; the pack is raised to leave 15 mm between the antenna reservation and cell envelope. This increases total height to 212 mm.

### Option D: Slim direct drive

Three cell columns in one depth layer, with a second row above them. The horizontal motor remains above the pack and the PCB retains the compact design’s lateral antenna clearance. This avoids the right-angle transmission while reducing projection to 54 mm, at the cost of a 220 mm height.

## 3. Comparison Table

Dimensions are calculated from the current original CAD, not a measured assembled product. Bounding volume includes empty space.

| Criterion | A: Broad | B: Compact direct | C: Narrow right-angle | D: Slim direct |
|---|---|---|---|---|
| Outer W × H × D |150 × 140 × 58 mm|114 × 140 × 68 mm|86 × 212 × 68 mm|114 × 220 × 54 mm|
| Wall area |210 cm²|159.6 cm²|182.3 cm²|250.8 cm²|
| Bounding volume |1,218 cm³|1,085.3 cm³|1,239.8 cm³|1,354.3 cm³|
| Motor orientation |Horizontal; direct|Horizontal; direct|Vertical; bevel conversion|Horizontal; direct|
| Pack arrangement |6 across × 1 deep|3 across × 2 deep|3 rows × 2 deep, axes horizontal|3 across × 2 vertical rows × 1 deep|
| Board allowance |75 × 35 mm|75 × 35 mm|65 × 35 mm, routing pressure|75 × 35 mm|
| Antenna separation from pack |15.5 mm in depth|15.5 mm laterally|15 mm vertically|15.5 mm laterally|
| Extra transmission parts |None|None|At least 5, excluding fasteners|None|
| Battery service |One shallow row|Remove PCB carrier, lift pack|Remove PCB carrier, lift pack|Two shallow rows; longer pack|
| Main size compromise |Broad front|68 mm projection|More drive parts and alignment|Tallest and most wall area|
| Alignment/noise risk |Chain retention, shaft side load|Same|Adds gear mesh, backlash and bearings|Same as direct candidates|
| Current qualification |Envelope study|Envelope study plus provisional fit meshes|Envelope study; no functional gears|Envelope study|

## 4. Recommendation

**Rationale:** Take **B** into first-fit coupons and an assembled non-powered mockup. It has the smallest wall area and avoids buying complexity to make one dimension narrower. D remains a credible direct-drive alternative if 68 mm of projection is visually unacceptable and a 220 mm height fits. A suits a broad, short installation. All candidates still need a realistic wiring route and heat tests; the battery mass makes speculative reductions of a few millimetres a poor trade for crushed insulation or inaccessible screws.

**What we're giving up:** B projects 10 mm farther from the wall than A and 14 mm farther than D. Its PCB sits in front of the battery pack and must be removable without tugging battery wires. The direct-drive approach depends on acceptable motor output-bearing radial load; the measured chain load may require a separate supported shaft and coupling, which could erase the size advantage.

**When to revisit:** Measure the owned motor; establish chain-to-wall offsets and return clearance at every blind; verify pack dimensions and motor radial-load capability; route the actual PCB; test the assembled antenna. The model evaluates shaft-offset scenarios of 0/±7 mm in both Y and Z for direct drives. A 52 mm shell would interfere with the flange by 0.4 mm at +7 mm Z offset; D therefore uses 54 mm. These scenarios are not bounds on the owned motor. A larger body, different eccentricity, restrictive radio clearance or an added bearing must update both CAD and table. User review is still pending; OPEN does not imply a fabrication decision.
