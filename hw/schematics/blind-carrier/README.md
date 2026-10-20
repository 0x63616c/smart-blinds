# Native battery-carrier schematic

This A3 circuit study captures the 33-part MAX17320 3S2P protection and gauge
block. KiCad independently exports the same 103 physical pin connections as
the compiled board. Tests deliberately miswire the three-cell sensing network,
bypass a cell fuse and bypass the current shunt; each is rejected.

The drawing follows the Rev12 three-cell connection: CELL2 joins CELL1 and the
second balancing resistor is omitted. The exposed pad joins RAW_GND, following
the manufacturer's implementation guide. CSN remains a separate Kelvin sense
connection to the protected side of the shunt. These net checks cannot establish
Kelvin layout, fuse coordination or cell safety.

Fifteen explicit ERC boundary findings remain: two external power inputs, two
thermistor inputs and eleven isolated interface labels (six cell positives,
two thermistors and three host signals). There are no hidden exclusions or
artificial power flags. Holders, thermistors, retained internal wiring and the
protected output connector still need integration. The independent secondary
protection decision is open; this is not a completed battery pack or a
fabrication release.

See `hw/boards/blind-carrier/README.md` for the fault boundaries, primary sources
and required physical qualification. Nominal values printed here are not
measured component performance.

```sh
python3 tools/generate_schematics.py hw/schematics/blind-carrier/carrier-test.layout.json --check
python3 hw/sim/blind-carrier/checks.py --check
python3 -m unittest discover -s tools -p test_schematic_graph.py -v
```
