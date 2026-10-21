# Cleaner controller layout — working source

Open `placement.kicad_pro` in KiCad 10. Local footprints and all referenced 3D
models are included. This is the editable 54 × 80 mm, four-layer controller study.

**Partial routing: 417 connections remain open. Do not order or fabricate it.**
The earlier canonical board under `hw/routing/blind-main/` remains a historical
checkpoint. This study is not a replacement fabrication release, and the older
196-part schematic does not yet describe this 206-part input-protection candidate.

The current study has gridded component poses, outward edge connectors, a rounded
outline, black mask and 45°/90° routing. Top routes avoid component bodies except
for narrowly reviewed own-pad connections. Its USB-C protection routes pass
through the actual clamp lands. The local PD ground island is actual saved copper;
continuity and clearance checks do not establish transient or thermal performance.

`review.json` records the current partial-route findings. `source-sha256.json`
records the initial imported v16 source/model/footprint bytes; it is historical
provenance, not a lock that prevents design edits. Update the review findings when
the study changes. The normal preview workflow renders these source files and
records fresh hashes; edit this source and register any new model dependencies
rather than replacing the README image by hand.

See [the layout review](../../../docs/reviews/2026-10-21-clean-layout/pd-routing.md)
and [placement/routing requirements](../../../docs/electrical/routing-style.md).
