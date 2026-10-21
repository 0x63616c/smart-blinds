# Bounded enclosure v2 clearance successor

Work-only candidate; no canonical geometry, PCB circuit, placement, native KiCad job, commit or push was performed for this correction. The exterior remains **118 × 196 × 77 mm**. The integral button faces reach Z78.8; optional cosmetic plugs reach Z79.5.

## Concrete change

Only the front and rear cassette print shapes change. The guard-boss link/roof clears the actual primary substrate and spacer stop. A bounded recess clears the unchanged motor-tail keeper boss, with at least 1.8 mm local nominal wall. The right-hand capture recesses retain 1.2 mm integral outer bands; their local X extent grows from 92.4 to 93.8 inside the same exterior. No PCB, holder, motor, wire, fastener, button or spacer-catch anchors move. No printed piece or hardware SKU is added.

`review/changes.md` gives exact dimensions and distinguishes nominal clearance from print/load qualification. Four original material conflicts remain reproducibly positive regression witnesses: front versus substrate, front versus motor frame, front versus spacer and rear versus spacer. The initial diagnostic witness mistakes and the later real roof-gap failure are preserved without rebinding old evidence.

## Deliberate board revision

The local saved board is SHA256 `03a6b3dc624e2cf0e83f8cfdd90f64dc52071fb2b8387deb0e22949903981e74`: 206 footprints and 120 rear vias. Compared with the historical 4102 board, only three physical component poses change: R95 to (32.5,12.75,0°), R96 to (32.5,11,90°), and D5 to (32.5,8.75,0°). The exact outline and model attachments remain unchanged. `review/board-rebind-delta.json` records the comparison; the fresh actual-board check independently reads this local file. It uses conservative courtyard body extrusions and connector tail/hole reserves, not substituted-model or vendor-tolerance acceptance.

## Current evidence

All 17 jobs passed in the fresh 340.8-second sequential replay. This includes 2,170 current-board component/tail comparisons and all 120 rear vias; 27 new cassette static/approach checks and three material witnesses; and the retained service, extraction, cable parking, button and clamp controls. The four original overlapping pairs must still fail against their historical shells. The button check retains the rejected no-nest alternatives rather than claiming those paths work.

The six full pack-wire polylines were additionally checked against both corrected shells in all three assumed row-height cases: 36 comparisons passed, with a minimum sampled-polyline clearance of 0.4247 mm after the existing 1.85 mm wire-OD and planning allowance. That is geometric clearance, not verified cable bend, contact-row tolerance or strain relief performance.

The fresh export gate originally stopped before any geometry job because it selected an older same-source export record. Its failure is retained. The corrected gate selects the latest source-current record per role, checks the actual file hash, and refuses fallback to an older output. Five controls pass. No geometry was repaired, regenerated or restamped to address that validator bug.

## Inventory and remaining limits

The base remains **22 installed pieces / 21 shapes per blind; 176 pieces for eight**. Optional plugs add two pieces per unit; the one button assembly nest is shared tooling. The older eight-piece holder-loading fixture is separate and not requalified here. Exact dense mesh volume is 369.2393486 cm³/unit, or 468.934 g using the historical 1.27 g/cm³ PETG assumption. This is not a slicer, purchase or structural estimate.

The maintained runtime is local to this package. The two inherited cassette mesh operands remain explicit: this is bounded editable Boolean CAD, not a fully analytic or freely resizable cassette. The historical comparison utilities are one-time review tools, not normal build dependencies. `dependencies.md`, `promotion.md`, `inventory.md` and `service.md` describe those boundaries and the coordinated future integration.

Physical motor/holder/chain fit, connector variants and contact-row datum, flexible cable forming/trim/force, actual hand/latch/catch access, solder/insulation protection, silicone pull strength and creep, button setting/return, PETG strength and optional cap retention remain unqualified. The optional home sensor and complete cable route remain unfinished. Existing blind holding is owner-reported and must survive the added chain path. No fabrication or complete physical-assembly acceptance is implied.

## Final comparison and visual review

The final comparison confirms **28 unchanged export roles**: 27 have exactly equal float32 triangles; the touching service-hardware assembly has exactly equal float32 vertices and integer-plane directed boundary multiplicities, with only coplanar diagonals differing. The latter proof is restricted to that auxiliary role and has alternate-diagonal and moved-surface controls. Front and rear are the only changed print shapes. No numerical distance/volume tolerance or mesh repair is used. The strict comparator stop is preserved.

All four new detail images were inspected. The initial CGAL cutaway render asserted and is preserved; the final views are OpenCSG source-export previews of identical geometry. Their narrow link/capture gaps are partly occluded, so they are orientation/detail evidence backed by the full-solid tests, not visual distance measurements. Current images are `renders/relief-link.png`, `relief-motor.png`, `relief-upper_capture.png` and `relief-lower_capture.png`. The overall exterior and buttons are unchanged; fresh public assembly/service views should be generated from the promoted sources.

`promotion-public-main.md` gives exact destination paths, CI commands/artifacts, current-native-board invalidation and README preview ordering onto public main 51cd391. `review/public-preview-entries.json` supplies the proposed entries. The current board fit is explicitly pinned; a later 211-via/six-pose charger board cannot silently inherit it. All user-facing cable/history references are local or primary web URLs.


## Exact selected file hashes

- `parameters/enclosure-v2.json`: `7b00c0977d70f8479589bc36594e5589f898a9e3fa7608fe25ec569b6dce593e`
- `source/definitions.scad`: `7e158ddde12b27f3b82b929e3472cd414397bed086db700f4fd10aee8450c952`
- `verify.py`: `622db664fc6a654d2388beeac15bc4d171793b7c0c8e88161f8e6e87ea494ee2`
- `evidence/verification-run.json`: `c30bc90c19e9e26b8e08852d425d1b32b737be1b7be42760a52a8191a5c0298f`
- `review/baseline-comparison.json`: `3c8f0cb6c7a757608aa9964ed77a5a1707ce1294bceaa91e577a88465ae1757e`
- `review/render-report.json`: `ddb6eacab16d99857f1df4f2122d1f153784531544470edf84952a67c45a0ac1`
- `review/visual-review.json`: `68ef71f6d343e1ae801133a652c37d4f6ae147d72b5761fb791de60874a83624`
