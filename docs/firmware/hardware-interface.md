# Firmware-to-board interface proposal

Status: provisional resources for the electronics design. ESP32-C6-WROOM-1-N4 is the electrical candidate; a motor-disabled C6 bring-up application is under `firmware/esp-idf`. The actual motor/sensor pin map remains unassigned. GPIO0/1 are reserved for wake buttons and GPIO12/13 for native USB; avoid loaded motor signals on strap-sensitive GPIO8/9/15. The electronics review owns the final pin map.

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

Sampling and output tasks must be independent of blocking radio/flash writes. A watchdog must disable the bridge if the control task stalls; the host core's next-call gap detector cannot turn off a physical pin while software is frozen. Brownout, boot, update and crash output defaults must be off. Brake/coast and reversal dead time require driver truth-table, regeneration and mechanical testing before selecting behavior.

Calibration needs versioning, integrity checks and transactional storage. Avoid writing flash on every encoder edge. Preserve telemetry separately from position validity. Battery percentage should come from an appropriate state-of-charge estimator, with charge current, temperature, idle/load state and a freshness timestamp; an unloaded voltage percentage table alone is not evidence of remaining runtime.

For a 4 MB flash module, build the complete selected radio stack and check the partition budget with two update slots before committing the BOM. A small bring-up image does not prove the full application and rollback image fit. Fuel-gauge chemistry/configuration tooling and any required programmer belong in the eight-unit setup budget; gauge communications alone cannot commission a pack model.
