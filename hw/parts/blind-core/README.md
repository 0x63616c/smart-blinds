# Fresh part library

These assets were independently imported from public EasyEDA/LCSC component
records with easyeda2kicad 1.0.1 on 19 October 2026. They are geometry/pin-map
starting points, not manufacturer-qualified libraries. `make_wrappers.py` splits
the combined symbol file and creates local atomic Ato wrappers. Imported physical
symbols have unspecified electrical pin types, so their own ERC coverage is weak;
the native review schematic uses reviewed electrical types separately.

Only the DRV8874 motor block has been wired and built so far. Its source/BOM-linked
rating records and checker live in `../../boards/blind-controller/`.

| Part | Review status |
| --- | --- |
| DRV8874PWPR, C1855818 | Physical pins 1-17 checked against TI SLVSF66A pp3-6, including exposed pad 17 grounded. Layout land dimensions and thermal vias still need verification. |
| 0402WGF1201TCE, C25862 | 1.2 kohm, 1%, 0402; rated in the motor manifest against Royalohm standard-series data. |
| 0402B223K500NT, C1532 | 22 nF, 50 V, X7R, 0402; manufacturer catalog checked. |
| UCM1E221MCL1GS, C340768 | 220 uF, 25 V, polarized, 6.3 mm can; Nichicon UCM data checked. Actual PWM ripple/ESR heating not qualified. |
| BQ25798RQMR, C2876593 | Pin map checked against TI SLUSDV2C; no assembled circuit yet. Exposed pad 29 is PMID, **not ground**. Imported footprint name mentions BQ25792; dimensional qualification remains open. |
| MAX17320G22+, C2914309 | Unreviewed circuit/geometry. Import signal `PFALL` is a typo for PFAIL; correct before use. |
| ESP32-C6-WROOM-1-N4, C6034714 | Unreviewed import; no 3D model supplied. Module clearance/antenna guidance needs independent review. |
| TPS62902RPJR, C2870154 | Unreviewed circuit/geometry. |

The `blind-core.pretty` directory holds upgraded KiCad 10 imports. Flat footprint
copies beside the Ato files are required by this installed atopile release. The
3D files are visual aids; no STEP shape establishes fit or pin accuracy. Keep
unused parts labelled provisional when publishing this library. A motor-block
build does not validate the unused charger, gauge, radio or regulator assets.
