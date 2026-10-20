# USB-C input circuit study

The fresh 32-part circuit uses an STUSB4500 autonomous PD sink and a
TPS259470L latched eFuse. A successful normal/frozen atopile build and a separate
111-pin contract check establish the captured connections, not USB compliance
or tested charging. The standalone block is unrouted. The earlier partial main
route requires explicit migration to this new graph; there is no fabrication release.

The intended profile is 5 V/1.5 A, 9 V/2.5 A and 15 V/2.5 A, with
`POWER_ONLY_ABOVE_5V=1` and `REQ_SRC_CURRENT=0`. Only a matching 9 V or 15 V
contract enables the downstream power path. Factory defaults are unsuitable.
The PD controller now uses direct always-on 3.3 V on VSYS, with an existing
1 uF/50 V capacitor SKU. Its 0x28 bus shares the single MCU-owned SDA/SCL
pair with the charger and pack; the old two 100k pulldowns are removed.
ALERT shares charger INT on GPIO17. Main supplies one explicit 10k pull-up;
the prior capture had omitted this delegated resistor. No active chip or new
component SKU is added. RESET remains active high with a 10k pulldown.
CC1DB/CC2DB stay connected to their CC pins and raw-USB VDD remains available
for dead-pack startup. There are no duplicate external CC pulldowns.

Physical factory pads are still pending. They must use this shared bus with the
MCU held reset, CE physically inhibited and downstream USB input isolated while
programming unknown NVM. No fixture pull-up may back-power a dead host rail.
See [the monitored-PD revision](../../../docs/electrical/monitored-pd-revision.md) for the exact interface,
conditional electrical margins and proposed fixture pad map.

A PNP inverts the detach-aware VBUS_EN_SNK signal into the eFuse enable.
POWER_OK flags alone cannot do that job. The divider estimates are 6.73–7.78 V
for rising UVLO and 16.93–18.77 V for rising OVLO, including resistor drift and
an explicitly provisional PNP drop allowance. TI's specified 1.65 kohm limit
point gives an estimated 1.769–2.239 A range after resistor allowance. The
charger's initial input setpoint is 1.5 A; its error allocation remains tied to
the firmware/register review. A charger must advertise 9 V or 15 V at 2.5 A
or more. Many 20 W phone chargers will not qualify.

The raw input uses one CL31A475KBHNNNE 4.7 uF/50 V capacitor. Samsung's typical
21 V bias data, multiplied by tolerance, temperature and aging allowances,
estimates 1.745 uF. Internal 1.2/2.7 V regulator caps estimate 0.678/0.602 uF,
above ST's 0.5 uF minimum. The conservative nominal input-capacitance planning
raw-local subtotal is 9.741 uF; it excludes the new host-rail VSYS capacitor
and does not bound possible internal reverse feed into that rail. These estimates are not guaranteed production bounds or an
inrush test. The 1 uF VDD reservoir follows ST's nominal reference value but
loses substantial capacity under bias; startup/hold-up remains unqualified.

The selected ST reference TVS parts do **not** prove a safe surge clamp. The
VBUS TVS specifies up to 31 V at the cited ESD test point and 41 V at its
35 A surge point, above connected IC DC absolute ratings. Actual layout,
source inductance, transient energy and device response need qualification.
Separate 3 kohm discharge chains use three 0603 resistors each; pulse power
is bounded in the static calculation, but final timers and the charger's
reverse-current paths still need evaluation. The charger supplies the local
output capacitor bank. No negative-output-transient immunity is claimed.

Sources and scoped numbers are in `usb-ratings.json`; independent physical
pin assignments are in `usb-connectivity.json`. `hw/sim/blind-usb/checks.py`
rejects five deliberately introduced faults, including reversed VDD diode,
CC short and a grounded AUXOFF output. The native KiCad drawing has eight
documented external-supply/bus/alert ERC findings and no exclusions or artificial drivers.

```sh
ato build hw/boards/blind-usb -b usb-test --frozen -v
python3 hw/sim/blind-usb/checks.py --check
python3 tools/generate_schematics.py hw/schematics/blind-usb/usb-test.layout.json --check
```
