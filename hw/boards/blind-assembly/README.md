# Integrated control and motor capture

The ESP32-C6 interface, independent motor supervision and DRV8874 bridge now compose
into one 61-component, 207-pin circuit. This is still an incomplete design study:
charger/regulator/USB-PD/protected carrier, regenerative clamp, connectors, final
placement, routing and physical tests remain outside this capture.

GPIO20 requests movement through the watchdog and reset gate. It never connects
directly to nSLEEP. GPIO16 supplies the control-task heartbeat; TPS3808 reset reaches
both C6 EN and the output gate. The previous EN capacitor and duplicate IO reset/
request pull-ups are removed. The supervisor supplies those pulls and reset timing.
The combined 1 kΩ and 10 kΩ nSLEEP pulls draw at most 3.815 mA including the driver
input current allowance, within the AUP gate's reviewed 4 mA output test condition.

`check_assembly.py` checks that composition preserves every pin and selected part
of the three standalone blocks. It also independently asserts exact physical-pin
groups across the request, heartbeat, reset, nSLEEP, PWM, fault and current-readout
boundaries. Four regression tests reject broken reset, bypassed motor gating and
missing replacement-switch pads. These are connection checks, not a cutoff test.

The ADC branch's loading, rail-collapse backfeed, external-interface protection,
actual motor stall current and regeneration remain open electrical gates. The
candidate front switches have sourced mechanical dimensions; catalog terminal
pairing still needs sample verification. No GPIO motor driver is enabled in firmware.

```sh
ato build hw/boards/blind-assembly -b controller-test --frozen -v
python3 hw/boards/blind-assembly/check_assembly.py
python3 -m unittest discover -s hw/boards/blind-assembly -p 'test_*.py' -v
```
