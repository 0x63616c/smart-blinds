# Controller interface parts

Public EasyEDA atomic geometry imports, with original circuit design in `hw/boards/blind-io`. No catalog schematic has been reused. Reproduce imports with `easyeda2kicad --full --lcsc_id <code> --output <this-directory>/blind-control-io --project-relative --overwrite`, upgrade the footprint library with KiCad10, then run `make_wrappers.py` using the atopile Python environment. Flat atomic footprints use model paths relative to `hw/layouts/<board>/<target>`.

Pin functions checked against primary documents:

- **SN74LVC2G17DCKR, C50714:** TI SCES381N (January 2015), page3: 1=1A, 2=GND, 3=2A, 4=2Y, 5=VCC, 6=1Y. Wrapper aliases A1/A2/Y1/Y2 preserve these numbers. DCK is SC70-6; the imported SOT-363-named footprint still needs package-drawing dimensions checked before layout.
- **TPD2E2U06DRLR, C1972959:** TI SLLSEG9C (December 2019), page3: 1/2=NC, 3=IO1, 4=GND, 5=IO2. TI permits the NC pins to be grounded. This is a two-channel data ESD part, not a PD-VBUS clamp.
- **TS-1088-AR02016, C720477:** imported two-terminal tactile switch; exact mechanical force/travel, footprint and enclosure actuator geometry are still provisional.
- Resistors and capacitors are fixed supplier/MPN imports. Ratings, tolerances, DC bias and the actual populated circuit must be reviewed; build success alone is not a rating check.

The C6 module remains in `blind-core`; its nine imported thermal pad segments connect to the same ground. The manufacturer presents these as one EPAD29, so pad-number subdivision is a geometry representation rather than nine separate chip signals. Detailed paste/mask/land review remains open.

No source contained here is fabrication approval. The controller capture has unresolved watchdog/reset/power-down behavior described in its README.
