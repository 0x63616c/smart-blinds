# Assembly and fit qualification

The first print is a coupon set and non-powered mockup. An STL existing and passing a closed-mesh check does not establish load capacity, electrical insulation, safe battery mounting, print quality or compatibility with the owned motor.

## Parts and intended assembly

1. **Backplate:** rounded 3 mm plate, locating rim, three elongated mounting slots, removable pack/motor interfaces and captive-nut provision for the underside cover screw. The slots provide provisional ±4.7 mm adjustment around a 4.6 mm screw clearance. Select anchors for the actual wall material and prove the loaded wall mounting.
2. **Insulated pack cradle:** retains a separately insulated and protected 3S2P module. Printed plastic is mechanical support, not the sole cell or busbar insulation. Carrier tabs and smooth nonconductive straps need a real service/removal demonstration. No printed loose-cell holder contacts are proposed.
3. **Motor lower saddles, two:** preliminary clamp saddles with strap channels. An actual upper retention method, torque-reaction restraint, flange measurements and screw engagement must be qualified. The saddles alone are not ready for a powered motor.
4. **Chain wheel:** 12 pockets on a 6 mm chord pitch; provisional 6 mm D-shaft interface. Print and test coupons before using the whole wheel. No assured shaft fit, retention or wear rating is claimed.
5. **Chain guard:** first geometry for a removable guard; fastening support and both exit paths need further work. It is not represented as an accepted child-safe tensioner. Keep a supported, tensioned chain path and verify applicable installation requirements before release.
6. **PCB carrier:** a reserved removable support frame. Electronics mounting-hole positions are provisional. The antenna zone must remain clear of cells, metal fasteners, motor wiring and copper according to the chosen module guide. Carrier attachment and connector strain relief remain unresolved.
7. **Two button plungers:** candidate geometry only; exact switch height, travel, operating force and captive retention must be set with the chosen PCB switches.
8. **Front cover:** white rounded shell with underside USB-C, chain exits, two button openings and one underside retention screw. The locating rim uses 0.35 mm nominal clearance. Print that interface as a coupon before assuming the printer reproduces it.

Use a separately manufactured/qualified welded battery assembly with appropriate cell matching, positive-end insulating rings, inter-cell insulation, protected busbars, strain-relieved taps and a temperature sensor. The electrical design must specify protection and fuse behavior. **Do not treat the CAD's individual green cells as permission to connect loose cells directly.** The drawing presently allocates space rather than specifying a qualified welding process, wire gauge or fuse.

## Measurements that change the design

| Item | Needed before full fit release | Why |
|---|---|---|
| Motor | Body and encoder lengths/diameters, shaft length/D-flat/eccentricity, mounting holes and thread depth | Current envelope is an assumption; a 7 mm shaft offset would move the chain path materially |
| Motor output | Permissible radial load or load test | The chain applies side load to the gearbox shaft; separate support might be needed |
| Chain installation | Both strand offsets from the wall, side clearance, coupling and knot envelope, available mounting surface, left/right arrangement | The existing perpendicular chain plane is known, its placement is not |
| Pack | Finished 3S2P dimensions, wrap and insulation thickness, leads/connector and bend envelope | Cells alone do not define a finished pack |
| Printer/material | Actual filament grade, extrusion calibration, hole/shrink behavior, warm-wall/charging temperature | Fit and creep cannot be inferred from nominal filament color |
| Electronics | Board outline, mounting holes, antenna guide, tallest parts, USB and switch coordinates | The current board is a 75 × 35 mm reservation |
| Blind mechanism | Travel versus encoder counts at several positions, repeated up/down drift, slack and slip | Matching motor RPM does not guarantee aligned fabric edges |

The chain wheel's ideal pitch radius is **11.591 mm**, nominal chain speed at 111 RPM is **133.2 mm/s**, and a 22.24 N pull implies **0.258 N·m** before losses, acceleration and margin. These are calculations, not motor capability tests. Slower closed-loop motion and controlled ramps should be used; the listing RPM is not a guaranteed loaded speed.

## Acceptance sequence

- Inspect every purchased cell and measure the completed insulated pack without exposing terminals; first use inert dummies for fit checks.
- Print diameter, shaft, seam and chain coupons. Record actual measured dimensions and accepted clearances.
- Dry-assemble case, inert pack, motor, PCB dummy, USB plug and wires. Check every screw can be installed and removed and no wire crosses the chain path or touches sharp edges.
- Test chain wrap, retention, reverse direction, sag and full travel at all seven locations. Address accessibility and loop entanglement in the final installation; a decorative guard alone is insufficient.
- Measure torque, radial load behavior, current and temperatures under normal, high-load and jam conditions; define overload stop and recovery in firmware.
- Verify charging heat, pack temperature, motor heat and printed-part creep in the assembled case.
- Test radio connectivity in the actual wall-mounted orientation with the final battery and screws.
- Only then freeze printable parts, pack construction and hardware release. Regenerate all views from that same source revision.
