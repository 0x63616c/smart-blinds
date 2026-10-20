# Fresh part library

These assets were independently imported from public EasyEDA/LCSC component
records with easyeda2kicad 1.0.1 on 19 October 2026. They are geometry/pin-map
starting points, not manufacturer-qualified libraries. `make_wrappers.py` splits
the combined symbol file and creates local atomic Ato wrappers. Imported physical
symbols have unspecified electrical pin types, so their own ERC coverage is weak;
the native review schematic uses reviewed electrical types separately.

The DRV8874 motor block, C6 interface, BQ25798 charger, MAX17320 carrier and
TPS62902 supply now have connected circuit studies under `../../boards/`. Their
source/pin/BOM checks do not establish routing, stability or physical qualification.

| Part | Review status |
| --- | --- |
| DRV8874PWPR, C1855818 | Physical pins 1-17 checked against TI SLVSF66A pp3-6, including exposed pad 17 grounded. Land pattern and assigned thermal vias now follow the TI example; physical assembly and thermal qualification remain open. |
| 0402WGF1201TCE, C25862 | 1.2 kohm, 1%, 0402; rated in the motor manifest against Royalohm standard-series data. |
| 0402B223K500NT, C1532 | 22 nF, 50 V, X7R, 0402; manufacturer catalog checked. |
| UCM1E221MCL1GS, C340768 | 220 uF, 25 V, polarized, 6.3 mm can; Nichicon UCM data checked. Actual PWM ripple/ESR heating not qualified. |
| BQ25798RQMR, C2876593 | Pin map checked against TI SLUSDV2C; connected charger study with independent 101-pin contract; no physical assembly. Perimeter lead 29 is PMID, **not ground**; there is no central exposed pad. The retained imported filename mentions BQ25792, but its geometry now follows TI RQM0029A. |
| MAX17320G22+, C2914309 | Connected carrier study; 3S mapping checked against Rev12. The wrapper and atomic symbol correct the original PFALL typo to PFAIL. Geometry and protection commissioning remain open. |
| ESP32-C6-WROOM-1-N4, C6034714 | Connected C6 interface study; pin mapping, manufacturer land pattern and antenna reservation reviewed. Manufacturer STEP model linked by its datasheet is included; physical RF/fit tests remain open. |
| TPS62902RPJR, C2870154 | Connected logic-supply study; capacitor-bias and inductor-footprint review recorded. Stability, layout and thermal qualification remain open. |

The `blind-core.pretty` directory holds upgraded KiCad 10 imports. Flat footprint
copies beside the Ato files are required by this installed atopile release. The
3D files are visual aids; no STEP shape establishes fit or pin accuracy. Keep
unused parts labelled provisional when publishing this library. A motor-block
build does not validate the unused charger, gauge, radio or regulator assets.

The UCM1E221MCL1GS atomic symbol corrects imported vertical pin directions to face the capacitor body, with 3.81 mm pin graphics. Terminal numbers, positions, polarity and PCB connections are unchanged. `make_wrappers.py` reproduces this drawing correction. Native KiCad exports independently check the resulting netlist.

The [land-pattern review](../../../docs/electrical/land-pattern-review.md) records corrections, sources, thermal-hole choices and unresolved assembly gates. `tools/rebuild_core_lands.py` reproduces those geometries without changing logical pins.
