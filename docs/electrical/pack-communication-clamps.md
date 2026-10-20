# Battery communication-clamp topology

The maintained carrier captures and primary route use the corrected topology
below. The change affects exactly six diode pins; the selected purchased parts
and their physical footprints are retained.

The reviewed manufacturer example places each communication clamp on the
connector side of the 150 Ω series resistor, returning to PACK−. Our preceding
capture used the gauge side and RAW_GND. These are different nets across the
current shunt. The correction changes exactly six diode pins, with the same
three purchased parts and footprints:

| Pin | Previous connection | Corrected connection |
|---|---|---|
| z_sda.K | gauge SDA_DQ | external SDA |
| z_scl.K | gauge SCL_DOD | external SCL |
| z_alert.K | gauge ALRT | external ALERT |
| all three anodes | RAW_GND | PACK− |

Evidence: [ADI UG7177 Rev0, March 2020](https://www.analog.com/media/en/technical-documentation/user-guides/max17320-battery-pack-implementation-guide.pdf),
Figure 3 on p5, visually inspected in the primary PDF in Chrome on 2026-10-20,
and ESD routing discussion pp5–6. The inverted-triangle symbol connects the
Zener anodes to CSN/PACK−, while the three-line ground symbol identifies GND,
NTCs and the battery side of the shunt. The diagram puts each clamp between
its external port and the series resistor.
The ground/Kelvin guidance on p4 requires distinct sense routes. Combining
Zener and NTC returns in the previous isolated quiet branch was our layout
interpretation, not a manufacturer requirement.

The [MAX17320 Rev12 datasheet](https://www.analog.com/media/en/technical-documentation/data-sheets/max17320.pdf)
p175 omits the external communication protection network; it does not
contradict the application guide. Its p18 SCL/SDA/ALRT absolute limits are
−0.3 to +20 V relative to GND. The normal 4 A, 10 mΩ shunt differential is
about 40 mV before trace drops. This does not establish transient immunity.

Retain JSCJ BZT52C4V7 provisionally. The [manufacturer-authored Rev2.1 sheet](https://datasheet.lcsc.com/datasheet/pdf/748504625e418aa84c5305d597e87d6d.pdf)
specifies 4.4–5.0 V at 5 mA, 80 Ω maximum dynamic impedance at that point,
and 0.9 V forward drop at 10 mA. Leakage is bounded only at 2 V; capacitance
is a typical plot. There is no IEC ESD or clamping-voltage guarantee for the
assembled bus. Neither the Zener's 500 mW rating nor the gauge's absolute
limit proves an ESD result. Bus leakage/rise time, negative-pulse behavior,
resistor pulse survival, ground bounce and hot-plug tests remain open.
The reference's nominal 5.6 V device is not silently substituted for 4.7 V.

The isolated layout candidate keeps gauge bypass/NTC grounds on the separate RAW_GND
quiet branch and keep both Kelvin routes free of branches. Zener anodes
instead enter the protected ground trunk near the external harness, avoiding
the old 96.4 mm quiet trace and its shared 19 mm rejoin. The preceding quiet-return links were removed; no second ground tie bypasses
the intended separation.
