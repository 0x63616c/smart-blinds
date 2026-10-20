# Native charger schematic

This A3 drawing reproduces the current 36-component charger capture. KiCad's
exported netlist independently matches all 101 physical PCB pins. The separate
reviewed charger connection contract checks the circuit against physical pin
numbers rather than merely comparing two generated views.

The drawing displays nominal capacitance. A fourth PMID capacitor was added after
checking Samsung's typical DC-bias curve against TI's effective-capacitance minima.
The [sensitivity check](../../sim/blind-power/check_capacitance.py) includes part
tolerance, temperature and an explicit aging allowance. It is a planning estimate;
it does not guarantee production capacitance or converter stability.

There are ten explicit ERC findings and no exclusions:

- Three external power nets: VBUS, BAT and ground.
- An external SCL driver and five single-pin external interfaces.
- ACDRV1/2 use generic output pin types and share ground. TI SLUSDV2C page 5
  explicitly requires both pins grounded when the external input FETs are absent.
  This mode-dependent connection is retained and documented rather than hidden.

The exposed pad is **PMID, not ground**. D+/D− and QON remain deliberate isolated
no-connect pins. The thermistor is external, and its connector is not part of this
capture. USB input entitlement/switching, protected pack, power-domain isolation,
complete routing and physical charging tests remain unfinished.

```sh
python3 tools/generate_schematics.py hw/schematics/blind-charger/charger-test.layout.json --check
python3 hw/sim/blind-charge/check_connectivity.py --check
```
