# Promotion map onto public main 51cd391

Parent integration only; this work package does not edit canonical files. Keep the original frozen source/checkpoint and this successor's 17-job evidence immutable. Routine CI produces new evidence; it must not restamp the human-reviewed snapshot.

## Paths and history

| Destination | Action |
|---|---|
| `cad/enclosure-v2/` | Add this package's sources, local assets/data, parameters, geometry, builders, verifiers, references, docs and frozen evidence. No normal runtime imports another work folder. Keep the two inherited cassette mesh operands and their exact provenance explicit. |
| `docs/mechanical/enclosure-v2.md` | Add the current 118 × 196 × 77 candidate summary, proper inward PCB pose, service sequence and links to `cad/enclosure-v2/inventory.md`, `service.md`, `handoff.md` and `print-list.csv`. |
| `bom/README.md` | Make the v2 22-piece / 21-shape list current; distinguish two optional caps, one shared button nest and the older eight-piece holder fixture, which is not requalified here. Do not add historical and current installed-piece volumes together. |
| `README.md`, `docs/status.md` | Lead with current exterior, cover-off and service views; say nominal geometry checks pass but motor/holder fit, load, cable, insulation, print strength and complete home path remain open. Retain the original 115 × 174 × 71 case as collapsed historical evidence, with its orientation error label. |
| `docs/previews.json` | Prepend the entries in `review/public-preview-entries.json`; keep old case IDs collapsed and explicitly historical. No old assembly image is silently relabelled as new. |
| `.github/workflows/design-checks.yml` | Add the v2 job and current-native-board binding gate below; add `cad/enclosure-v2/**` to both path filters. Retain old retained/workshop jobs as historical checks until independently retired. |
| `.github/workflows/design-previews.yml` | Existing `cad/**` filter already covers v2. Add `python3 cad/enclosure-v2/prepare.py --check` before the central source renderer. |

`references/motor-service-cables.md` now contains the cable primary-source URLs and dated availability boundaries. `references/historical-maintained/` retains the original checkpoint, exact migration and verification records, and missed-pair audit. Its freeze ID is readable without a work checkout. The one-time historical comparison scripts are review evidence, not routine CI dependencies. Raw historical command logs may retain their original paths; they are not live links or runtime imports.

## Mandatory current-board binding

This checkpoint fits **03a6b3dc… / 206 parts / 120 rear vias**, not whatever board happens to be latest later. The newer charger trial with 211 vias and six pose changes must invalidate that fit claim until deliberately reviewed. Do not overwrite the copied board automatically and do not let its old checks remain a green current-fit badge.

Add a small pure-file integration gate, proposed `tools/check_enclosure_board_binding.py`, before heavy v2 work. It must take the native `candidate.kicad_pcb` and `native.json` from the same CI run's `current-partial-controller-route` artifact, produced by the existing `native-schematic` job. Use the original saved native candidate, not the linked-project metadata variant. Require all of:

1. The actual artifact file hash equals `native.json.board_sha256`; its receipt confirms unchanged source inputs and successful saved-board physical checks.
2. That hash equals the active `parameters/enclosure-v2.json.physical_board.sha256` and the copied `data/physical-board.kicad_pcb` hash. Count all actual footprints and vias against the contract.
3. A mismatch or missing artifact exits nonzero before publication. Never substitute the older copied file for the requested current artifact, waive by equal part count, or silently update the expected hash.

Controls should reject a changed byte, a new native receipt paired with the old copied board, a missing artifact, and the 211-via successor. Deliberate rebinding updates the local board, expected hash/counts and any affected poses/constraints, then regenerates source-bound geometry/contact/service evidence. If a later metadata-only board change is accepted, record its exact geometry-equivalence proof rather than merely changing the SHA.

The old v1 main placement checker and `cad/parameters/retained-interfaces.json` remain historical. Current placement checks must read the v2 54 × 80 outline, 206-part contract and proper pose; the eight PicoBlade foot restrictions do not replace antenna/cable/retainer restrictions. `promotion.md` enumerates current connector, button, motor-pad and clip coordinates. Its nested `placement_reference_only` is historical metadata, not the active board authority.

## CI commands and artifacts

Proposed `enclosure-v2-fit` job: `needs: native-schematic`, Ubuntu 24.04, initially 40-minute timeout, one sequential worker. Install OpenSCAD, Xvfb, Xauth and a Python virtual environment; install the recorded Python dependencies `numpy==2.3.5` and `manifold3d==3.3.2`. Linux execution is a new portability check, not an already observed pass.

After downloading the native artifact to `work/current-main`, run the binding gate on its `clean-main-native/candidate.kicad_pcb` and `native.json` with the active contract. Then:

```sh
xvfb-run -a work/enclosure-env/bin/python cad/enclosure-v2/rebuild.py --stages parameters export check inventory render
```

The current package records 29 core exports plus one service-hardware operand; all 17 verifiers and all four preserved overlap controls are required. `inventory.py` validates exact fresh hashes and one closed connected component per installed print shape. Upload `exports/`, fresh export/current-export/verification/inventory reports, verification logs, the four relief images, their render report and `print-list.csv` under a distinct `enclosure-v2-fit-candidate` artifact.

Do **not** run the default all-stages command or `freeze.py` as a routine CI restamp: the final freeze additionally binds one-time baseline comparison and human visual-review evidence. CI should create new provenance through the stated stages, preserving the reviewed checkpoint as a separate immutable record. The old material-budget workflow remains a historical budget; present the v2 inventory artifact separately until its aggregate consumer is deliberately updated.

## README previews

`review/public-preview-entries.json` supplies five source entries: closed, assembly, service, buttons and optional plugs. All use `cad/enclosure-v2/source/assembly_v2.scad`, with explicit cameras, `auto_frame:false` and local dependency globs. Default buttons are integral/plain; plugs remain optional. The closed/assembly/service entries are expanded ahead of all historical cases; button details can be collapsed.

The promoted central renderer should generate fresh current assembly/service views from those sources. No additional full views were rendered for this bounded clearance correction. Earlier full exterior/button images depict exactly unchanged parts but remain historical evidence; the four new local cutaways are source-bound OpenCSG previews. They do not replace full geometric checks or a fresh published current-source preview run.
