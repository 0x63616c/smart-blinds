# Integrated controller capture

This unrouted 191-component, 595-pin study connects the C6 interface, independent
motor supervision, motor bridge, USB-C PD/eFuse input, BQ25798 charger, 3.3 V buck
switched 5 V encoder supply and independent regenerative-energy clamp. Each block's reviewed physical net graph and
exact part identities are preserved, and independent boundary checks keep:

- The motor on protected PACK, separate from charger SYS.
- The charger behind the USB input eFuse, with raw and switched USB distinct.
- Logic and encoder regulators on SYS, with reset-gated encoder permission.
- Charger CE permission, IRQ and I2C on their assigned controller pins.
- The factory PD I2C bus separate from the always-on MCU/gauge bus.
- BQ25798 exposed pad on PMID, never ground.

Normal and frozen builds pass locally; nine integration tests include injected
power-domain, factory-bus, exposed-pad, reset and thermal-inhibit faults. These checks preserve
circuit intentions, not behavior of physical silicon or a routed board.

The mechanical team is evaluating a **47 × 75 mm** controller outline inside the
unchanged 115 × 174 × 71 mm enclosure, with a large antenna reservation. This
capture has no accepted outline or placement. Carrier/motor/home connectors and
factory pads are still being integrated. The independent thermal latch gates motor
permission and pulls the shared driver-fault line low; firmware cannot distinguish
those two fault sources from that pin alone. The clamp is only a conditional pulse
design; sustained regeneration and local thermal behavior remain unqualified. NVM commissioning, a full native integrated drawing,
placement/routing/DRC, thermal/RF/EMI and prototype tests remain open. Do not
fabricate or power hardware from this study.

```sh
ato build hw/boards/blind-main -b main-test --frozen -v
python3 hw/boards/blind-main/check_main.py
python3 -m unittest discover -s hw/boards/blind-main -p 'test_*.py' -v
```

The six-contact protected-pack header is now captured. Its keyed pigtail assignment is
checked at the physical pin boundary; three negative controls reject swapped power,
a shorted charger thermistor and swapped gauge bus. Geometry and harness evidence
are in `../../../docs/electrical/battery-connector.md`. Motor/home/service ports remain open.
