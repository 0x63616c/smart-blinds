# Effective ceramic capacitance

`python3 hw/sim/blind-power/check_capacitance.py --check` compares selected bank
counts with TI's effective capacitance minima. Primary Samsung typical DC-bias
curve points are retained in `capacitor-bias.json`; nominal capacitance alone is
insufficient. The shared10µF/50V part falls to about1.75µF typical at20V.

The calculation multiplies typical biased capacitance by the specified initial
tolerance, a15%X5R temperature allowance, and an explicit10%aging planning allowance.
The combined curve, aging duration and lot distributions are not guaranteed by
this calculation. Confirm capacitance and ripple/stability on assembled boards.
It deliberately excludes the small100nF bypass contribution.

The charger PMID bank was increased from3to4shared10µF capacitors. Its estimated
4.83µF exceeds TI's4µF minimum for backup-disabled operation; enabling backup would
require70µF and is prohibited by this design. Other estimated banks are VBUS2.42µF,
SYS10.38µF and BAT4.40µF. TPS62902 now uses two input capacitors for4.15µF estimated,
and two local22µF output capacitors for16.71µF estimated at3.366V.

The22µF/25V active part is suitable for the3.3V rail, but its bias loss and20%
tolerance give no useful effective-capacitance advantage at the high-voltage
nodes. The10µF/50V part is active and JLC Basic; keeping it shared avoids another
Extended-part setup charge. See the current sourcing snapshot for price and stock
metadata. No manufacturer stock or assembly quote is guaranteed by that snapshot.
