# Controller interface capture

**UNVERIFIED, incomplete block.** This fresh ESP32-C6-WROOM-1 circuit builds in atopile 0.15.9, but has no placed/routed PCB, reviewed native schematic or manufacturing approval. The public motor block remains a separate reviewed snapshot. This capture must not be connected directly to a motor or charger as a complete design.

It contains the C6 module, 22 µF/100 nF supply bypass, externally supervised reset and boot straps, two side-actuated tactile switches for front buttons, native USB data series resistors/ESD, I2C pulls, dual 5 V-tolerant Schmitt encoder receivers, optional dry-contact home input and a divided/filtered current readout. It accepts external 3.3 V and switched 5 V encoder power. GPIO mappings follow the firmware interface document; the source is not a board driver.

GPIO20/22/23 requests are **active low**, with external pull-ups agreeing with the C6's reset weak pull-ups. The charger and encoder rail require their own inversion/default-off circuitry. MOTOR_REQUEST_N must pass through the separately timed motor gate, not directly to DRV8874 nSLEEP. The former EN 1 µF capacitor and duplicate reset/request pull-ups have been removed; the external TPS3808/TPS3430 block now owns reset delay and those pulls. This standalone capture requires that block. Connector assignments, power domains and return paths remain integration boundaries.

The 100k/100k ADC branch loads the motor's 1.2k current resistor. Its integrated worst-case static chopping estimate becomes about 3.418 A; the standalone motor block's 3.398 A result cannot be reused unchanged. The nominal readout filter is approximately 5 ms and does not slow the driver's local current-limit comparator. GPIO current-injection/back-power behavior during rail collapse and ADC settling remain unresolved. No protection claim is made from the divider alone.

Encoder pull-ups use switched VENC, with ground pulls defining disconnected/off input state. The SN74LVC2G17 tolerates up to 5.5 V at its inputs and specifies partial-power-down Ioff; this does not establish the purchased motor's pinout, encoder supply, output type or pulse rate. Hardware/PCNT filtering must be tuned against measured edges. The optional home contact is a dry-contact interface, not a generic 5 V sensor port; external cable ESD remains to be integrated.

Component pin maps and geometry are tracked in `hw/parts/blind-control-io`. Capacitance under DC bias, supply transients, RF antenna placement and populated-board ESD performance still need review and prototype measurements. Stock/prices in the controller sourcing snapshot are dated catalog observations, not a reservation or quote.

Build from the repository root:

```sh
ato build hw/boards/blind-io -b controller-test
```

Sources: [Espressif module datasheet](https://www.espressif.com/sites/default/files/documentation/esp32-c6-wroom-1_wroom-1u_datasheet_en.pdf), [C6 schematic guidance](https://docs.espressif.com/projects/esp-hardware-design-guidelines/en/latest/esp32c6/schematic-checklist.html), [TI dual Schmitt receiver](https://www.ti.com/lit/ds/symlink/sn74lvc2g17.pdf), [TI dual ESD protector](https://www.ti.com/lit/ds/symlink/tpd2e2u06.pdf).

The active Samsung CL21A226MAYNNNE (C602037) replaces the NRND CL21A226MAQNNNE. Its nominal 22 µF is not its effective capacitance: Samsung's typical bias curve gives approximately 13.86 µF at 3.3 V, before tolerance, temperature and aging. The regulator needs its own local output bank. The candidate front switch is XUNPU TS-1081S-AC01326 (C720493), one additional Extended feeder type for both buttons. Its manufacturer drawing establishes geometry but not the numbered contact circuit; the imported 1/2 and 3/4 grouping remains a sample verification gate.
