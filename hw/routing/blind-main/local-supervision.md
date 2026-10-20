# Local supervision and encoder routing

This maintained stage appends 59 local branches to the protected USB routing
stage. It retains every incoming copper item, all mechanical anchors, the
outline and all thirteen reservations. Fourteen previously unwired small-part
placements change, including a 180° in-place rotation of the final thermal AND.
Its former output escape was obstructed by an existing discharge trace.

Connected paths include watchdog supply/ground/timing, watchdog-to-supervisor
reset, local supervision gates, encoder regulator bypass/enable, local buffer
supply and the ADC divider/filter island. The long MCU, motor permission/fault,
encoder signal, pack and onward ADC connections remain incomplete. The encoder
regulator's upstream SYS feed and some gate supply feeds also remain unfinished.

The input and output capacitor ground branches meet at the physical encoder
regulator GND land, with one local via into the plane. The check removes that
land from actual front copper and requires the capacitor branches to become
separate connected components. It also rejects an added copper shortcut around
the land. This is a geometric return-path check, not a measured regulator result.

| Local path | Routed recipe length | Remaining limitation |
|---|---:|---|
| Watchdog timing capacitor | 1.49 mm | Timing tolerance and parasitics unmeasured |
| Watchdog supply bypass | 1.93 mm | Supply transients unmeasured |
| Encoder input bypass | 1.77 mm | Upstream supply feed pending |
| Encoder output bypass | 6.28 mm | Longer than desired; transient review required |
| Encoder buffer bypass | 5.48 mm | Constrained by home cable volume |
| Thermal-AND bypass | 7.62 mm | Layout improvement still desirable |
| Watchdog output pull-up | 8.47 mm | Longer than near-pin guidance |
| ADC filter/divider branch | 5.97 mm | MCU ADC pad is about 27 mm away; onward layout unresolved |

The path data and exact placement overrides live in
`local-supervision-routes.json`. The generator consumes the freshly built USB
stage, preserves incoming tracks/vias through fill and save, and retains the
original electrical graph. Physical checks follow pads and copper rather than
assuming equal net names establish a connection. Seven injected faults cut
five paths, put a via through a same-net capacitor solder land, and bypass the
encoder ground junction. They run with the existing USB and power-route checks.

The full current counts and remaining DRC findings are in [README](README.md)
and `checks.json`. No noise, timing, USB, current, thermal or motor measurements
have been performed.

Primary layout guidance:
[TPS3430 §10](https://www.ti.com/lit/ds/symlink/tps3430.pdf),
[TPS3808 §8.4](https://www.ti.com/lit/ds/symlink/tps3808.pdf), and
[TPS709 §10.1](https://www.ti.com/lit/ds/symlink/tps709.pdf).
