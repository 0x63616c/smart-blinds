# Controller interface parts

Public EasyEDA atomic geometry imports, with original circuit design in `hw/boards/blind-io`. No catalog schematic has been reused. Reproduce imports with `easyeda2kicad --full --lcsc_id <code> --output <this-directory>/blind-control-io --project-relative --overwrite`, upgrade the footprint library with KiCad10, then run `make_wrappers.py` using the atopile Python environment. Flat atomic footprints use model paths relative to `hw/layouts/<board>/<target>`.

Pin functions checked against primary documents:

- **SN74LVC2G17DCKR, C50714:** TI SCES381N (January 2015), page3: 1=1A, 2=GND, 3=2A, 4=2Y, 5=VCC, 6=1Y. Wrapper aliases A1/A2/Y1/Y2 preserve these numbers. DCK is SC70-6; the imported SOT-363-named footprint still needs package-drawing dimensions checked before layout.
- **TPD2E2U06DRLR, C1972959:** TI SLLSEG9C (December 2019), page3: 1/2=NC, 3=IO1, 4=GND, 5=IO2. TI permits the NC pins to be grounded. This is a two-channel data ESD part, not a PD-VBUS clamp.
- **TS-1088-AR02016, C720477:** imported two-terminal tactile switch; exact mechanical force/travel, footprint and enclosure actuator geometry are still provisional.
- Resistors and capacitors are fixed supplier/MPN imports. Ratings, tolerances, DC bias and the actual populated circuit must be reviewed; build success alone is not a rating check.

The C6 module remains in `blind-core`; its nine imported thermal pad segments connect to the same ground. The manufacturer presents these as one EPAD29, so pad-number subdivision is a geometry representation rather than nine separate chip signals. Detailed paste/mask/land review remains open.

No source contained here is fabrication approval. The controller capture has unresolved watchdog/reset/power-down behavior described in its README.

- **TS-1081S-AC01326, C720493:** side-actuated front-button candidate. XUNPU family drawing supplied by [JLC](https://jlcpcb.com/partdetail/XUNPU-TS_1081SAC01326/C720493) shows 3.5 × 3.0 × 1.3 mm body, 4.6 mm terminal span, 3.75 mm including actuator and 0.8 ±0.05 mm actuator centre above PCB. The AC variant has two 0.6 mm locating posts; imported unnumbered plated holes are corrected to NPTH in the wrapper generator. Contact pairing 1/2 and 3/4 comes from the catalog symbol, not a numbered manufacturer circuit, and must be confirmed on samples. Do not promote it to verified wiring. Drawing travel entries differ (0.20 ±0.05 and ±0.10 mm), so use 0.30 mm as the maximum operating-travel reservation pending clarification.
- The old top-actuated switch, NRND CL21A226MAQNNNE and EN capacitor imports remain unused reference geometry. The active MCU bulk capacitor comes from `blind-power`.
