# Controller land-pattern review

Reviewed 20 October 2026. These are manufacturer-drawing transcriptions, not physical
assembly or thermal qualification. `tools/rebuild_core_lands.py` regenerates the three
corrected library footprints. Symbols, ordered parts and logical pin identities remain
unchanged. The deliberately retained imported footprint filenames preserve existing
board links; they do not imply that the original imported geometry is still used.

| Device | Primary drawing | Correction |
| --- | --- | --- |
| BQ25798 | [TI SLUSDV2C](https://www.ti.com/lit/ds/symlink/bq25798.pdf), RQM0029A example board layout, drawing 4225253/A 11/2019, PDF p149 | All lands follow the example's coordinates, widths and lengths. Four connected L-shaped corner lands replace invalid imported custom polygons whose anchors were outside copper. The outline has 0.05 mm corner radii. Lead 29 is the elongated **PMID perimeter lead**; this package has no central exposed ground pad. |
| DRV8874 | [TI SLVSF66A](https://www.ti.com/lit/ds/symlink/drv8874.pdf), PWP0016J drawing 4223595/B 12/2023, PDF pp40–41 | Example pattern rotated 90 degrees to retain the source's pin orientation: 0.45 × 1.5 mm signal lands, 0.65 mm pitch and 5.8 mm row spacing. Thermal copper is 5 × 3.4 mm with a 3.55 × 2.46 mm mask/paste opening. Twelve 0.2 mm holes on the example's 1.2 mm grid are explicitly assigned to ground pad 17. |
| ESP32-C6-WROOM-1 | [Espressif v1.4](https://www.espressif.com/sites/default/files/documentation/esp32-c6-wroom-1_wroom-1u_datasheet_en.pdf), figure 11-1, p44 | 1.5 × 0.9 mm side lands at 1.27 mm pitch, 17.5 mm row spacing, nine 0.8 mm ground lands separated by 0.45 mm. Corrected the small rounding/offset errors in the imported pattern. Twelve thermal holes now share ground pad 29 rather than remaining unnumbered/no-net. |

The module drawing does not dimension the thermal-hole drill. Its existing 0.3 mm
holes/0.5 mm annuli are retained as an explicit design choice. Repeated numbers on
thermal barrels do not create additional logical IC pins; all repeated instances must
carry the same net. The independent board-graph check rejects differing nets on a
repeated number.

No thermal-hole paste or solder-mask apertures are added. The DRV8874 example's
thermal opening still exposes holes within the pad. The paste window follows TI's example for a 0.125 mm stencil; a different assembly
stencil requires a reviewed aperture/process choice. TI recommends filled, plugged or
tented vias under paste; the assembly process and solder-wicking/thermal performance
must be resolved with the fabricator and verified on prototypes. Bottom tenting is
represented, but the design does not claim filled or capped vias have been quoted.
A solder-joint/thermal qualification remains mandatory even when KiCad DRC passes.

Fabrication rules are being selected from [JLCPCB's current capabilities](https://jlcpcb.com/capabilities/pcb-capabilities):
0.15 mm different-net SMD-pad spacing, 0.13 mm minimum black-mask bridge for 1 oz
copper, and 0.2 mm NPTH-to-copper spacing. Prefer wider routing and edge margins.
These published minima do not authorize reducing isolation clearances or waive an
assembly review. USB shell lands use the separate HRO drawing review.

The source library intentionally uses sparse fabrication/courtyard graphics. Actual
PCB identification, connector polarity and service markings are board-level work;
a preview without reference designators does not remove the assembly drawing/BOM.

A separate read-only review checked all three drawings against the generator and
compiled-instance checks. The radio now uses Espressif's linked STEP model (source
record beside the model); model dimensions are a preview reference, not owned-part fit.
