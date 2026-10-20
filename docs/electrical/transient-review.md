# Input transients and motor energy

20 October 2026. **Open design findings; the captured board is not ready to order.**
These findings apply to the monitored-PD circuit and partial route published in
`a2baedb`, with the native test correction in `b6e2558`. The
[calculation record](transient-review.json) binds the exact reviewed files.
Passing circuit, routing and firmware checks does not resolve these findings.

## USB input protection

The existing ESDA25P35 suppressor specifies a maximum 41 V clamp at its specified
35 A, 8/20 µs surge. STUSB4500 VDD and TPS25947 IN both have 28 V absolute
limits. The eFuse cannot disconnect its own input pin or the upstream PD
controller from that event. The current parts therefore do not establish
coordinated surge protection. This does not predict failure with an ordinary
compliant charger. Sources: [ST suppressor, electrical table](https://www.st.com/resource/en/datasheet/esda25p35-1u1m.pdf),
[STUSB4500, absolute limits](https://www.st.com/resource/en/datasheet/stusb4500.pdf),
[TPS25947, §6.1](https://www.ti.com/lit/ds/symlink/tps25947.pdf).

The development direction is an upstream, higher-voltage cutoff feeding a
protected rail for the PD controller and the existing contract-gated eFuse.
A lower-clamping suppressor on that protected rail can then cover the
sensitive inputs. The existing raw suppressor remains at the connector.
The additional cutoff's area, cost, dissipation, startup and fault response
must be included in the revised capture and layout.

A lower-voltage TVS alone is insufficient: continuous unexpected 20/21 V
input must be disconnected, rather than dissipated indefinitely in that
shunt. The current 21 V fault envelope remains a design requirement.
The revised parts are not yet present in the published board.

## Dump load and thermal trip

The eight 10 Ω resistors form four series pairs in parallel: nominally 5 Ω.
At 12.6 V and the low end of their 1% tolerance, a stuck dump switch draws
approximately **2.55 A and 32.07 W**, or 4.01 W per resistor. A provisional
4 A pack threshold cannot be credited with clearing this fault.

The Bourns 2 W rating relies on its specified 300 mm² solder-pad/trace area
per resistor. The compact shared layout does not establish eight independent
thermal paths or a 16 W installed rating. The thermostat measures its own
temperature; its placement alone cannot establish the hottest resistor's
temperature or shutdown delay. Sources: [Bourns CRM, rating and land-area notes](https://www.bourns.com/docs/Product-Datasheets/CRM.pdf),
[TMP302, thermal response and layout](https://www.ti.com/lit/ds/symlink/tmp302.pdf).

Thermal trip opens the dump and disables the motor bridge. DRV8874 sleep is a
high-impedance state, so a motor that continues rotating can still return
energy through its bridge diodes. It is not an independent brake.
For the explicitly assumed 2 A return and 176 µF bulk capacitance,
18 V to the charger BAT pin's 20 V absolute limit takes only 176 µs.
This is sensitivity arithmetic, not a measured motor event.
[DRV8874 control modes](https://www.ti.com/lit/ds/symlink/drv8874.pdf),
[BQ25798 absolute limits](https://www.ti.com/lit/ds/symlink/bq25798.pdf).

The two-prototype design needs accessible load/probe connections and an
external, suitably derated dump-load population option for characterization.
Neither that fixture nor a larger resistor resolves sustained back-drive
after thermal isolation.

## Holding and release condition

The installation must retain a working original blind holding mechanism,
independent of motor current and electronic braking. Its behavior under the
added chain preload is unverified. See the
[mechanical holding condition](../mechanical/existing-blind-holding.md).
No self-locking property is assumed for the purchased gearbox.

Before unattended wall operation, establish the actual returned energy,
input-pin overshoot, hottest component/plastic temperatures, and behavior
after thermal trip or pack isolation. If the original blind cannot hold
independently, a qualified holding/braking redesign is required. These are
physical prototype gates; the owner being away does not prevent the remaining
CAD, circuit and software design.
