# Review evidence roles

This folder retains failed and intermediate trials so a later passing result does not erase their provenance. The normal package runtime does not import the frozen sibling package.

Current acceptance evidence is the fresh `evidence/verification-run.json`, its individually bound reports, the current source-bound export manifests, `baseline-comparison.json`, `board-rebind-delta.json`, `pack-relief-clearance.json`, `render-report.json`, and the final `visual-review.json`. Only the final `checkpoint.json` binds the complete selected set. Physical assembly is not accepted by these geometric checks.

`compare_baseline.py` and `board_rebind_delta.py` are one-time historical comparisons. They read the frozen `enclosure-v2-maintained` sibling to demonstrate unchanged roles and the deliberate PCB revision; they are not geometry/build dependencies.

The earlier `relief_trial`, `capture_relief_trial`, and `shell_motion_trial` reports retain their original inputs. `first-relief-clearance-witness.json` documents initially overbroad diagnostic boxes; the note explains why those boxes included adjacent seats. `inherited-roof-clearance-failure.json` is the subsequent correctly located nominal-gap failure that caused the roof-edge relief. None of these earlier reports is silently rebound to the final geometry.

`manifest-gate-failure/` preserves the validator entry failure before any fresh geometry job ran. The replacement selection logic chooses the latest source-current export per role, verifies its actual output hash, and does not fall back to an older matching output when the latest output is missing or changed. Five controls are recorded in `manifest-selection-controls.json`.

The four original material overlaps are also replayed as positive regression witnesses by `verification/cassette_reliefs.py`. Their continued detection is separate from the corrected shells passing their new pair and approach checks.

The initial exact-triangle comparison stopped at the multi-part `service_hardware` export; `first-baseline-comparison/` preserves that stop. Only this auxiliary touching assembly may use the predecessor's exact vertex/integer-plane boundary proof for alternate coplanar diagonals. All 27 unchanged printable/other roles preserve their exact float32 triangles; the front/rear changes are intentional. No distance or volume tolerance is used.

`first-detail-render/` preserves a CGAL assertion during imported-mesh cutaway rendering. The final four views use OpenCSG preview of the same exported source geometry. Small crop fringes and partly hidden gaps are recorded in the visual review; these images are not clearance measurements. Independent full-solid checks provide the geometric results.
