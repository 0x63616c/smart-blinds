# MAX17320 commissioning path

Status: provisional MAX17320G22+ for the separate 3S2P holder/protection carrier. A Windows-free host path is credible, but no complete cell-specific protection profile or physical commissioning has been validated. Tooling below cannot program the gauge.

## Evidence and remaining gap

The ROM EZ model is selected with `enX=0` and `enOCV=0`; published defaults avoid an inherently opaque custom OCV table. Internal addresses use 7-bit I2C `0x36` for normal registers and `0x0B` for shadow registers, with little-endian words. Capacity scales with sense resistance; 3S2P of nominal 5 Ah cells is 10 Ah, giving `0x4e20` at 10 mΩ. `nRSense=0x03e8` records that resistor for host conversions. These are partial calculations, not protection settings. [ADI datasheet Rev 12, pp78, 98, 125, 132–135, 161–162](https://www.analog.com/media/en/technical-documentation/data-sheets/max17320.pdf)

ADI's pack workflow uses a GUI-generated configuration file and then a documented host programming sequence. EZ avoids cell characterization as a prerequisite, but the published workflow does not prove our Samsung 50E accuracy or supply an independently reviewed, complete pack profile. It calls for pack production measurements and calibration checks. Our next step is to derive and review the whole profile against the selected circuit and cell limits, then verify it on a fixture before the eight-unit build. [ADI Battery Pack Implementation Guide, pp7–11](https://www.analog.com/media/en/technical-documentation/user-guides/max17320-battery-pack-implementation-guide.pdf)

Normal operation reads identity, charge/capacity, voltage/current/temperature and protection status; configured values restore automatically at power-up. `DevName` must be recorded because register behavior varies with silicon revision. A successful I2C read alone does not establish correct provisioning or healthy protection. [ADI Software Implementation Guide, pp3–5](https://www.analog.com/media/en/technical-documentation/user-guides/max17320-software-implementation-guide.pdf)

## Tools provided

`firmware/tools/max17320.py` has a fixed register read whitelist, an offline partial-profile calculator and readback comparison. It has **no unlock, reset, configuration write, NVM copy, FET-control or permanent-lock implementation**. The Linux backend uses combined I2C pointer/read transactions; hardware access has not been tested. [Linux i2c-dev interface](https://www.kernel.org/doc/html/latest/i2c/dev-interface.html)

```sh
python3 -m unittest discover -s firmware/tools -p 'test_*.py' -v
# On a Linux test fixture with the intended I2C bus and reviewed electrical connection:
python3 firmware/tools/max17320.py read --bus 1 --output work/gauge-readback.json
# Offline on macOS or Linux; output remains explicitly INCOMPLETE_DO_NOT_PROGRAM:
python3 firmware/tools/max17320.py derive work/gauge-readback.json \
  --series 3 --parallel 2 --cell-mah 5000 --rsense-milliohm 10 > work/gauge-partial.json
python3 firmware/tools/max17320.py compare work/gauge-partial.json work/gauge-readback.json
```

The bus number is an example, not an identified device. Select the actual fixture bus. Read errors abort capture; missing values never become zero. A capture is shadow RAM plus live readings, not independently recalled NVM. Comparison covers only listed partial registers. macOS runs the offline tools now; a physical USB-to-I2C backend or a C6 service bridge remains to be implemented and tested. Do not connect the Mac directly to pack signals.

## Before any NVM implementation

Require the exact silicon revision, complete register coverage with reserved-bit review, selected thermistors, charge termination, empty voltage, all protection thresholds/delays, balancing, restore/checksum rules and a recorded remaining-write count. Configuration has seven user writes; block programming can take up to 7.36 s. A future tool must poll status, bound timeouts, preserve evidence and never blindly retry a failed burn. [ADI datasheet Rev 12, pp23, 128–130](https://www.analog.com/media/en/technical-documentation/data-sheets/max17320.pdf)

Our engineering acceptance must include per-cell voltage comparison, zero/known current tests, temperature checks, charger coordination, connector removal, depleted cells, controlled protection tests and measured state-of-charge error over representative cycles. Do not commission a live installed blind as the first test fixture.

## Carrier and runtime contract

The proposed carrier retains the protector and FETs when disconnected. The controller receives protected power and I2C, plus an independent charger NTC connection. Missing gauge, absent pack, wrong identity/profile, NACK, stale sensor data or a stuck bus must inhibit charging and movement until a fresh healthy pack validation. Hardware charge/motor enables must default off during reset and bus recovery. Reconnection never resumes an interrupted move.

Use bounded I2C transactions in a separate worker, not the motor loop. Carry read time and a conservative ADC-age bound: reading again is not a new conversion. Keep fast motor current feedback independent of the fuel gauge. Runtime acceptance must account for hot-plug/back-power paths, ground sequencing and bus recovery before declaring the interface complete.
