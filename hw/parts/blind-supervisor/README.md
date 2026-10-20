# Supervision parts

Public EasyEDA/LCSC geometry imported for an original circuit. `make_wrappers.py` regenerates the atomic atopile wrappers. Geometry, pin polarity and final assembly orientation still require populated-board review; no imported symbol proves the circuit works.

| Selected part | LCSC | Pin-number review |
|---|---|---|
| TPS3430WDRCR | C2870545 | TI SBVS366A, page3: both supplies tied, EP grounded; CRST and NC deliberately isolated |
| TPS3808G33DBVR | C43698 | TI SBVS050N, page4, SOT-23 mapping; 3.07 V threshold, not the G30's 2.79 V |
| SN74AUP1G97DCKR | C2682139 | TI SCES505J, package diagram and truth table; B=pin1, GND2, A3, Y4, VCC5, C6 |
| CL05C121JB5NNNC | C307442 | Samsung 120 pF, C0G, ±5%, 50 V, 0402; selected timing part |

The unused SN74LVC1G97 import is retained as comparison geometry only. It is absent from the circuit BOM; its 1.65 V minimum operating supply gave a less convenient power-down boundary. The dual buffer and ordinary passives reuse already reviewed local parts. See the source-linked BOM/49-pin graph audit under `hw/boards/blind-supervisor`.

Source documents: [watchdog](https://www.ti.com/lit/ds/symlink/tps3430.pdf), [voltage supervisor](https://www.ti.com/lit/ds/symlink/tps3808.pdf), [logic gate](https://www.ti.com/lit/ds/symlink/sn74aup1g97.pdf), [Samsung capacitor specification](https://media.digikey.com/pdf/Data%20Sheets/Samsung%20PDFs/CL05C121JB5NNNC_Spec.pdf). Catalog observations are date-stamped separately; raw presale fields are not confirmed MOQ or SMT stock.

The AUP import referenced a missing 3D filename; the wrapper uses the already downloaded nominal SC70-6 body model. This is visual geometry only, not package tolerance or assembly-clearance acceptance.
