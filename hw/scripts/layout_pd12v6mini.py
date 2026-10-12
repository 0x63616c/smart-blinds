#!/usr/bin/env python3
"""Deterministic placement + routing for pd12v6mini (4-layer, 33 x 20 mm).

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

W, H, RAD = 33.0, 20.0, 1.5
CY = 10.0                                   # connector centre line
CNX = W - 10.9                              # Micro-Fit footprint origin (body flush with the right edge)
REV = "rev A  2026-10"

PLACE = {
    # mounting holes, M2, corners
    "H1": (2.5, 2.5, 0), "H2": (W - 2.5, 2.5, 0), "H3": (2.5, H - 2.5, 0), "H4": (W - 2.5, H - 2.5, 0),
    # connectors on the centre line, mouths outward
    "USBC1": (4.2, CY, 270),
    "CN1": (CNX, CY, 90),
    # ---- top band: power stage, left -> right ----------------------------------------------
    "C3": (8.0, 3.4, 270), "C4": (10.0, 3.4, 270),   # 2 x 10 uF 1206, VBUS pad up, GND pad down
    "C5": (11.35, 3.0, 270),                          # 100 nF right at VIN (up) / PGND (down)
    "U1": (13.6, 3.4, 90),                            # TPS56637: VIN top, SW exits right, EN/FB/AGND/PG bottom
    "C1": (16.0, 2.0, 270),                           # boot cap: BOOT up, SW down
    "L1": (19.0, 3.4, 0),                             # 5.6 uH, SW left / VOUT right
    "C6": (24.0, 2.6, 0),                             # 47 uF 1210 above the Micro-Fit body
    # ---- feedback / UVLO row under U1 (1.0 mm pitch, signal pad up) ---------------------------
    "R7": (11.5, 6.3, 90),  "R8": (12.5, 6.3, 270),  # UVLO 390 k / 27 k        (EN up)
    "R3": (13.5, 6.3, 270), "R4": (14.5, 6.3, 90),   # FB 10 k, feed-forward 20 k (FB up)
    "R2": (15.5, 6.3, 90),                            # FB 200 k                  (FB up, VOUT down)
    "C2": (14.92, 7.55, 180),                         # feed-forward 100 pF under R4/R2
    # ---- PD controller ------------------------------------------------------------------------
    "U2": (14.5, 10.5, 90),                           # CH224A: CC/VBUS/CFG1/PG column faces the USB-C
    "R1": (10.4, 14.3, 270),                          # CFG1 120 k
    "C8": (17.5, 14.0, 0),                            # VHV 1 uF
    # ---- bottom band: TVS, LEDs, second output cap -----------------------------------------
    "D1": (9.2, 17.6, 0),                             # SMAJ22A, K (VBUS) left
    "R6": (14.5, 17.6, 180), "LED2": (16.0, 17.6, 0),   # PD LED (red)
    "R5": (19.0, 17.6, 180), "LED1": (20.5, 17.6, 0),   # ON LED (green)
    "C7": (24.0, 17.4, 0),                            # 47 uF 1210 below the Micro-Fit body
}

b = Board(PCB, layers=4)
b.place_only = PLACE_ONLY
b.place(PLACE, silk_refs=set())
b.reset(OUT)
if DUMP:
    b.dump(); sys.exit(0)

b.rules(clearance=0.15, track_min=0.15, via=(0.5, 0.3), via_min=(0.5, 0.3), track=0.2)
for p in b.fps["CN1"].Pads():           # Micro-Fit plastic locating peg -> NPTH
    if p.GetNumber() == "":
        import pcbnew
        p.SetAttribute(pcbnew.PAD_ATTRIB_NPTH); p.SetSize(p.GetDrillSize())
b.rounded_rect(0, 0, W, H, RAD, "Edge.Cuts", 0.1)

exec(open(HERE / "routes_pd12v6mini.py").read())

b.finish(OUT, mask="Black", finish="ENIG", project_from=PCB if PLACE_ONLY else None,
         severities={"lib_footprint_mismatch": "ignore", "starved_thermal": "ignore",
                     **({"unconnected_items": "ignore", "isolated_copper": "ignore"} if PLACE_ONLY else {})})
print("layout written:", OUT)
