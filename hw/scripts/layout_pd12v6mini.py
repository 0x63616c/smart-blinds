#!/usr/bin/env python3
"""Deterministic placement + routing for pd12v6mini rev E (4-layer, 47.5 x 25 mm).

    /Applications/KiCad.app/Contents/Frameworks/Python.framework/Versions/Current/bin/python3 \
        scripts/layout_pd12v6mini.py [--place-only] [--dump]

Rewrites hw/layouts/pd12v6mini/pd12v6mini.kicad_pcb (run after `ato build -b pd12v6mini`).
  --place-only  write layouts/pd12v6mini_manual/ instead: same placement, zones and silk, no tracks/vias
  --dump        print every pad centre after placement and exit

Look (docs/pd12v6/mini.md):
  * reads left to right like the schematic: INPUT | BUCK over PD | OUTPUT, each group in its own
    silkscreen cell with a title. Cells are made by dividing the inset outline, so there are no double lines.
    Each status LED sits in the cell it reports on (PD bottom of PD, ON bottom of OUTPUT, same line).
  * every part sits on a shared centre line with a constant pitch; every part has its reference on the
    top silk at 0.8 mm, always on the same side within a row
  * no top copper runs under a part body except into that part's own pad (scripts/check_layout.py)
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

W, H, RAD = 47.5, 25.0, 1.5
CY = H / 2                                  # connector centre line
CNX = W - 10.9                              # Micro-Fit footprint origin (body flush with the right edge)
REV = "rev E  2026-10"

# ---- silkscreen cells (inset outline FRAME, divided at XA | XB, middle column split at YM)
FRAME = 0.6
XA, XB, YM = 13.0, CNX - 2.65, 16.45
TITLE_Y = 1.5                               # cell titles sit in the top-left corner of each cell
LABEL_Y = 3.1                               # reference row above the buck power row

# ---- anchors
PY = 7.5                                    # buck power row centre line (L1 pads clear the label row)
UX = 22.65                                  # TPS56637 centre
L1X = UX + 6.8                              # inductor: body clears the boot cap
L1P = 2.2                                   # L1 pad centres at L1X -/+ L1P
RY = PY + 5.2                               # buck control row (pads on RY -/+ 0.43)
RP = (L1X + L1P - (UX - 0.75)) / 4         # control-row pitch: R8 under EN, C2 under L1 pad 2
D1X = 11.0                                  # TVS column (VBUS strip runs up it)
U2X, U2Y = 25.2, 20.5                       # CH224A centre
SY = U2Y + 2.0                              # status LEDs on CH224A pin 10's line, PD and OUTPUT alike

PLACE = {
    "H1": (3.0, 3.0, 0), "H2": (W - 3.0, 3.0, 0), "H3": (3.0, H - 3.0, 0), "H4": (W - 3.0, H - 3.0, 0),
    # ---- INPUT: USB-C, then the TVS hanging off the VBUS strip, fed from its cathode end
    "USBC1": (4.2, CY, 270),
    "D1": (D1X, 11.1 + 2.19, 270),                   # SMAJ22A, K (VBUS) up
    # ---- BUCK power row on PY: input caps -> TPS56637 -> boot cap -> inductor
    "C3": (UX - 8.4, PY, 270), "C4": (UX - 6.4, PY, 270),   # 3 x 10 uF 1206, VBUS up / GND down
    "C9": (UX - 4.4, PY, 270),
    "C5": (UX - 2.2, PY - 0.4, 270),                  # 100 nF right at VIN/PGND
    "U1": (UX, PY, 90),                               # VIN top, SW right, EN/FB/AGND/PG bottom
    "C1": (UX + 2.8, PY - 0.91, 0),                   # boot cap on the BOOT pin line
    "L1": (L1X, PY, 0),                               # 6.8 uH, 6.4 x 6.6 mm
    # ---- BUCK control row on RY, signal pad up
    "R7": (UX - 0.75 - RP, RY, 90), "R8": (UX - 0.75, RY, 270),            # UVLO 390 k / 30 k  (EN up)
    "R3": (UX - 0.75 + RP, RY, 270), "R2": (UX - 0.75 + 2 * RP, RY, 90),   # FB 10 k / 200 k    (FB up)
    "R4": (UX - 0.75 + 3 * RP, RY, 90), "C2": (L1X + L1P, RY, 270),       # feed-forward 20 k + 100 pF
    # ---- PD: CH224A; CC / VBUS vias in one column on its left, CFG1 resistor on pin 9's line,
    #      PD LED on pin 10's line, VHV cap on pin 1's line
    "U2": (U2X, U2Y, 90),
    "R1": (U2X - 5.95, U2Y + 1.0, 180),               # CFG1 120 k, CFG1 pad toward pin 9
    "R6": (U2X - 5.0, SY, 0), "LED2": (U2X - 7.8, SY, 180),   # PG <- R6 <- LED2 <- VBUS via
    "C8": (U2X + 5.4, U2Y + 2.0, 0),                  # VHV 1 uF
    # ---- OUTPUT: caps mirrored above / below the Micro-Fit, each pad in line with a pin
    "CN1": (CNX, CY, 90),
    "C6": (CNX + 1.5 + 1.52, CY - 6.6, 0),           # VOUT pad straight above pin 1
    "C7": (CNX + 1.5 + 1.52, CY + 6.6, 180),         # GND pad straight below pin 2
    # ON status, mirror of PD: GND <- R5 <- LED1 <- VOUT via
    "R5": (W - 11.0, SY, 180), "LED1": (W - 8.2, SY, 0),
}
SILK_REFS = {r for r in PLACE if not r.startswith("H")}
BELOW = 2.2                                   # under the via row (RY + 1.2)
REF_POS = {
    **{r: (0, LABEL_Y - PLACE[r][1], 0) for r in ("C3", "C4", "C9", "C5", "U1", "C1", "L1")},
    **{r: (0, BELOW, 0) for r in ("R7", "R8", "R3", "R2", "R4", "C2")},
    "C6": (-4.15, 0, 0), "C7": (-4.15, 0, 0), "CN1": (-0.8, -3.2, 0),
    "USBC1": (0, -6.3, 0), "D1": (0, 5.6, 0),
    "U2": (0, -3.15, 0), "R1": (0, -1.0, 0), "C8": (0, -1.1, 0),
    **{r: (0, 1.1, 0) for r in ("LED2", "R6", "LED1", "R5")},
}
# 3D models: KiCad's own where one matches the package (the EasyEDA ones carry logos / wrong part text)
KI3D = "${KICAD10_3DMODEL_DIR}/"
MODELS = {
    # same 16-pin USB-C family; shifted so its pins sit on this footprint's pad row (shell legs within 0.2 mm)
    "USBC1": (KI3D + "Connector_USB.3dshapes/USB_C_Receptacle_GCT_USB4105-xx-A_16P_TopMnt_Horizontal.step",
              (0, -1.21, 0), (1, 1, 1), (0, 0, 0)),
    "D1": (KI3D + "Diode_SMD.3dshapes/D_SMA.step", (0, 0, 0), (1, 1, 1), (0, 0, 0)),
    "U2": (KI3D + "Package_SO.3dshapes/SSOP-10-1EP_3.9x4.9mm_P1mm_EP2.1x3.3mm.step", (0, 0, 0), (1, 1, 1), (0, 0, -90)),
    # PROD PSTMAA666460 is 6.4 x 6.6 x 6.0 mm (max); the Chilisin 5040 model scaled to that size
    "L1": (KI3D + "Inductor_SMD.3dshapes/L_Chilisin_BWVS00505040.step", (0, 0, 0), (6.4 / 5.02, 6.6 / 5.0, 6.0 / 4.0), (0, 0, 0)),
}

b = Board(PCB, layers=4)
b.place_only = PLACE_ONLY
b.place(PLACE, silk_refs=SILK_REFS, ref_size=0.8, ref_stroke=0.13, ref_pos=REF_POS)
b.reset(OUT)
for ref, (path, off, scale, rot) in MODELS.items():
    if not len(b.fps[ref].Models()):                # EasyEDA gave this footprint no model entry at all
        import pcbnew
        b.fps[ref].Models().append(pcbnew.FP_3DMODEL())
    m = b.fps[ref].Models()[0]
    m.m_Filename = path
    m.m_Offset.x, m.m_Offset.y, m.m_Offset.z = off
    m.m_Scale.x, m.m_Scale.y, m.m_Scale.z = scale
    m.m_Rotation.x, m.m_Rotation.y, m.m_Rotation.z = rot
if DUMP:
    b.dump(); sys.exit(0)

b.rules(clearance=0.15, track_min=0.15, via=(0.5, 0.3), via_min=(0.5, 0.3), track=0.2)
for p in b.fps["CN1"].Pads():           # Micro-Fit plastic locating peg -> NPTH
    if p.GetNumber() == "":
        import pcbnew
        p.SetAttribute(pcbnew.PAD_ATTRIB_NPTH); p.SetSize(p.GetDrillSize())
b.rounded_rect(0, 0, W, H, RAD, "Edge.Cuts", 0.1)

# ---- silkscreen: inset outline (broken at the connectors) divided into four cells
GAP_L, GAP_R = (CY - 5.6, CY + 5.6), (CY - 5.4, CY + 5.2)
b.rounded_rect(FRAME, FRAME, W - FRAME, H - FRAME, RAD - FRAME + 0.3, "F.SilkS", 0.15,
               gaps=[("left", *GAP_L), ("right", *GAP_R)])
b.rounded_rect(FRAME, FRAME, W - FRAME, H - FRAME, RAD - FRAME + 0.3, "B.SilkS", 0.15,
               gaps=[("left", *GAP_L), ("right", *GAP_R)])
b.line((XA, FRAME), (XA, H - FRAME), "F.SilkS", 0.15)
b.line((XB, FRAME), (XB, H - FRAME), "F.SilkS", 0.15)
b.line((XA, YM), (XB, YM), "F.SilkS", 0.15)
for text, x, y in (("INPUT", 5.6, TITLE_Y), ("BUCK", XA + 0.45, TITLE_Y),
                   ("PD", XA + 0.45, YM + TITLE_Y - FRAME), ("OUTPUT", XB + 0.45, TITLE_Y)):
    b.label(text, x, y, 0.8, bold=True, justify="left")

exec(open(HERE / "routes_pd12v6mini.py").read())

b.finish(OUT, mask="#0B0B0DF5", finish="ENIG", project_from=PCB if PLACE_ONLY else None,
         severities={"lib_footprint_mismatch": "ignore", "starved_thermal": "ignore",
                     **({"unconnected_items": "ignore", "isolated_copper": "ignore"} if PLACE_ONLY else {})})
print("layout written:", OUT)
