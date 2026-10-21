# PCB binding review

The maintained implementation is [check_enclosure_board_binding.py](../../../../tools/check_enclosure_board_binding.py), with [failure controls](../../../../tools/test_enclosure_board_binding.py) and the [approved manifest](../../approved-native-inputs.json).

The gate requires the exact reviewed board, adjacent project, current source inputs and all native receipt fields except the DRC report hash. That hash must instead match the actual adjacent report, whose content must match the reviewed findings after narrowly normalizing its timestamp, item ordering and proven equivalent connected-track representatives. No clearance rule, allowed violation or physical-board identity is relaxed. [Diagnosis](diagnosis.json) records the observed local/CI discrepancy and the precise equivalence proof.

The files here retain the pre-integration review, including its [original notes](candidate-readme.md), exact evidence hashes and the earlier whole-receipt comparison failure rationale. Paths in those records identify historical inputs; they are not required runtime dependencies. The three source files named in `handoff.json` now live at the maintained locations above; the historical `README.md` entry is retained as `candidate-readme.md`.

The parent independently replayed all 58 controls against the final commented code and the downloaded native CI artifact. Its fresh receipt and log are `binding-v2-parent-controls.json` and `binding-v2-parent-controls.log`. The older candidate evidence is preserved with its original tested hashes.

Full CI takes its board/project/receipt/DRC from the native job in the same workflow, then runs all enclosure geometry checks. Preview mode only checks current approved sources and the copied board; it explicitly performs no native verification. A new PCB requires reviewed rebinding and new geometry evidence. Neither mode approves fabrication or establishes physical fit.
