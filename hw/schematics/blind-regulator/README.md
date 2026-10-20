# Native logic-supply schematic

This A4 drawing captures the 12-part TPS62902 3.3 V supply from the charger's
SYS output. KiCad's exported netlist matches all 31 physical PCB pins. The
separate regulator connection contract also checks the selected components,
physical pin numbers and footprint pads.

FB/VSET is deliberately open to select the internal 3.3 V divider. The 1 A
design load is a provisional envelope, not a verified continuous board rating.
Two explicit external-power ERC findings remain for SYS and ground; there are
no exclusions or artificial power flags.

The drawing shows nominal capacitor values. Typical DC-bias curves, tolerance,
temperature and an explicit aging allowance inform the effective-capacitance
estimate in `hw/sim/blind-power`. The estimate is not a guaranteed production
minimum. The roughly 65 mV static margin above the supervisor's maximum reset
release threshold does not establish load-transient behavior.

Input clamping, full-board integration, layout, converter stability, thermal
performance and hardware measurements remain open. This capture is unrouted
and is not a fabrication release.

```sh
python3 tools/generate_schematics.py hw/schematics/blind-regulator/regulator-test.layout.json --check
python3 hw/sim/blind-regulator/checks.py --check
python3 hw/sim/blind-power/check_capacitance.py --check
```
