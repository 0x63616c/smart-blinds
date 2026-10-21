# Smart Blinds

Compact, rechargeable blind controllers for seven windows, with one spare.
White printed enclosures, USB-C charging, physical buttons and Home Assistant control.

[![Design previews](https://github.com/0x63616c/smart-blinds/actions/workflows/design-previews.yml/badge.svg)](https://github.com/0x63616c/smart-blinds/actions/workflows/design-previews.yml)
[![Design checks](https://github.com/0x63616c/smart-blinds/actions/workflows/design-checks.yml/badge.svg)](https://github.com/0x63616c/smart-blinds/actions/workflows/design-checks.yml)

**Current stage: prototype design.** This repository is being designed afresh. The inherited
USB-C boards below are references, not the new blind controller or a battery charger.
No complete unit has been built or physically validated.

[Enclosure comparison](docs/mechanical/2026-10-19-holder-and-drive-trade-study.md) · [Electronics comparison](docs/electrical/2026-10-19-power-control-trade.md) ·
[Design brief](docs/brief.md) · [Progress](docs/status.md) · [Measurements](docs/measurements.json) ·
[Validation plan](docs/verification-plan.md) · [Shopping list](bom/README.md) · [Wi-Fi motion checkpoint](docs/firmware/wifi-motion.md) · [Local ownership](docs/firmware/local-ownership.md)

## The product

- One integrated controller and one 3S2P Samsung 50E battery pack per blind.
- PCB-mounted cell holders are being evaluated on a separate protected carrier to simplify assembly.
- Existing Recfountik JGB37-520 12 V / 111 RPM encoder motors.
- A small white enclosure mounted low on the wall, with accessible USB-C and up/down buttons.
- Group commands align the **physical bottom edges** of different-height blinds.
- A short remote-command preparation delay is acceptable; local controls respond immediately.
- 60 days between charges is the design target; 90 days is a stretch, pending measured power use.
- Compare at least three enclosure layouts before choosing the packaging and PCB outline.
- Optimize the total cost for eight units, including JLCPCB assembly fees, packs, fixings and wiring.

The first milestone is a complete, costed design for **two prototypes**. Two different-height
blinds are needed to test synchronization before committing to the eight-unit batch.

## Design gallery

**Layout rework:** the [54 × 80 mm comparison and native placement views](docs/trades/2026-10-21-cleaner-main-board.md)
show the proposed cleaner board. All 206 components are on-grid; routing and
revised enclosure fit are still unfinished. The canonical route shown below is
the earlier checkpoint and does not meet the new routing-style requirements.
The [next review pass](docs/reviews/2026-10-21-clean-layout/usb-and-models.md)
shows the first parallel USB traces and corrected connector/inductor models,
including an actual underside view.

These images are generated from the design sources. [Preview generation and provenance](docs/previews.md).
A green preview badge means the images generated successfully, not that the hardware is validated.
The enclosure previews below still contain a [known PCB orientation error](docs/mechanical/pcb-orientation-review.md).
The inward-facing board placement and its frame, ports and cable paths are being corrected;
these images must not be used as physical PCB-fit evidence.

<!-- previews:start -->
### Retained enclosure — current exterior

115 × 174 × 71 mm white enclosure candidate, with front buttons and underside USB-C. Buttons project to 72.2 mm. This compact version requires holder tails and solder joints trimmed to the documented limit; motor-family fit and printed tolerances remain provisional.

![Retained enclosure — current exterior](docs/generated/compact-holder-closed/assembly.png)

[Source](cad/source/compact_retained.scad) · [Generated files](docs/generated/compact-holder-closed/)

### Removable battery cassette and compact drive

Two opposing three-cell carrier boards fit in a removable cassette. Separate controller supports, cable routes and adjustable front buttons are modeled. The controller is shown as a reserved volume; exact holder fastening and physical load tests remain open.

![Removable battery cassette and compact drive](docs/generated/compact-holder-assembly/assembly.png)

[Source](cad/source/compact_retained.scad) · [Generated files](docs/generated/compact-holder-assembly/)

### Retained enclosure — service view

The cover and cassette lid are separated to show access. Two integral cleats and one mounting screw retain the cassette; its modeled release and removal paths clear the controller and drive. These are prototype-fit files, pending tolerance and load qualification.

![Retained enclosure — service view](docs/generated/compact-holder-exploded/assembly.png)

[Source](cad/source/compact_retained.scad) · [Generated files](docs/generated/compact-holder-exploded/)

<details>
<summary>Integrated controller — first component placement</summary>

54 × 68.5 mm black-board study, with USB-C, protected battery connection, motor tails and encoder/home ports. All 196 footprints are placed; no copper is routed. Thermal design, manufacturing rules and physical qualification remain open.

![Integrated controller — first component placement](docs/generated/main-controller-placement/assembly.png)

[Source](hw/layouts/blind-main/main-test/main-test.kicad_pcb) · [Generated files](docs/generated/main-controller-placement/)

</details>

### Integrated controller — partial power routing

Experimental four-layer route with 1013 segments and 255 vias. The monitored-PD revision removes obsolete ground and bus pull-down branches while preserving surviving copper and existing placements. All 47 routing fault controls pass; 122 unconnected items remain. New PD supply/bus/interrupt connections, factory access, pack feed, onward signals, transient/thermal review and manufacturing checks are unfinished.

![Integrated controller — partial power routing](docs/generated/main-power-route/assembly.png)

[Source](hw/routing/blind-main/main-routed.kicad_pcb) · [Generated files](docs/generated/main-power-route/)

<details>
<summary>Companion battery carrier — experimental copper</summary>

Two-layer companion carrier with 35 copper segments, 12 vias and no disconnected nets. Silkscreen and library comparisons pass; four mounting-hole courtyard findings remain. Experimental only: current capacity, holder loading, insulation and pack assembly still require qualification.

![Companion battery carrier — experimental copper](docs/generated/companion-routed/assembly.png)

[Source](hw/routing/blind-pack-companion/companion-routed.kicad_pcb) · [Generated files](docs/generated/companion-routed/)

</details>

<details>
<summary>Primary battery carrier — connected routing study</summary>

Experimental 451-segment, 129-via route with all 35 nets physically connected and zero unconnected items. Eleven injected-fault checks cover current/Kelvin topology, protected-ground communication clamps and same-net solder-land clearance. Silkscreen and library comparisons pass. Four mounting-hole courtyard findings and thermal, transient, holder and assembly qualification remain. Not a fabrication release.

![Primary battery carrier — connected routing study](docs/generated/primary-current-route/assembly.png)

[Source](hw/routing/blind-pack-primary/primary-routed.kicad_pcb) · [Generated files](docs/generated/primary-current-route/)

</details>

<details>
<summary>Reusable battery-loading fixture</summary>

Reusable workshop supports for the wired carrier pair. The rear tray is fitted before turning the cassette; broad captive pads and temporary clamps support the modeled sequence. Eight printed tools are shared across all builds and add no installed parts. Cell retention, handling forces and pigtail restraint still require physical qualification.

![Reusable battery-loading fixture](docs/generated/holder-pair-fixture/assembly.png)

[Source](cad/source/holder_pair_fixture.scad) · [Generated files](docs/generated/holder-pair-fixture/)

</details>

<details>
<summary>Battery loading with the rear tray fitted</summary>

The first cell row is enclosed by the rear tray before turning onto a supporting cradle to load the second row. Two temporary clamps use broad pads against the tray. This is a nominal geometric sequence, pending load and tolerance tests.

![Battery loading with the rear tray fitted](docs/generated/holder-pair-tray/assembly.png)

[Source](cad/source/holder_pair_fixture.scad) · [Generated files](docs/generated/holder-pair-tray/)

</details>

<details>
<summary>Captive pressure pad detail</summary>

A broad captive pad spreads the temporary clamp load; the screw tip remains clear of the tray in the nominal model. Retention and head-stop geometry are checked. Safe tightening force and print creep remain unqualified.

![Captive pressure pad detail](docs/generated/holder-pair-pad/assembly.png)

[Source](cad/source/holder_pair_fixture.scad) · [Generated files](docs/generated/holder-pair-pad/)

</details>

<details>
<summary>Complete controller schematic</summary>

Eleven native KiCad sheets cover all 196 circuit features and 609 pin identities. The exported net partition matches the PCB; seven documented ERC findings remain. Unrouted and unpowered.

![Complete controller schematic](docs/generated/main-controller-schematic/smart-blinds-main.svg)

[Source](hw/schematics/blind-main/smart-blinds-main.kicad_sch) · [Generated files](docs/generated/main-controller-schematic/) · [PDF](docs/generated/main-controller-schematic/schematic.pdf)

</details>

<details>
<summary>Adjustable front buttons — mechanism section</summary>

Two captive M2 adjusters set the plungers to first electrical closure at the 0.4 mm positive stop. Jam nuts lock the setting. Switch return, printed friction, adjustment and repeated operation still require physical tests.

![Adjustable front buttons — mechanism section](docs/generated/compact-holder-buttons/assembly.png)

[Source](cad/source/compact_retained.scad) · [Generated files](docs/generated/compact-holder-buttons/)

</details>

<details>
<summary>Battery cassette — removable assembly</summary>

Six holders on opposing carrier boards, a separate insulating barrier and a removable printed shell. The assembled cassette releases with a 2.5 mm lift and then moves forward; disconnect and handle the cables separately.

![Battery cassette — removable assembly](docs/generated/retained-cassette/assembly.png)

[Source](cad/source/compact_retained.scad) · [Generated files](docs/generated/retained-cassette/)

</details>

<details>
<summary>Cassette retention — cutaway</summary>

The cassette pocket captures the integral backplate cleat. Nominal interference confirms capture before the release slide; printed strength, creep and fit remain prototype tests.

![Cassette retention — cutaway](docs/generated/retained-cleat-section/assembly.png)

[Source](cad/source/compact_retained.scad) · [Generated files](docs/generated/retained-cleat-section/)

</details>

<details>
<summary>Holder carrier enclosure — provisional exterior</summary>

Original 170 × 158 × 64 mm packaging study using six PCB-mounted holders and an independent chain shaft. Retention, electrical layout and purchased-part fit are still in development.

![Holder carrier enclosure — provisional exterior](docs/generated/holder-closed/assembly.png)

[Source](cad/source/packaging_v2.scad) · [Generated files](docs/generated/holder-closed/)

</details>

<details>
<summary>Battery holders and supported drives, at the same scale</summary>

Six packaging reservations. The two welded-pack options remain size references; the holder alternatives compare assembly effort, width and depth.

![Battery holders and supported drives, at the same scale](docs/generated/holder-comparison/footprints.svg)

[Source](cad/parameters/packaging-v2.json) · [Generated files](docs/generated/holder-comparison/)

</details>

<details>
<summary>Protected carrier and supported drive — exploded study</summary>

Original 170 × 158 × 64 mm packaging study using six PCB-mounted holders and an independent chain shaft. Retention, electrical layout and purchased-part fit are still in development.

![Protected carrier and supported drive — exploded study](docs/generated/holder-exploded/assembly.png)

[Source](cad/source/packaging_v2.scad) · [Generated files](docs/generated/holder-exploded/)

</details>

<details>
<summary>One protected carrier — internal arrangement</summary>

Original 170 × 158 × 64 mm packaging study using six PCB-mounted holders and an independent chain shaft. Retention, electrical layout and purchased-part fit are still in development.

![One protected carrier — internal arrangement](docs/generated/holder-inside/assembly.png)

[Source](cad/source/packaging_v2.scad) · [Generated files](docs/generated/holder-inside/)

</details>

<details>
<summary>Motor driver — native KiCad circuit study</summary>

Fourteen components and 43 physical pin connections agree with the atopile board graph. This open block has four documented ERC boundary findings; supply, controller, motor connector and regenerative-energy clamp are not yet integrated.

![Motor driver — native KiCad circuit study](docs/generated/motor-schematic/motor-test.svg)

[Source](hw/schematics/blind-controller/motor-test.kicad_sch) · [Generated files](docs/generated/motor-schematic/)

</details>

<details>
<summary>Motor cutoff and reset — native KiCad circuit study</summary>

Four ICs and ten passive parts. All 49 physical pin connections checked against the compiled circuit; two explicit external-power ERC findings. Physical cutoff and full-board qualification remain open.

![Motor cutoff and reset — native KiCad circuit study](docs/generated/supervisor-schematic/supervisor-test.svg)

[Source](hw/schematics/blind-supervisor/supervisor-test.kicad_sch) · [Generated files](docs/generated/supervisor-schematic/)

</details>

<details>
<summary>USB-C-fed 3S charger — native KiCad circuit study</summary>

36-part capture with 101 physical pins checked. A fourth PMID capacitor follows DC-bias review; effective capacitance remains a curve-based planning estimate. Ten explicit ERC findings and unfinished power/pack integration. Not a charging or fabrication release.

![USB-C-fed 3S charger — native KiCad circuit study](docs/generated/charger-schematic/charger-test.svg)

[Source](hw/schematics/blind-charger/charger-test.kicad_sch) · [Generated files](docs/generated/charger-schematic/)

</details>

<details>
<summary>Regenerative clamp and thermal latch — native KiCad circuit study</summary>

38 parts and 105 physical pins checked. Two explicit external-power ERC findings. Pulse energy, response time, thermal coupling and sustained back-drive remain unqualified.

![Regenerative clamp and thermal latch — native KiCad circuit study](docs/generated/regen-schematic/regen-test.svg)

[Source](hw/schematics/blind-regen/regen-test.kicad_sch) · [Generated files](docs/generated/regen-schematic/)

</details>

<details>
<summary>3.3 V logic supply — native KiCad circuit study</summary>

12 parts and 31 physical pins checked. Internal 3.3 V divider; 1 A design envelope. Two external-power ERC findings. Biased capacitance, load transients, layout and hardware qualification remain open.

![3.3 V logic supply — native KiCad circuit study](docs/generated/regulator-schematic/regulator-test.svg)

[Source](hw/schematics/blind-regulator/regulator-test.kicad_sch) · [Generated files](docs/generated/regulator-schematic/)

</details>

<details>
<summary>Protected 3S2P carrier — native KiCad circuit study</summary>

33 parts and 103 physical pins checked, including three-cell sensing and six branch fuses. Fifteen explicit ERC boundary findings. Holder, thermistor, connector and secondary protection integration remain open; no battery fault safety or fabrication approval is implied.

![Protected 3S2P carrier — native KiCad circuit study](docs/generated/carrier-schematic/carrier-test.svg)

[Source](hw/schematics/blind-carrier/carrier-test.kicad_sch) · [Generated files](docs/generated/carrier-schematic/)

</details>

<details>
<summary>USB-C PD input — native KiCad circuit study</summary>

33 parts and 113 physical pins checked. Three explicit external-power ERC findings. Mandatory factory PD profile, surge behavior, startup and integrated charging remain unqualified; not a fabrication release.

![USB-C PD input — native KiCad circuit study](docs/generated/usb-schematic/usb-test.svg)

[Source](hw/schematics/blind-usb/usb-test.kicad_sch) · [Generated files](docs/generated/usb-schematic/)

</details>

<details>
<summary>Compact enclosure — provisional exterior</summary>

Earlier study, before PCB-mounted holders and independent shaft support. Initial compact direct-drive packaging candidate. Original parametric geometry; purchased-part fit and the holder-carrier alternative remain under review.

![Compact enclosure — provisional exterior](docs/generated/compact-closed/assembly.png)

[Source](cad/source/smart_blinds.scad) · [Generated files](docs/generated/compact-closed/)

</details>

<details>
<summary>Four layouts at the same scale</summary>

Earlier study, before PCB-mounted holders and independent shaft support. Calculated front footprints from the original packaging study. Dimensions and purchased-part envelopes remain provisional.

![Four layouts at the same scale](docs/generated/packaging-comparison/footprints.svg)

[Source](cad/parameters/packaging.json) · [Generated files](docs/generated/packaging-comparison/)

</details>

<details>
<summary>Compact enclosure — exploded study</summary>

Earlier study, before PCB-mounted holders and independent shaft support. Enclosure and internal fit study. Motor, cells and PCB are reserved envelopes; attachment and drive details are still being developed.

![Compact enclosure — exploded study](docs/generated/compact-exploded/assembly.png)

[Source](cad/source/smart_blinds.scad) · [Generated files](docs/generated/compact-exploded/)

</details>

<details>
<summary>Compact direct drive — packaging study</summary>

Earlier study, before PCB-mounted holders and independent shaft support. Compact direct drive with three cell columns and two depth layers. Provisional packaging study.

![Compact direct drive — packaging study](docs/generated/compact-assembly/assembly.png)

[Source](cad/source/smart_blinds.scad) · [Generated files](docs/generated/compact-assembly/)

</details>

<details>
<summary>Wide and shallow — packaging study</summary>

Earlier study, before PCB-mounted holders and independent shaft support. Six cells across one depth layer. Provisional packaging study.

![Wide and shallow — packaging study](docs/generated/broad-assembly/assembly.png)

[Source](cad/source/smart_blinds.scad) · [Generated files](docs/generated/broad-assembly/)

</details>

<details>
<summary>Narrow with right-angle drive — packaging study</summary>

Earlier study, before PCB-mounted holders and independent shaft support. Narrow footprint with a right-angle transmission envelope. Gears are not yet functional designs.

![Narrow with right-angle drive — packaging study](docs/generated/narrow-assembly/assembly.png)

[Source](cad/source/smart_blinds.scad) · [Generated files](docs/generated/narrow-assembly/)

</details>

<details>
<summary>Tall and shallow direct drive — packaging study</summary>

Earlier study, before PCB-mounted holders and independent shaft support. Two vertical rows of three cells in a single depth layer. Provisional packaging study.

![Tall and shallow direct drive — packaging study](docs/generated/slim-assembly/assembly.png)

[Source](cad/source/smart_blinds.scad) · [Generated files](docs/generated/slim-assembly/)

</details>

<details>
<summary>Battery life and wake-up cost</summary>

Source-generated energy scenarios, not measured runtime. Motor-branch current and awake logic are counted separately. Additional service wake time replaces idle; use zero if already included in a measured idle average.

![Battery life and wake-up cost](docs/generated/battery-energy/energy.png)

[Source](hw/sim/blind-control/plot_energy.py) · [Generated files](docs/generated/battery-energy/)

</details>

<details>
<summary>PD12V6Mini — inherited power-board reference</summary>

Existing e8s USB-C PD to 12.6 V power supply. This is not the new controller or a battery charger; no new hardware validation is implied.

![PD12V6Mini — inherited power-board reference](docs/generated/pd12v6mini-reference/assembly.png)

[Source](hw/layouts/pd12v6mini/pd12v6mini.kicad_pcb) · [Generated files](docs/generated/pd12v6mini-reference/)

</details>

<!-- previews:end -->

The enclosure views show original packaging studies with provisional motor and PCB envelopes.
The fresh integrated controller is still being designed; the inherited board is labelled separately.

## What's in the project

| Folder | Contents |
|---|---|
| `cad/` | Original packaging studies, enclosure sources and print/export instructions |
| `hw/` | Board sources, KiCad layouts, parts and simulation models |
| `firmware/` | Embedded control, calibration, safety state machine and tests |
| `integrations/` | Home Assistant coordination and integration as implemented |
| `bom/` | Per-unit, two-prototype and eight-unit cost/inventory records |
| `docs/` | Requirements, evidence, design comparisons and validation results |
| `tools/` | Reproducible documentation and preview generation |

## Development

The inherited electrical project uses atopile and KiCad 10. See [hardware instructions](hw/README.md).
The documentation renderer uses Python 3.11+ and KiCad 10; it reads layouts without regenerating them.

```sh
python3 tools/render_previews.py
```

CI renders registered sources on changes, uploads review artifacts for pull requests, and refreshes
committed previews on `main`. Source hashes and tool versions accompany the images. Print and
manufacturing releases must also pass the separate [validation gates](docs/verification-plan.md).

## Provenance

Created from private [e8s](https://github.com/0x63616c/e8s) at
`3ad0a29efcf933d6b887825998ced19d0c5ab11e`, preserving its history and working reference boards.
The original e8s repository is unchanged. Older Smart Shades, Smart Blinds and Packmule projects
are evidence sources only: [archive findings](docs/research/archive-findings.md).
Their architecture and completion claims do not carry forward into this design.
