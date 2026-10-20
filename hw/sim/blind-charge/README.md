# Charger calculations

Run `python3 hw/sim/blind-charge/checks.py` from the repository root. `--write`
refreshes `results.json`. This is fixed-network arithmetic, not SPICE and not a
BQ25798 control-loop model. Exact source parts and rail expressions are checked
against `hw/boards/blind-charger/charger-ratings.json`; a generated BOM, when
present, must also agree.

Checks cover the startup ILIM divider, nominal NTC curve and comparator/resistor
corners, steady voltage ratings, ordinary resistor dissipation, and conservative
buck/boost inductor ripple. The nominal 3S thermistor network's cold/hot crossings
are not safe charging-temperature guarantees. NTC tolerance and mounting are
excluded explicitly. The current-limit calculation is a command estimate, not
100 mA USB pre-enumeration compliance or a measured input current.

Charger, cell-protection and switching stability still require vendor-model work
where available, a routed board, and instrumented physical tests. The existing
`blind-control` ideal regenerative model is separate and does not implement an
actual protective clamp.
