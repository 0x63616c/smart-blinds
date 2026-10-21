# Bounded physical changes

No exterior, PCB, holder, motor, wire, fastener or button anchor moves. No additional installed piece or hardware SKU.

- The guard-boss link and nearby inherited roof clear the actual primary substrate and spacer end stop. The link is now 3 × 3.9 mm nominal. Its underside is Z39.1; FR4 ends at Z38.2 and the spacer stop at Z38.5. The full boss, screw and nut position stay unchanged. Removing 0.3 mm from the old roof only affects its lower edge; it does not cut a thin unsupported roof.
- The motor keeper remains unchanged. The cassette wall gains material inward and receives a radius 3.4 mm recess around the radius 2.9 mm keeper boss. Nominal radial clearance is 0.5 mm and local wall thickness is at least 1.8 mm at the deepest point. This changes actual printed material, not a component allocation.
- The two inherited right-side capture conflicts are cleared by bounded recesses. Integral outer seam bands retain 1.2 mm nominal thickness and extend the cassette locally from X92.4 to X93.8, inside the unchanged case. Capture max X92.2 has 0.4 mm to the new inner band face X92.6. The upper band ends at Y106.5, 0.4 mm before the guard wall at Y106.9. All spacer catches stay unchanged.

Fresh static solid tests include both shell halves against the spacer, actual contents allocation, frame, guard, clamp, fasteners, cover and backplate. Both full shell meshes also traverse the ±20 mm Z approach without intersecting unchanged spacer or contents. Printed fit allowance is not physical proof: the 1.2 mm band needs qualified extrusion/perimeters/orientation, and all load/creep/handling tests remain open.

Two initial diagnostic clearance boxes were too broad and included neighbouring shell seats. Their results remain in `first-relief-clearance-witness.json`. Corrected witnesses use the actual local FR4/stop footprint and vertical gap; complete-part intersection tests were never shrunk. A subsequent correctly located witness found the inherited roof's 0.3 mm gap; that failure remains in `inherited-roof-clearance-failure.json`, and the source now removes the bounded roof edge to provide 0.6 mm nominal clearance.
