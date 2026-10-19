# Electrical proposal and interfaces

Status: preliminary design envelope, not fabrication-ready. Physical pins and connectors are not frozen.

## Power domains

| Net/domain | Range or target | Connected functions | Important boundary |
|---|---|---|---|
| USB_VBUS | 5 V before negotiation; target 15 V PD | PD sink, input protection, charger | No assumed 3 A entitlement before CC/PD capability is known |
| CELL0..CELL3 | Three series groups, two cells parallel in each | Cell sensing, raw pack connection | Fused/insulated pack harness; connector order and fault current need review |
| PACK_PROTECTED | About 9–12.6 V normal working envelope | Motor bridge, charger battery terminal | Independent per-cell protection; 9 V is a planning limit, not a final cutoff |
| CHARGER_SYS | Battery-related system voltage | Logic buck | Permits USB-only commissioning; motor disabled without a safe pack |
| LOGIC_3V3 | 3.3 V, supply sized for radio peaks | C6, interfaces, buttons | TPS62902 candidate, up to 2 A and 4 µA typical quiescent current; complete rail must be measured |
| ENCODER_SW | Selectable 3.3 or 5 V after motor identification | Encoder | Switched off when idle only if manual movement cannot invalidate position |
| MOTOR_A/B | Bidirectional PWM from pack | Motor winding | No raw 15 V adapter connection |

[TPS62902 primary data](https://www.ti.com/product/TPS62902). Preserve a single system ground. The gauge's low-side measurement shunt is a sense element, not a low-side disconnect; route all load/charger return current through it, with Kelvin connections.

## Control and recovery

| Interface | Resource | Required behavior |
|---|---|---|
| Motor EN/PH or IN1/IN2 | Two PWM-capable outputs | Default off at reset; explicit low-side braking mode available |
| Motor nSLEEP | Output with hardware pulldown | Bridge remains disabled while MCU unprogrammed, resetting or disconnected |
| Motor nFAULT | Interrupt input | Latched software fault; no endless automatic restart against an obstruction |
| Motor IPROPI | ADC | Detect load increase and stalled/no-motion condition with encoder |
| Encoder A/B | Two hardware pulse-counter inputs | Buffered 5 V-tolerant Schmitt interface; pull-ups fitted according to actual output type |
| Up/down buttons | Two wake-capable inputs | Immediate local wake; both pressed means stop; no network dependency |
| Gauge SMBus | Two I2C-compatible pins | Charge %, current, cell voltages, temperature, fault status; bus recovery required |
| Charger control | Same bus plus CE/interrupt as needed | Hardware 3S defaults; charging disabled until configuration/readback checks pass |
| Optional home switch | Protected GPIO plus ground/power | Reference position after lost calibration or manual movement |
| USB D+/D− | Native USB Serial/JTAG | Wired for recovery/programming; PD/legacy charging circuitry must not contend with data |
| Recovery pads | UART, EN, BOOT, GND, 3V3 | Accessible with enclosure removed; no separate USB-UART chip required |

Reserve roughly 16–19 GPIO plus native USB, depending on shared interrupt and encoder power implementation. Assign exact pins only after checking C6 strapping, wake capability, flash conflicts and module pad numbers. The timing protocol needs a monotonic clock and readiness/clock synchronization before a scheduled start; an external RTC is not assumed necessary.

## Motor envelope and energy return

DRV8874 is a candidate with current feedback and hardware current limiting. Its 6 A figure is peak capability, not permission to run continuously at 6 A on a tiny PCB. Initial calculation: 1.65 V reference and 1.21 kΩ IPROPI resistor give about 3.03 A nominal trip using the datasheet 450 µA/A gain. Tolerances and chopping overshoot must be included before setting the final limit. At 2 A, 200 mΩ nominal bridge resistance alone dissipates 0.8 W; heat rises further at temperature. [TI DRV8874 data](https://www.ti.com/lit/ds/symlink/drv8874.pdf)

The actual motor resistance, inductance, no-load current, loaded current, stall current, encoder supply and counts are unknown. A hypothetical 1.5 Ω / 500 µH load is a simulation stimulus, not a claimed motor specification. The design must stop when the encoder fails to make expected progress, with a bounded startup allowance; current feedback alone cannot prove an obstruction is safe.

Energy can return from the motor when slowing down or when the blind back-drives it. Low-side braking and controlled deceleration reduce return to the supply, but pack protection may open at exactly the wrong time. Reserve bulk capacitance, voltage sensing and a hardware energy clamp/dump path. A TVS alone must not be assumed to absorb a continuously driven blind. Keep this as a release blocker until measured motor/load energy and a component pulse/thermal rating close the calculation.

## Battery pack and charging

The BQ40Z50-R2 candidate combines cell monitoring, high-side protection-FET control, balancing and fuel gauging. It does not charge the battery. Gauge configuration must match 3S2P capacity, cell chemistry, current-shunt calibration and protection limits; an unconfigured part is not a working battery manager. [TI product and setup resources](https://www.ti.com/product/BQ40Z50-R2)

Use an inline pack fuse close to the cells, protected terminals, strain relief and an insulated serviceable pack assembly. Cell identification, condition and matching remain to be checked. Raw cell sense wires need fault-current-limiting treatment. Do not choose a holder footprint from the conflicting old drawing.

The charger needs its own hardware thermistor path; do not connect two IC analog NTC excitation circuits to one thermistor. A second pack thermistor can serve the gauge. Charge current starts at a conservative 1 A (about 0.5 A per parallel cell) and can increase only after input-power and enclosure-temperature validation. Avoid powering the motor during charging until power-path and termination behavior are tested. Charge/discharge thresholds must come from the actual Samsung cell specification and pack tests, not generic lithium defaults.

USB insertion with an empty or disconnected battery, reversed/partial sense-harness insertion, an open thermistor, gauge reset, host crash, loss of Wi-Fi/Thread and low-battery motion are required fault cases. USB-only logic bring-up must never bypass pack protection to energize the motor.
