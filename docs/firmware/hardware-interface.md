# Firmware-to-board interface proposal

Status: provisional resources for the electronics design. ESP32-C6-WROOM-1-N4 is the electrical candidate; a motor-disabled C6 bring-up application is under `firmware/esp-idf`. The following allocation is proposed for schematic review; the application does not configure these pins yet. Leave GPIO4/5, GPIO8/9 and GPIO15 free of loaded control signals because they are strap-sensitive. GPIO14 is not exposed on this module. The electronics review owns the final pin map. [Module pin and strap tables](https://documentation.espressif.com/esp32-c6-wroom-1_wroom-1u_datasheet_en.pdf)

| Proposed GPIO | Board signal | Default and constraint |
|---|---|---|
| 0 / 1 | Up / Down buttons | Wake-capable, active low; excludes an external 32 kHz crystal on these pins |
| 2 | IPROPI ADC branch | ADC1_CH2; isolated RC filtering, independent of current-limit resistor |
| 3 | Optional physical reference | Input; sensor voltage and debounce defined by board |
| 6 / 7 | Encoder A / B | LP-capable inputs; forfeits these external JTAG signals; no PCNT retention claim |
| 10 / 11 | I2C SDA / SCL | External pull-ups; bounded worker transactions |
| 12 / 13 | Native USB D− / D+ | Preserve programming/recovery access |
| 18 / 19 | DRV8874 IN1 / IN2 | External pull-downs; PWM-mode truth table below |
| 20 / 21 | Driver nSLEEP / nFAULT | Sleep pulled down; fault input pulled up as reviewed |
| 22 | Charge permission | Active high to NFET pulling CE low; charger-side pull-up disables on reset |
| 23 | Encoder rail enable | Active high, default off; gating subject to reference/holding policy |
| 17 | Optional charger INT | GPIO input; shared gauge alert requires a changed carrier connector |
| 16 | External watchdog WDI | Reserved for control-task heartbeat; replaces optional service UART TX |

With DRV8874 PMODE high, IN1/IN2 `00` coasts, `01` reverses, `10` forwards and `11` uses low-side braking. Current proposal: fixed off-time regulation with latched overcurrent protection, 1.2 kΩ IPROPI resistor and nominal 1.65 V VREF, approximately 3.06 A nominal regulation. These are electrical design values, not validated safe motor current or braking performance. Do not enable the motor from the map alone.

Thread sleepy-device operation must retain the network stack using supported modem/automatic light sleep. Deep sleep is a reset/rejoin boundary. Encoder counting and manual movement while its rail is gated remain separate physical-reference problems; reserving LP pins does not solve them. Resynchronize the awake clock and prove an error bound before coordinated motion.

| Function | Resource to reserve | Reason |
|---|---|---|
| Motor encoder | Two GPIO suitable for hardware quadrature counting; normalized direction | Position and speed feedback; voltage/pinout of purchased encoder is unverified |
| H-bridge | Two PWM/control signals, hardware default-off enable/sleep, fault input | Bidirectional speed, standby power and independent fault reporting |
| Motor current | ADC-capable current feedback input or suitable digital measurement | Detect load/jam and verify current limits; firmware is not the short-circuit protector |
| Buttons | Two wake-capable GPIO, debounce provisions, unambiguous simultaneous press | Local control/STOP without a network round trip |
| Battery/charger | I2C, relevant interrupt/alert and temperature data | Charge state, pack/current/cell/temperature diagnostics, low-battery movement inhibit |
| Encoder rail | Switchable supply if required, no back-power through I/O | Motor encoder idle draw can dominate a nominally sleeping MCU |
| Home/reference | Spare connector/input, with defined power and input limits | Recover a physical reference after reboot or position loss |
| Programming | Native USB or accessible UART, boot/reset/service pads | Initial flashing, recovery even when radio/network or OTA fails |
| Radio | Antenna keepout clear of cells, motor, ground and wall hardware | Test RF in assembled enclosure, not on an empty PCB |

The C6 PCNT peripheral can decode quadrature with edge and level inputs and glitch filtering. Validate counts/revolution at the chosen decode multiplier and prove no missed edges at maximum speed before assigning travel units. [Espressif PCNT documentation](https://docs.espressif.com/projects/esp-idf/en/latest/esp32c6/api-reference/peripherals/pcnt.html)

The eventual board port must turn `Output.velocity_mm_s` into a **calibrated encoder velocity** using the local slope of the calibration map, close the velocity loop with measured motor response, and apply current/PWM limits. Counts per second changes with position when the fabric-to-encoder map is nonlinear. Do not simply turn physical velocity into fixed PWM duty.

`Measurement.power_ready` must aggregate the real charger/protection/temperature state and any per-cell fault indications. Total pack voltage alone cannot establish that all three series groups are healthy. The board-level current limiter and pack protector remain authoritative; firmware must inhibit movement on their faults. Whether motion is permitted while charging remains an electrical power-path decision.

The proposed holder/protection carrier retains the MAX17320 and FETs with the cells. Its protected supply/I2C connector and independent charger NTC pair need hot-plug, back-power and ground-sequencing review. Missing pack/gauge, wrong identity or profile, stale readings and a stuck I2C bus must inhibit charging and movement; reconnection cannot replay a move. Use bounded sensor transactions outside the motor task and require fresh healthy validation before restoring readiness. See the [commissioning assessment and read-only tooling](max17320-commissioning.md).

See the [frozen-controller cutoff requirement](watchdog-output-boundary.md): proposed external watchdog worst-case cutoff at most 100 ms, with GPIO16 reserved for its control-task heartbeat.

Sampling and output tasks must be independent of blocking radio/flash writes. A watchdog must disable the bridge if the control task stalls; the host core's next-call gap detector cannot turn off a physical pin while software is frozen. Brownout, boot, update and crash output defaults must be off. Brake/coast and reversal dead time require driver truth-table, regeneration and mechanical testing before selecting behavior.

Calibration needs versioning, integrity checks and transactional storage. Avoid writing flash on every encoder edge. Preserve telemetry separately from position validity. Battery percentage should come from an appropriate state-of-charge estimator, with charge current, temperature, idle/load state and a freshness timestamp; an unloaded voltage percentage table alone is not evidence of remaining runtime.

For a 4 MB flash module, build the complete selected radio stack and check the partition budget with two update slots before committing the BOM. A small bring-up image does not prove the full application and rollback image fit. Fuel-gauge chemistry/configuration tooling and any required programmer belong in the eight-unit setup budget; gauge communications alone cannot commission a pack model.
