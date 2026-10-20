# Clamp verification scope

`checks.py` validates exact MPN/import identity, the compiled PCB's 105 physical
pin connections, corrected resistor lands, and conditional rating arithmetic.
Its independent pin contract rejects five altered graphs: grounded sense input,
lost latch feedback, loss of independent supply, bypassed thermal FET, and a
bypassed bank resistor. It checks an ignored local compiled BOM when available;
absence of that BOM is not a fresh build claim.

`run_spice.py` runs six **generic topology experiments** with ngspice. The PNP
uses an illustrative model, the MOSFETs are threshold-controlled switches, the
TLV6710 has its nominal hysteresis plus an assumed RC lag, and the thermostat
receives an injected hot signal. None are vendor-validated models or a thermal
model of the PCB.

The latch stays off during 1 µs, 1 ms and 40 ms supply ramps, holds a simulated
trip after its trigger clears, and releases after a modeled power cycle. This
checks feedback polarity; real leakage, slow brownout, TMP output behavior and
transistor spread remain unverified. TI's TMP302 power-on discussion says the
output is typically valid after 35 ms; §9 also says fully functional within
35 ms. No maximum startup row is given in the electrical table.
The latch drive includes three 1 nF gate-load allowances: cutoff, hold and the
parent controller's separate fault-indicator MOSFET.

The dump experiments inject a 20 ms current pulse after startup:

| Stimulus | Simulated peak | Interpretation |
|---|---:|---|
| 0.5 A, 220 µF, 0.05 Ω ESR, 30 µs lag | 14.08 V | Nominal topology case |
| 2 A, 176 µF, 0.2 Ω ESR, 100 µs lag | 15.02 V | Assumed stress case |
| Same with 1 ms lag | 18.79 V | Deliberate failure against 18 V design ceiling |

An RC lag is not a pure time delay. The separate full-delay arithmetic gives a
higher 26.44 V estimate for 1 ms. Neither number predicts an actual TLV6710
fault. The point is that response time is a material design constraint, and a
successful nominal waveform cannot prove safe operation.

`spice-results.json` contains measurements and template hashes; `waves/` holds
downsampled traces. They are source-checkpoint evidence, not hardware test logs.
The output-capacitor curve excerpt is typical manufacturer data with separate
tolerance, temperature and aging factors in the arithmetic.

```sh
python3 hw/sim/blind-regen/checks.py --check
python3 hw/sim/blind-regen/run_spice.py
```

Required physical qualification and sourcing links are in
`hw/boards/blind-regen/README.md`.
