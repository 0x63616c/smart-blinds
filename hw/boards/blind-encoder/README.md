# Switched encoder supply

Six parts supply a provisional **5 V / 30 mA** encoder rail from charger SYS
(8.8–13.2 V). The TPS70950DBVR C96028 is the TI part, not the similarly named
third-party TPS70950DBVR-TP. The extra SN74AUP1G97 reuses an existing SKU and
implements `RESET_N && !ENCODER_ALLOW_N`; reset and a high request both turn it
off. A 1 kΩ EN pull-down keeps the regulator disabled with unpowered logic.
EN is never tied to SYS. Pin4 of the DBV regulator remains NC.

[TI TPS709 SBVS186H](https://www.ti.com/lit/ds/symlink/tps709.pdf) specifies at
least 1.5 µF effective output capacitance for outputs at or above 1.5 V, with
0–0.2 Ω ESR and at most 47 µF. The selected Samsung 4.7 µF/50 V output capacitor
has a **3.02 µF estimate at 5.25 V** after typical bias, tolerance, temperature
and aging allowances. The local 1 µF input capacitor estimates 0.178 µF at
13.2 V, within TI's decoupling recommendation. These typical-curve estimates
are not guaranteed production minima or a stability test.

Adding the stated accuracy/line/load contributions gives a planning range of
4.89–5.11 V. At 30 mA and maximum normal SYS, dissipation is approximately
0.249 W. The datasheet reference board's 212.1°C/W predicts a 53°C junction
rise; our enclosure and copper are not qualified. Actual encoder current must
be checked before accepting this arrangement. The 150 mA chip rating is not
our enclosure's current rating, and its current limit is not a 30 mA limit.

The gate's 3 V, 4 mA VOH guarantee exceeds TPS709's 0.9 V enable threshold;
the calculated pull-down load is below 4 mA. Gate input and output off-state
behavior are taken from [TI SCES505J](https://www.ti.com/lit/ds/symlink/sn74aup1g97.pdf).
TPS709's EN pull-up and shutdown-current entries are typical only, so power
ramping, off-state leakage and actual rail collapse remain bench gates. Its
output has no active discharge. Firmware must wait for encoder power and
stable counts before using those counts; the typical startup figure is not a
system-ready guarantee. Motor encoder voltage and wiring remain provisional.

Normal and frozen atopile builds pass locally. A separate 19-pin contract and
four injected wiring faults check identity/connectivity, not semiconductor
behavior. No motor or cell has been powered and this is not fabrication-ready.

```sh
ato build hw/boards/blind-encoder -b encoder-test --frozen -v
python3 hw/sim/blind-encoder/checks.py --check
```
