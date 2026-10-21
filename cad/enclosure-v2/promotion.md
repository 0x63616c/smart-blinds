# Proposed canonical integration map

This package is a separate revision. Preserve the published 115 × 174 × 71 mm, 196-part/54 × 68.5 mm controller study and its reports as historical evidence; do not overwrite their input identities with this revision's current dimensions.

The package can move as a unit to `cad/enclosure-v2/` without runtime work-relative imports. Keep the public `source/*_v2.scad` modules, local `assets/`, copied `data/`, `parameters/`, `geometry/`, verification scripts and build/render/inventory drivers together. The historical utilities under `review/` and their exact comparisons are one-time review evidence, not routine CI prerequisites. The two cassette mesh operands must retain their provenance and exact hashes until separately replaced with analytic geometry.

`parameters/enclosure-v2.json` is the proposed mechanical contract. Its active physical board is the deliberately screened 03a6 metadata-native snapshot. The nested `placement_reference_only` object is retained historical documentary metadata from the prior consolidation; it does not override the top-level active PCB hash or the fresh actual-board report. Rewrite that historical proposal when integrating a final canonical placement checker, without silently changing older evidence. Main connector/button/MCU/motor/clip coordinates are enumerated by component address, reference, local origin, rotation and global datum. Global pose is a proper rigid rotation with components facing inward; no board or component mirror is permitted.

The controller source-placement checker should use these v2 requirements:

- 54 × 80 mm body; exact rounded outline/notches in the declared source primitives; no USB tongue.
- 206 physical footprints in the source reconciliation, with eight explicit PicoBlade plastic-foot F.Cu restrictions. These eight are not substitutes for the antenna, clip, tail, cable and component-height reservations.
- UP at local (52,50), DOWN at (52,30), preserving their existing logical nets/GPIOs.
- USB (29.5,5.75,0°), pack (45.5,69.5,180°), encoder (49,40,90°), optional home (49,20.5,90°), motor lands (51.5,57) and (51.5,63).
- Upper clip local (54,76), lower clip (0,7), with the exact bare lands/round notches and current rear-face reliefs. Neither contact checks nor pose checks should be inferred from the old v1 interface JSON.

The source-preview manifest can call `source/assembly_v2.scad` for closed, cover-off, service and button views. Keep `optional_plugs=false` as the mechanism baseline; show the optional plugs separately with their provisional retention label. The render source uses a real white case, visible cover screws, a provisional chain at the actual exit and wall scale; it does not claim a complete native populated PCB model.

CI should run parameter consistency, sequential core/auxiliary exports, the complete 17-job verification suite, inventory and source-export relief views, then verify report hashes. Upload the exact STLs, report JSON, images, print list and checkpoint. A single job can reuse successful fresh exports, but must not restamp evidence when its inputs change. Retain explicit failed controls and historical known-failure snapshots.

Promotion itself does not authorize fabrication. Physical motor/holder/chain fits, electrical and thermal qualification, real cable construction/trim/strain relief, button setting/return, print strength and assembly repeatability remain separate gates.
