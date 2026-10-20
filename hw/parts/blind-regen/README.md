# Clamp parts and pin review

`make_wrappers.py` splits public EasyEDA imports into atomic atopile parts.
Primary pin maps checked for the selected ICs:

| Exact part | Physical pins |
|---|---|
| TLV6710DDCR, C2863066 | 1 OUTA, 2 GND, 3 INA, 4 INB, 5 VDD, 6 OUTB |
| TMP302ADRLR, C2877557 | 1 TRIPSET0, 2 GND, 3 OUT, 4 HYSTSET, 5 VS, 6 TRIPSET1 |
| TPS70933DBVR, C89347 | 1 IN, 2 GND, 3 EN, 4 NC, 5 OUT |

Sources: [TLV6710 §6](https://www.ti.com/lit/ds/symlink/tlv6710.pdf),
[TMP302 §5](https://www.ti.com/lit/ds/symlink/tmp302.pdf),
[TPS709 Table 5-1, original TPS709 DBV column](https://www.ti.com/lit/ds/symlink/tps709.pdf).
The TPS709A/B suffix variants have different pin assignments and are not substitutes.

The selected pulse resistor is **CRM2512-FX-10R0ELF**, C840605. The generator
corrects its lands to the primary suggested layout: 2.45 × 3.7 mm pads,
centers ±2.575 mm, 2.7 mm inner gap, 7.6 mm overall land extent. Body dimensions
are 6.3 ±0.2 × 3.1 ±0.2 × 0.6 ±0.2 mm. The generic imported 3D shape remains
approximate. [Bourns CRM drawing](https://www.bourns.com/docs/Product-Datasheets/CRM.pdf)

Other new passives are UNI-ROYAL 0402WGF3303TCE (330 kΩ, C25778),
0402WGF8202TCE (82 kΩ, C4142), and 0603WAF1005T5E (10 MΩ, C7250).
All are 1%; the 0402 parts are 62.5 mW / 50 V and the 0603 is 100 mW / 75 V.
The check conservatively allows 200 ppm/°C for the high-value feedback pair;
the general 0603 >10 Ω table states 100 ppm/°C, while the adjacent high-value
range states 200 ppm/°C. [Primary Royal Ohm catalogue](https://www.royalohm.com/assets/pdf/products/smd/1.pdf)

AON7400A, MMBT3906LT1G, AO3400A and common passives reuse previously reviewed
project-local wrappers. The imported but unused MMBT3904 candidate has no atomic
wrapper and is not in the circuit BOM. IC mechanical pad geometry and all
3D shapes still require final package/assembly review. Pin mapping checks do not
constitute that review. No component substitution is authorized by these files.
