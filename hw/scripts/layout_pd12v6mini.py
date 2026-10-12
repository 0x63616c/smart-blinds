#!/usr/bin/env python3
"""Deterministic placement + routing for pd12v6mini (4-layer, 35 x 24.5 mm).

    /Applications/KiCad.app/Contents/Frameworks/Python.framework/Versions/Current/bin/python3 \
        scripts/layout_pd12v6mini.py [--place-only] [--dump]

Rewrites hw/layouts/pd12v6mini/pd12v6mini.kicad_pcb (run after `ato build -b pd12v6mini`).
  --place-only  write layouts/pd12v6mini_manual/ instead: same placement, zones and silk, no tracks/vias
  --dump        print every pad centre after placement and exit

Look-and-feel rules for this board (see docs/pd12v6/mini.md):
  * power flows in a straight line along the top: USB-C -> input caps -> TPS56637 -> inductor -> Micro-Fit
  * no reference designators on the copper side; they live on F.Fab (assembly drawing in build/review)
  * silk = product name, connector labels, LED labels, pin-1/polarity marks. Nothing else.
  * every via 0.5/0.3 mm (no <0.3 mm drill: JLCPCB charges ~$37 extra for it), tented both sides
  * matte black mask, ENIG finish
Coordinates: mm, origin top-left, +y down. Rotation: KiCad degrees (CCW on screen).
"""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from pcbkit import Board

HERE = pathlib.Path(__file__).resolve().parent
PCB = HERE.parent / "layouts" / "pd12v6mini" / "pd12v6mini.kicad_pcb"
PLACE_ONLY = "--place-only" in sys.argv
DUMP = "--dump" in sys.argv
OUT = (PCB.parent.parent / "pd12v6mini_manual" / "pd12v6mini_manual.kicad_pcb") if PLACE_ONLY else PCB
OUT.parent.mkdir(exist_ok=True)

W, H, RAD = 35.0, 24.5, 1.5
CY = 13.5                                   # connector centre line
CNX = W - 10.9                              # Micro-Fit footprint origin (body flush with the right edge)
REV = "rev B  2026-10"

# Groups (left -> right): INPUT (USB-C, TVS) | BUCK (top band + control row) | PD (U2 + status
# columns) | OUTPUT (output caps above/below the Micro-Fit). Everything on a 0.05 mm grid.
PLACE = {
    "H1": (3.0, 3.0, 0), "H2": (W - 3.0, 3.0, 0), "H3": (3.0, H - 3.0, 0), "H4": (W - 3.0, H - 3.0, 0),
    # ---- INPUT
    "USBC1": (4.2, CY, 270),
    "D1": (8.35, 20.5, 0),                             # SMAJ22A, K (VBUS) left
    # ---- BUCK power row, centre line y 4.6: input caps -> TPS56637 -> inductor
    "C3": (8.4, 4.6, 270), "C4": (10.6, 4.6, 270),   # 10 uF 1206, VBUS up / GND down
    "C5": (12.45, 4.2, 270),                          # 100 nF at VIN/PGND
    "U1": (14.7, 4.6, 90),                            # VIN top, SW exits right, EN/FB/AGND/PG bottom
    "C1": (17.5, 3.69, 0),                            # boot cap, BOOT left / SW right
    "L1": (20.4, 4.6, 0),                             # 5.6 uH
    # ---- BUCK control row: six identical 0402s, 2 mm pitch, pads on y 7.97 / 8.83, labels on y 9.85
    "R7": (11.95, 8.4, 90), "R8": (13.95, 8.4, 270),  # UVLO 390 k / 27 k        (EN on top)
    "R3": (15.95, 8.4, 270), "R2": (17.95, 8.4, 90),  # FB 10 k / 200 k          (FB on top)
    "R4": (19.95, 8.4, 90), "C2": (21.95, 8.4, 270),  # feed-forward 20 k + 100 pF (FB on top / VOUT on top)
    # ---- PD: CH224A on the centre line, CC1 straight across from the USB-C
    "U2": (15.0, CY - 0.25, 90),
    "R1": (10.4, 16.9, 270),                          # CFG1 120 k (CFG1 up)
    "R6": (12.0, 16.9, 90), "LED2": (12.0, 19.6, 270),   # left status column:  PG -> R6 -> LED2 -> VBUS
    "C8": (18.0, 16.9, 270),                          # right column: VHV 1 uF
    "LED1": (18.0, 19.6, 90), "R5": (18.0, 21.3, 270),   #               VOUT -> LED1 -> R5 -> GND
    # ---- OUTPUT: caps mirrored above / below the Micro-Fit pins
    "C6": (CNX + 1.5, 4.6, 90),                       # VOUT pad down, straight onto pin 1
    "CN1": (CNX, CY, 90),
    "C7": (CNX + 1.5, 21.0, 90),                      # GND pad up towards pin 2
}
SILK_REFS = {r for r in PLACE if not r.startswith("H")}
TOP = 1.3                                             # label row above the power row
REF_POS = {
    "C3": (0, TOP - 4.6, 0), "C4": (0, TOP - 4.6, 0), "C5": (0, TOP - 4.2, 0), "U1": (0, TOP - 4.6, 0),
    "C1": (0, TOP - 3.69, 0), "L1": (0, TOP - 4.6, 0), "C6": (2.5, 0, 0), "C7": (2.5, 0, 0),
    "R7": (0, 1.45, 0), "R8": (0, 1.45, 0), "R3": (0, 1.45, 0), "R2": (0, 1.45, 0),
    "R4": (0, 1.45, 0), "C2": (0, 1.45, 0),
    "USBC1": (-0.2, -6.5, 0), "D1": (0, -1.6, 0), "U2": (0, 3.05, 0),
    "R1": (0, 1.3, 0), "R6": (1.2, 0, 0), "LED2": (1.9, 0, 0),
    "C8": (1.2, 0, 0), "LED1": (1.9, 0, 0), "R5": (1.2, 0, 0),
    "CN1": (5.5, -5.9, 0),
}

b = Board(PCB, layers=4)
b.place_only = PLACE_ONLY
b.place(PLACE, silk_refs=SILK_REFS, ref_size=0.8, ref_stroke=0.12, ref_pos=REF_POS)
b.reset(OUT)
if DUMP:
    b.dump(); sys.exit(0)

b.rules(clearance=0.15, track_min=0.15, via=(0.5, 0.3), via_min=(0.5, 0.3), track=0.2)
for p in b.fps["CN1"].Pads():           # Micro-Fit plastic locating peg -> NPTH
    if p.GetNumber() == "":
        import pcbnew
        p.SetAttribute(pcbnew.PAD_ATTRIB_NPTH); p.SetSize(p.GetDrillSize())
b.rounded_rect(0, 0, W, H, RAD, "Edge.Cuts", 0.1)
# white inset outline on both sides, broken where the connectors cross the edge
FRAME = 0.6
for side in ("F.SilkS", "B.SilkS"):
    b.rounded_rect(FRAME, FRAME, W - FRAME, H - FRAME, RAD - FRAME + 0.3, side, 0.15,
                   gaps=[("left", CY - 5.6, CY + 5.6), ("right", CY - 5.4, CY + 5.2)])

exec(open(HERE / "routes_pd12v6mini.py").read())

b.finish(OUT, mask="Black", finish="ENIG", project_from=PCB if PLACE_ONLY else None,
         severities={"lib_footprint_mismatch": "ignore", "starved_thermal": "ignore",
                     **({"unconnected_items": "ignore", "isolated_copper": "ignore"} if PLACE_ONLY else {})})
print("layout written:", OUT)
