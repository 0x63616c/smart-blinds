# Retained drive cartridge

This is a replaceable mechanical fit prototype, not a released enclosure. The source is `cad/source/drive_cartridge.scad`; `python3 cad/build_drive.py --render --export` produces source views, nine binary STL files and a source/mesh-hashed verification record. The separate [compact direct-support study](2026-10-19-compact-drive-and-holder-study.md) is the stronger wall-product candidate. This cartridge provides a comparison with an independently supported shaft.

The motor body remains at Z=28 mm. The bearing pods follow a selectable 0 or 7 mm shaft offset, so a different motor variant changes small fit parts. Two split clamps carry motor torque into a screwed base; two flanged bearings and captured bearing retainers carry the chain load into that base. A flexible coupling connects the shafts. Both shaft collars have explicit axial spacers, and the screwed chain guard attaches to the bearing blocks. The cosmetic shell is outside this load path.

The seller illustration shows a 6 mm axial boss **before** the 15.5 mm exposed shaft. The current model includes both, a provisional 64 mm body, a 4 mm rear encoder model and rear cable allowance. The boss diameter is a 12 mm allocation; it was not dimensioned by the seller. Can diameter 33 mm and can length 22 mm come from the listing. Gearbox length, actual encoder connector, mounting pattern, shaft offset and tolerances remain assumptions. Clamps rely on friction and require a torque/slip test; no positive keyed gearbox mount has been verified.

## Nominal stack

X is the shaft direction, Y runs up the wall and Z projects from the wall.

| Feature | X interval, mm | Detail |
|---|---|---|
| Motor can and gearbox | 12–76 | 64 mm family allowance |
| Front boss | 76–82 | 6 mm seller axial dimension |
| Motor shaft | 82–97.5 | 6 mm diameter, seller 5.4 mm flat |
| Flexible coupling | 89–114 | 8.5 mm motor insertion, 8 mm driven-shaft insertion |
| Driven shaft | 106–176 | 70 mm purchased D shaft, 5.5 mm flat |
| Left collar body / boss | 115–124 / 124–124.5 | 22.6 mm rotating screw envelope |
| Left spacer stack | 124.5–127.5 | 2 mm spacer plus 1 mm shim |
| Left bearing | 127.5–132.5 | Flange faces left |
| Wheel | 138–148 | 12 pockets; 6 mm chord pitch; 30 mm flange diameter |
| Right bearing | 153.5–158.5 | Flange faces right |
| Right spacer stack | 158.5–161.5 | 2 mm spacer plus 1 mm shim |
| Right collar boss / body | 161.5–162 / 162–171 | Screw envelope included |

The allocated case is **180 × 160 × 58 mm**, not a fully integrated enclosure. The 7 mm offset puts the guard at Z=53.5 mm; a 2.4 mm front wall leaves 2.1 mm nominal clearance. A 56 mm case would leave only 0.1 mm and is not retained. Pack, controller and fastener integration can change this allocation.

The source check verifies selected nominal gaps, STL closure/connectedness and a frozen input snapshot. It records SHA256 and byte size per mesh. It does not establish bearing alignment, sliding fits, backlash, material strength, creep, insulation, thermal performance or physical function.

## Print and assembly sequence

Print one base, the four motor-clamp halves, two bearing blocks, two bearing retainers, one wheel and one guard. The nine exported file types include repeated block/retainer parts. Export positions put every part on Z=0, but a slicer review is still required; curved clamp caps may need a different orientation or support. Use the [material and load-path guidance](material-and-retention.md), then qualify actual coupons at temperature.

1. Fit the bearing seats and shaft bore with small coupons before printing a complete case. Check the actual motor and collar fits. Replace the clamp halves/pods if the motor differs.
2. Capture the base and clamp nuts. Attach the lower motor clamps and both bearing blocks loosely. Leave the cosmetic shell off.
3. Insert the bearings without transferring pressing force through the balls. Fit the bearing retainers and their recessed screws. Align both bearings with the shaft before tightening the bases.
4. Build the shaft stack with spacers and collars. Position the wheel between the bearings and engage its radial grub screw against the D flat. Set a small measured axial running clearance rather than squeezing the bearing races together.
5. Fit the motor and coupling with the listed insertion allowances. The coupler screw sweep is 23 mm; the collar sweep is 22.6 mm. Verify free rotation and adequate engagement before tightening.
6. Fit the actual chain and the screwed guard. The open cord channel connects all bead pockets. Confirm that the chain exits freely and cannot climb out under the selected tension.
7. Test manually first, then with a current-limited drive at low speed. Check shaft drag, guard contact, clamp slip, stall behaviour and fastener loosening before applying blind load.

An archived 5 lbf pull corresponds to 22.24 N tension difference and roughly 0.258 N·m at the current pitch radius. The radial chain load is the **sum** of strand tensions: a 10 N slack-side preload would give about 42.24 N before dynamic effects. Neither that preload nor the archived force has been verified. Published bearing dimensions alone do not prove a load rating. Motor current limiting, jam force and actual material load tests still set the operating limit.

## Hardware and remaining work

The [mechanical drive BOM](../../bom/mechanical-drive.md) names the purchased reference parts and dated prices. They are easy-to-audit reference hardware, not a minimum-cost selection. They add approximately $25 per device before printed parts and screws, which is a major reason to investigate the compact direct-support alternative.

The cartridge still needs actual motor fit, shaft/coupler torque and bearing-load qualification, hardware insertion/access checks, print calibration and fatigue/creep testing. Its four base-to-enclosure fasteners and the final wall load path depend on the retained enclosure. No purchased parts have been ordered and no physical prototype has been tested.
