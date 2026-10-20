# Connector checks

The physical six-pin assignment is checked against the compiled KiCad board.
A deliberately swapped power pair must fail. Finished signal/locator hole
geometry is checked independently against the manufacturer drawing and then
compared to the compiled footprint. Results retain source, board and graph
hashes. This does not establish fit, current capability or safe pack assembly.

Generate with `python3 hw/sim/blind-connectors/checks.py`; verify the saved
report with `--check`. The parent integrated board needs its own end-to-end
assignment check after composition.
