# Trade Study: PCB holders and supported chain drive

**Date:** 2026-10-19
**Status:** OPEN

## 1. Context

The owner prefers cells that plug into PCB-mounted holders, reducing eight-unit assembly effort. A separate battery carrier is acceptable. This supersedes the welded-pack preference implicit in the [first packaging study](2026-10-19-packaging-trade-study.md); its compact layout is retained as a comparison, not a frozen design.

An independent output shaft also deserves a fair allowance. The reported 22.24 N pull creates about 0.258 Nm at the 12-pocket wheel. It is the **difference** between strand tensions that produces torque; radial shaft force is approximately their sum. A modest 10 N slack-side preload would imply about 42.24 N radial force, before jam/shock factors. The owned gearbox has no recovered radial-load rating, so bolting a chain wheel to its shaft is an unresolved assumption, not the default safe cost saving.

The actual purchased [motor listing drawing](../research/purchased-motor.md) shows 33 mm motor can diameter,22 mm can length,6 mm boss,15.5 mm exposed 6 mm shaft, and 5.4 mm flat. Gearbox length is only labelledL. We retain a 39 × 64 mm family body allowance and 8 mm rear connector/bend reservation. This is a provisional design assumption, not a guaranteed maximum for all JGB37-520 variants. The owner cannot measure for weeks; design continues using a replaceable bracket, clockable clamp and replaceable shaft adapter.

## 2. Options

### Sourced holder geometry

The [MYOUNG TH drawing](https://datasheet.lcsc.com/datasheet/pdf/ea18f085f5f9b6da9d587816ecf7f47a.pdf), BH-21700-A5BJ001 / C20606809, gives 83±0.8 mm body length,25±0.5 mm width,15.6±0.5 mm unloaded height and 4±0.5 mm tail length. The [SMT drawing](https://datasheet.lcsc.com/datasheet/pdf/f19fdde684eed5e7f56342763817f937.pdf), BH-21700-B1BJ001 / C20606791, gives 82.5±0.8 mm body length but 92.6±1.5 mm overall length including tabs; its recommended lands extend 93.6 mm. Both specify 100 mΩ maximum contact resistance without an explicit current rating or clearly stating whether this is per contact or whole holder. Neither is qualified for motor surge merely by appearing in a catalog.

A25 mm loaded height allocation includes the 21.25 mm cell and cradle floor. Loaded height and cell extraction forces are not dimensioned in those drawings and remain sample checks. Bodies are spaced 26 mm apart. Solder joints do not carry insertion loads: the final carrier must screw to a cassette and use insulating retention straps/bars. The source rendering simplifies contact shapes; it does not reconstruct the purchased holder.

[Keystone 1121/1122/1123/1124](https://beta.keyelco.com/userAssets/file/M70p23-33.pdf) is a documented comparison: single TH82.2 × 23.1 mm, single SMT91.2 mm overall length, dual 45.1 mm width. Its datasheet describes polarity protection and nylon UL94 V-0 housings. Current suitability, sourcing and cost still need checking. A holder family claim does not prove the exact owned flat-top cell cannot be reversed.

### One wide, single-sided protected carrier

Six TH holders in one row on a 158 × 100 mm carrier. The controller is a separate 35 × 75 mm board in front of the right-hand cells. Its antenna reservation sits 17 mm in front of the conservative loaded battery envelope. Protection/gauge/FETs/fuse remain on the carrier; only protected power, I2C and an independent charger NTC pair cross a keyed harness to the controller. That connector remains an electrical selection, with current and insertion space to validate.

The carrier's 100 mm height is 4 mm leading margin +84 mm holder envelope +12 mm trailing protection/mounting allowance. Its lower face is 8 mm from the wall, allowing the 4.5 mm maximum tails to clear the 3 mm backplate by 0.5 mm; an insulating backing plate and adequate mechanical stand-off may require another 1–2 mm. The current study is deliberately not a released insulation stack.

The motor is centered atY126 mm above the carrier. The smaller 158 mm shell assumes the eccentric output is clocked into the depth direction, so motor offset does not sweep through the carrier inY. A replaceable clamp can accommodate that clocking; rear connector clearance must be checked. Unrestricted ±7 mm Y orientation instead requires approximately 174 mm height. The whole supported drive fits across 170 mm without adding another height band.

### Two small, outward-facing TH carriers

Three holders per board, two 82 × 100 mm boards with their backs facing. A12 mm clear gap separates board backs: two 4.5 mm maximum tails +1 mm insulating barrier +2 mm total residual clearance. With 25 mm loaded envelopes outside both boards, the shell becomes 74 mm deep. Four raw group rails join the boards permanently inside the screwed cassette; they are not a user-accessible connector. Protection lives on one carrier. The external pack connector still carries protected power only.

This buys 20 mm less width than the wide carrier at the cost of an additional PCB, enclosed raw rail joints, barrier and assembly inspection. The controller sits beside the pack at 35 × 75 mm. Cell removal requires extracting the cassette to reach the rear face.

### One double-sided SMT carrier

Three SMT holders per face of one 82 × 112 mm carrier. The longer terminal envelope and provisional 12 mm stagger reserve room for non-overlapping locating pegs. This pattern is not proven: the exact peg locations, paste/reflow support and mechanical fastenings need detailed CAD/footprints. The quoted holder is Standard Only even for single-sided assembly; double-sided assembly cannot inherit the TH Economic assumption. This option is physically compact but has the largest factory process uncertainty.

### Main-board holders

A single combined PCB can remove the interboard cable and one PCB setup. With six TH holders on one face, the 6 × 26 mm holder row occupies 156 mm width. Reserving a real 35 mm electronics/antenna band below an 84 mm holder region yields a preliminary 158 × 131 mm main board, compared 2625 mm² for the small controller. A170 × 190 × 64 mm enclosure is a conservative first allocation, **not routed or rendered as a fitted board**. A larger mixed-technology board must be quoted before assuming that one setup is cheaper. Bringing front buttons and underside USB from a board behind cells also needs longer actuators or a separate small control board. Moving electronics onto the opposite face can reduce height but changes assembly tier and retention/access.

### Welded pack and timing belt comparisons

The requested fifth arrangement rotates the controller into a 35 × 75 mm side strip, reducing the earlier compact layout to 118 × 142 × 60 mm. That figure retains the unverified direct-drive bearing assumption. Adding an independently supported inline shaft/coupler expands it to 150 × 156 × 64 mm.

A credible belt option places a supported chain shaft 36 mm above the motor, both axes parallel to the wall. With twin TH carriers it becomes 128 × 194 × 74 mm:22 mm narrower than their inline variant,36 mm taller and 4.8% greater volume. It adds two pulleys and a guarded tensioned belt in place of the coupler. A reduction could lower speed and increase torque, but the current visualization is a 1:1 envelope, not specified belt teeth or ratio. Width may justify it on a narrow wall; it is not a clear volume or cost winner.

## 3. Comparison Table

All dimensions are original parametric reservations. None establishes physical fit, thermal performance or a complete retained assembly.

| Candidate | W × H × Dmm | Wall area cm² | Volume cm³ | Battery assembly / principal compromise |
|---|---:|---:|---:|---|
| Welded, side PCB, direct motor shaft |118 × 142 × 60|167.6|1005.4|Small lower bound; welded assembly and gearbox radial-load qualification |
| Welded, independent inline shaft |150 × 156 × 64|234.0|1497.6|Supported shaft, but pack manufacture remains a separate job |
| Six TH holders on one carrier |170 × 158 × 64|268.6|1719.0|Simplest holder assembly, broadest qualified-drive study |
| Twin TH carriers |150 × 158 × 74|237.0|1753.8|20 mm narrower,10 mm deeper, extra board and raw-rail assembly |
| One double-sided SMT carrier |150 × 168 × 64|252.0|1612.8|Most compact holder volume; Standard assembly and stagger unresolved |
| Twin TH carriers, parallel belt |128 × 194 × 74|248.3|1837.6|Narrower, taller, two pulleys/belt/tension mechanism |
| Main-board single-sided TH holders |170 × 190 × 64|323.0|2067.2|Only an analytical allocation; large PCB, actuator/radio work outstanding |

The electronics sourcing snapshot found TH holders at approximately$1.2246 each for 48, or$7.35/device, before any other parts, shipping or tax. Twelve TH solder joints per unit were estimated around$0.65/device at eight units; obtain a live complete assembly quote. SMT holders were approximately$0.9079 each, saving$1.90/device on holders while requiring Standard assembly. These are dated sensitivity inputs supplied by the electrical study, not an order quote.

A single sided carrier is the smallest number of raw electrical joints to assemble. A welded pack avoids spring contacts but adds weld quality, insulation and pack assembly work. Two carriers avoid double-sided holder placement but need a protected, inspected raw-rail interconnect. The frame and fasteners must take battery insertion and shock loads in every case.

## 4. Recommendation

**Rationale:** Develop the **single-sided TH carrier with supported inline drive** as the first fully retained model, while keeping the twin-carrier alternative live for visual review and quotes. It follows the owner's assembly preference and avoids making battery-current paths depend on a hand-built four-rail interboard joint. Its two-controller-board partition also keeps the much smaller dense electronics board independent of holder dimensions. This is an engineering proposal; the holder still needs a current/temperature qualification or replacement.

**What we're giving up:** The 170 mm width is substantial. Twin carriers save 20 mm width and add 10 mm depth. A belt can narrow the twin version another 22 mm while making it 36 mm taller. The double-sided SMT design is~6% smaller in volume than the wide carrier, but savings depend on the Standard quote and a real peg/retention design.

**When to revisit:** Before freezing, complete current-limited motor/holder thermal analysis, exact PCB/connector and protection placement, carrier insulation/fastenings, adjustable motor support, shaft/bearing/coupler selection, chain guard and RF testing plan. Obtain Economic versus Standard complete eight-unit quotes. Use replaceable motor fit parts so the absent measurements do not stop design; physical fitting later is still required. A supported-shaft wall mockup and the owner's visual width preference can change this recommendation.
