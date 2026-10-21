# Reviewed native receipt policy successor

This work-only successor fixes the original gate's rejection of a valid fresh CI artifact. The original candidate and failed parent log remain unchanged. No native CAD, renders or full fit checks ran.

Promote the two tool files into `tools/` and `approved-native-inputs.json` into `cad/enclosure-v2/`. The manifest schema is now `smart-blinds.enclosure-native-inputs.v2`. Repository input coverage remains the same 119-file public-51cd391 closure; source-only previews remain a source/copy guard without current native verification.

## Observed failure and precise correction

The whole-receipt byte pin was introduced to bind all native evidence, including the DRC results. Parent's actual downloaded CI run `39602067230` has the exact same 03a6 board, project, source capture and every native receipt field except `drc_sha256`. Its DRC report is not byte-stable:

- Local date `2026-10-21T12:28:30`; CI date `2026-10-21T12:49:57`.
- Nineteen unchanged missing-connection endpoint pairs reverse item order.
- Two missing USB data connections select different track representatives. Each pair of selected tracks shares an **exact endpoint on the same net and layer** in the fixed board: USB_DM at `(130.75,166.25)` and USB_DP at `(130.25,165.75)`, both In2.Cu.
- The three named violations, settings and 352 missing connections remain unchanged. Merely deleting the date and sorting the original findings does **not** make the reports equal.

`diagnosis.json` records both artifact hashes and the exact differing representatives/segment proofs. No artifact is accepted by an allowlist of CI hashes.

The successor pins **every receipt field except `drc_sha256`**, including source/board/project hashes, KiCad version, status, native post-save project hash, retained violation counts, library count and all validation flags. Unknown receipt fields or changed field types fail. It additionally requires adjacent `candidate.kicad_pro` and `drc.json`; their actual bytes must match the current receipt hashes. The reviewed old `native_receipt_sha256` remains historical provenance in the manifest; it is no longer the fresh-receipt acceptance predicate.

DRC semantic comparison preserves all content except these deliberately bounded changes:

1. A valid ISO timestamp is checked and omitted.
2. Finding and item ordering is canonicalized, with duplicates preserved.
3. Only missing-connection items naming an actual straight segment may use an equivalent representative. The report item's UUID, exact start position, net/layer text and four-decimal length must match that segment in the exact hash-bound board. It then maps to the sorted UUID set of straight segments joined by exact shared endpoints on that same net and layer.

There is no proximity tolerance, crossing/overlap inference, layer transition, via, pad, arc or zone connectivity inference. The helper is a report-representative equivalence rule, not a replacement for native connectivity validation. All non-track items, finding types/severities, ignored checks, schema/source/version/settings and unknown fields remain in the semantic hash. Unknown track fields fail explicitly. Actual report totals also must agree with the pinned receipt.

Both real reports produce semantic hash:

`32384247798430524280004074e9fff880595ae05e5017eea9b4bc3606e73b46`

## Integration

Full mode still requires the existing native job's artifact; do not substitute the copied board or a linked metadata variant:

```sh
python3 tools/check_enclosure_board_binding.py \
  --repo . --package cad/enclosure-v2 \
  --native-board work/current-main/clean-main-native/candidate.kicad_pcb \
  --native-receipt work/current-main/clean-main-native/native.json \
  > work/enclosure-v2-native-binding.json
```

The project and DRC files must accompany that pair in the same directory. The workflow job/artifact dependency supplies CI-run provenance; the pure file checker does not authenticate a run independently.

Preview mode remains explicit and never substitutes for full mode:

```sh
python3 tools/check_enclosure_board_binding.py \
  --repo . --package cad/enclosure-v2 --source-only \
  > work/enclosure-v2-preview-binding.json
```

Changing live routing/placement/model inputs, the active contract, copied board or actual count still fails. A new 211-via board requires deliberate physical review and rebinding. Neither mode updates approval or proves fit. Preserve all ordinary enclosure/contact/service checks after the full binding gate.

## Exact evidence

- `test-evidence.json` and `test.log`: **58 controls passed**, plus both real local and downloaded CI artifact checks and source-only acceptance. Controls reject unrelated or near-but-disconnected representatives; changed net/layer/length/position; unknown fields; fake counts; missing or mismatched DRC/project; true extra violations; stale same-count sources/poses; 211-via successors; mode fallback and input races.
- `cli-evidence.json`: actual local native, CI native and source-only CLI acceptance; no-mode CLI rejection.
- `comment-only-delta.json`: final parent-requested explanatory comment changed the tool bytes after those tests. Its before/after SHA256 and identical Python AST prove no executable change. Earlier evidence retains its original tested hash; it is not restamped.
- `test-evidence-before-type-guards.json` and matching log preserve the earlier 56-control pass before adding strict receipt field types and near-endpoint rejection.

Synthetic controls use temporary fixtures. Their explicit reapproval helper only isolates deeper checks and is not a real manifest updater. The real checks use exact temporary package copies so the frozen geometry checkpoint remains untouched.

Reproduce synthetic tests with `python3 tools/test_enclosure_board_binding.py`. For the real pair comparison add `--real-repo`, `--real-package`, `--native-board`, `--native-receipt`, `--ci-native-board`, `--ci-native-receipt`, `--approved-manifest` and `--evidence`; see recorded artifact directories in `diagnosis.json`.
