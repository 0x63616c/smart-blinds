#!/usr/bin/env python3
"""Deterministic placement + routing for the pd12v6 board (4-layer, 40 x 32 mm).

Run with KiCad's bundled Python (it has `pcbnew`):

    /Applications/KiCad.app/Contents/Frameworks/Python.framework/Versions/Current/bin/python3 \
        scripts/layout_pd12v6.py [--place-only] [--dump]

It rewrites hw/layouts/pd12v6/pd12v6.kicad_pcb in place: footprints are moved to the
coordinates below, all old tracks/vias/zones/outline/labels are deleted and regenerated.
Re-run it after every `ato build` so the layout is always reproducible from source.

    --place-only  write layouts/pd12v6_manual/pd12v6_manual.kicad_pcb instead: same placement,
                  outline, planes, silk and labels, but NO tracks or signal vias (hand-route it).
                  That file is a derived copy; `ato build` only syncs the main pcb.
    --dump        print every pad centre (mm) after placement and exit (used to write routes).

Coordinates are mm, origin = board top-left, +y is DOWN (KiCad convention).
Rotation is KiCad's (degrees, counter-clockwise on screen).

Layout rules used (see docs/pd12v6/design.md):
  * one 0.5 mm grid, every part orthogonal, ICs in one orientation (pin 1 top-left)
  * signal flow left -> right: USB-C | PD controller + input caps | buck | inductor | output
  * passives in constant-pitch rows under the IC they belong to
  * inset white silk frame, labels on every connector pin, name/rev corner, black mask
  * 4 layers: F.Cu signals + power, In1.Cu unbroken GND, In2.Cu VBUS/VOUT pours, B.Cu GND + a few signals
"""
import sys, re, json, pathlib, shutil
import pcbnew
from pcbnew import VECTOR2I, FromMM

HERE = pathlib.Path(__file__).resolve().parent
PCB = HERE.parent / "layouts" / "pd12v6" / "pd12v6.kicad_pcb"
PLACE_ONLY = "--place-only" in sys.argv
DUMP = "--dump" in sys.argv
# The hand-route copy lives in its own folder: atopile allows only one layout per folder.
OUT = (PCB.parent.parent / "pd12v6_manual" / "pd12v6_manual.kicad_pcb") if PLACE_ONLY else PCB
OUT.parent.mkdir(exist_ok=True)

# ----------------------------------------------------------------------------- board
W, H, RAD = 40.0, 32.0, 2.0            # outline (mm) and corner radius
FRAME = 0.7                            # silk frame inset from the edge
CLEARANCE, TRACK_MIN = 0.15, 0.15      # JLCPCB 4-layer capability is 0.09 mm; keep margin
VIA_D, VIA_DRILL = 0.6, 0.3
PWR_VIA_D, PWR_VIA_DRILL = 0.8, 0.4
REV = "rev A  2026-10"

# ----------------------------------------------------------------------------- placement
# ref: (x, y, rot)
PLACE = {
    # mounting holes, M2, one in each corner (GND)
    "H1": (3.5, 3.5, 0), "H2": (W - 3.5, 3.5, 0), "H3": (3.5, H - 3.5, 0), "H4": (W - 3.5, H - 3.5, 0),
    # connectors: USB-C on the left edge (mouth -x, overhangs 1 mm), Micro-Fit on the right edge (mouth +x, flush)
    "USBC1": (4.2, 17.5, 270),
    "CN1": (W - 10.9, 17.5, 90),
    # --- top band: buck converter, power flows left -> right -------------------------------
    "D2": (8.25, 8.5, 270),              # TVS right behind the USB-C VBUS pads (VBUS pad up)
    "C4": (11.8, 8.5, 270), "C5": (15.4, 8.5, 270), # 2 x 10 uF input, VBUS top / GND bottom
    "U1": (21.5, 8.5, 270),              # TPS54560: BOOT/VIN/EN/RT column left, SW/GND/COMP/FB right
    "C1": (19.5, 3.0, 0),                # boot cap above U1
    "D1": (26.0, 3.0, 0),                # catch diode above the SW corner, K left (SW), A right (GND)
    "L1": (30.0, 8.4, 0),                # inductor, SW left pad, VOUT right pad
    "C7": (36.5, 8.5, 90),               # 47 uF output cap at the inductor
    # row 1 under U1 (2.5 mm pitch, vertical): VIN decoupling, UVLO divider, RT, COMP network
    "C6": (13.0, 13.5, 90), "R8": (15.5, 13.5, 90), "R9": (18.0, 13.5, 270), "R7": (20.5, 13.5, 270),
    "C3": (23.0, 13.5, 90), "R2": (25.5, 13.5, 270),
    # row 2 (right of U2): COMP HF cap and FB divider, right under the FB pin
    "R3": (21.5, 17.0, 90), "R4": (23.5, 17.0, 270), "C2": (25.5, 17.0, 270),
    # --- middle: PD controller between the USB-C and the output connector ------------------
    "U2": (14.5, 17.25, 90),             # CH224A: CC/VBUS/CFG1/PG column faces the USB-C, DP/DM/VHV column right
    "C9": (19.5, 17.25, 90),             # VHV decoupling
    # row 3 under U2: CFG1 resistor, PD LED resistor, PD LED
    "R1": (10.0, 22.5, 270), "R6": (12.5, 22.5, 90), "LED2": (15.0, 22.5, 90),
    # --- bottom right: second output cap under the connector pins, ON LED ------------------
    "C8": (31.5, 26.0, 90),
    "R5": (26.5, 26.0, 90), "LED1": (28.5, 26.0, 90),
}
# silkscreen reference designators: only parts big enough to label legibly (0603 refs stay on F.Fab)
SILK_REFS = {"U1", "U2", "L1", "D1", "D2", "C4", "C5", "C7", "C8", "LED1", "LED2", "CN1", "USBC1"}
REF_SIZE, REF_STROKE = 0.8, 0.12
# ref text offset from the part centre (mm) and rotation; default = above the part
REF_POS = {
    "USBC1": (0.0, -6.0, 0), "CN1": (-3.6, 5.5, 0),
    "U1": (0.0, -3.9, 0), "U2": (0.0, 3.25, 0), "L1": (0.0, -4.1, 0),
    "D1": (0.0, 2.3, 0), "D2": (0.0, -4.9, 0),
    "C4": (0.0, -4.7, 0), "C5": (0.0, -4.7, 0), "C7": (0.0, 3.1, 0), "C8": (0.0, 3.4, 0),
    "LED1": (0.0, 2.3, 0), "LED2": (0.0, 2.3, 0),
}

# ----------------------------------------------------------------------------- helpers
def mm(v): return FromMM(v)
def pt(x, y): return VECTOR2I(mm(x), mm(y))

board = pcbnew.LoadBoard(str(PCB))
if board is None:
    sys.exit(f"pcbnew could not load {PCB}")
board.SetCopperLayerCount(4)
fps = {f.GetReference(): f for f in board.GetFootprints()}
LAYER_NAMES = ["F.Cu", "In1.Cu", "In2.Cu", "B.Cu", "Edge.Cuts", "F.SilkS", "B.SilkS", "F.Mask", "B.Mask", "F.Fab", "B.Fab", "User.1"]
LAYER = {n: board.GetLayerID(n) for n in LAYER_NAMES}

# ---- placement + footprint cosmetics.
# NOTE: every Remove() (zones, drawings, footprint graphics) corrupts the other SWIG wrappers in
# KiCad 10's pcbnew module, so all removals happen here first, then the board is saved + reloaded.
missing = set(fps) - set(PLACE)
if missing: sys.exit(f"unplaced footprints: {sorted(missing)}")
for ref, (x, y, rot) in PLACE.items():
    f = fps[ref]
    f.SetPosition(pt(x, y))
    f.SetOrientationDegrees(rot)
    for fld in f.GetFields():
        if fld.GetName() == "Reference":
            fld.SetVisible(ref in SILK_REFS)
            fld.SetLayer(LAYER["F.SilkS"])
            fld.SetTextSize(VECTOR2I(mm(REF_SIZE), mm(REF_SIZE))); fld.SetTextThickness(mm(REF_STROKE))
            dx, dy, trot = REF_POS.get(ref, (0.0, -2.0, 0))
            fld.SetPosition(pt(x + dx, y + dy)); fld.SetTextAngleDegrees(trot)
            fld.SetKeepUpright(False)
            fld.SetHorizJustify(pcbnew.GR_TEXT_H_ALIGN_CENTER); fld.SetVertJustify(pcbnew.GR_TEXT_V_ALIGN_CENTER)
            fld.SetMirrored(False)
        elif fld.GetName() == "Value":
            fld.SetVisible(False)
# footprint silkscreen is dropped entirely (library outlines collide on a board this dense);
# the board gets its own labels/polarity marks instead (see labels() below). F.Fab keeps every outline.
_off = [(f, g) for f in fps.values() for g in f.GraphicalItems()
        if g.GetLayer() in (LAYER["F.SilkS"], LAYER["B.SilkS"])]

def pad(ref, num):
    for p in fps[ref].Pads():
        if p.GetNumber() == str(num):
            return p
    raise KeyError(f"{ref} pad {num}")

def P(ref, num):
    """pad centre in mm"""
    v = pad(ref, num).GetPosition()
    return (round(v.x / 1e6, 3), round(v.y / 1e6, 3))

def net(name):
    n = board.FindNet(name)
    if n is None: raise KeyError(name)
    return n

# ---- wipe generated geometry (tracks, vias, zones, outline, text) so the script is idempotent.
_old_drawings = [d for d in board.Drawings()
                 if d.GetLayer() in (LAYER["Edge.Cuts"], LAYER["User.1"], LAYER["F.SilkS"], LAYER["B.SilkS"])]
_old_tracks = list(board.GetTracks())
_old_zones = list(board.Zones())
for item in _old_drawings + _old_tracks + _old_zones:
    board.Remove(item)
for f, g in _off:
    f.Remove(g)
# save + reload so every SWIG wrapper is fresh (see note above)
board.Save(str(OUT))
board = pcbnew.LoadBoard(str(OUT))
fps = {f.GetReference(): f for f in board.GetFootprints()}
LAYER = {n: board.GetLayerID(n) for n in LAYER}

if DUMP:
    for ref in sorted(fps):
        for p in fps[ref].Pads():
            v = p.GetPosition(); print(f"{ref:6} {p.GetNumber():5} {p.GetNetname():10} ({v.x/1e6:.3f}, {v.y/1e6:.3f})")
    sys.exit(0)

# ---- design rules (JLCPCB 4-layer: 0.09 mm track/space, 0.2 mm drill; we keep 0.15 / 0.3)
ds = board.GetDesignSettings()
ds.m_MinClearance = mm(CLEARANCE)
ds.m_TrackMinWidth = mm(TRACK_MIN)
ds.m_ViasMinSize = mm(0.45)
ds.m_MinThroughDrill = mm(0.25)
ds.m_CopperEdgeClearance = mm(0.3)
ds.m_HoleClearance = mm(0.25)
ds.m_SolderMaskMinWidth = mm(0.1)
nc = ds.m_NetSettings.GetDefaultNetclass()
nc.SetClearance(mm(CLEARANCE)); nc.SetTrackWidth(mm(0.25)); nc.SetViaDiameter(mm(VIA_D)); nc.SetViaDrill(mm(VIA_DRILL))

# unnumbered thermal-via pads in U1's footprint are GND; CN1's unnumbered pad is its plastic locating peg (NPTH)
for p in fps["U1"].Pads():
    if p.GetNumber() == "": p.SetNet(net("GND"))
for p in fps["CN1"].Pads():
    if p.GetNumber() == "": p.SetAttribute(pcbnew.PAD_ATTRIB_NPTH); p.SetSize(p.GetDrillSize())

# ---- outline: rounded rectangle
def line(a, b, layer="Edge.Cuts", w=0.1):
    s = pcbnew.PCB_SHAPE(board, pcbnew.SHAPE_T_SEGMENT); s.SetLayer(LAYER[layer])
    s.SetStart(pt(*a)); s.SetEnd(pt(*b)); s.SetWidth(mm(w)); board.Add(s)
def arc(center, start, end, layer="Edge.Cuts", w=0.1):
    s = pcbnew.PCB_SHAPE(board, pcbnew.SHAPE_T_ARC); s.SetLayer(LAYER[layer])
    s.SetCenter(pt(*center)); s.SetStart(pt(*start)); s.SetEnd(pt(*end)); s.SetWidth(mm(w)); board.Add(s)
def rounded_rect(x0, y0, x1, y1, r, layer, w, gaps=()):
    """rectangle with rounded corners; `gaps` = list of (side, a, b) spans to leave out of a side"""
    def side(a, b, s):
        # split the straight side a->b into pieces avoiding gaps for this side
        spans = sorted((lo, hi) for sd, lo, hi in gaps if sd == s)
        (ax, ay), (bx, by) = a, b
        horiz = ay == by
        lo, hi = (min(ax, bx), max(ax, bx)) if horiz else (min(ay, by), max(ay, by))
        cur = lo
        for g0, g1 in spans:
            if g0 > cur: line((cur, ay) if horiz else (ax, cur), (g0, ay) if horiz else (ax, g0), layer, w)
            cur = max(cur, g1)
        if cur < hi: line((cur, ay) if horiz else (ax, cur), (hi, ay) if horiz else (ax, hi), layer, w)
    side((x0 + r, y0), (x1 - r, y0), "top"); side((x1, y0 + r), (x1, y1 - r), "right")
    side((x1 - r, y1), (x0 + r, y1), "bottom"); side((x0, y1 - r), (x0, y0 + r), "left")
    # arcs: KiCad arcs go counter-clockwise (on screen, y down) from start to end
    arc((x1 - r, y0 + r), (x1 - r, y0), (x1, y0 + r), layer, w)
    arc((x1 - r, y1 - r), (x1, y1 - r), (x1 - r, y1), layer, w)
    arc((x0 + r, y1 - r), (x0 + r, y1), (x0, y1 - r), layer, w)
    arc((x0 + r, y0 + r), (x0, y0 + r), (x0 + r, y0), layer, w)
rounded_rect(0, 0, W, H, RAD, "Edge.Cuts", 0.1)

# ---- silk frame: inset white outline, broken where the connectors cross the edge
usb_y0, usb_y1 = 17.5 - 5.6, 17.5 + 5.6
cn_y0, cn_y1 = 17.5 - 5.7, 17.5 + 5.7
rounded_rect(FRAME, FRAME, W - FRAME, H - FRAME, RAD - FRAME + 0.3, "F.SilkS", 0.15,
             gaps=[("left", usb_y0, usb_y1), ("right", cn_y0, cn_y1)])
rounded_rect(FRAME, FRAME, W - FRAME, H - FRAME, RAD - FRAME + 0.3, "B.SilkS", 0.15,
             gaps=[("left", usb_y0, usb_y1), ("right", cn_y0, cn_y1)])

# ---- silkscreen labels (text, x, y, size, layer, rotation, [justify]); edit freely
def label(text, x, y, size=0.8, layer="F.SilkS", rot=0, bold=False):
    t = pcbnew.PCB_TEXT(board); t.SetText(text); t.SetLayer(LAYER[layer]); t.SetPosition(pt(x, y))
    t.SetTextSize(VECTOR2I(mm(size), mm(size))); t.SetTextThickness(mm(round(size * (0.2 if bold else 0.15), 2)))
    t.SetTextAngleDegrees(rot); t.SetMirrored(layer.startswith("B."))
    board.Add(t)

cn = PLACE["CN1"]
LABELS = [
    # title block, bottom-left free area
    ("e8s  pd12v6", 14.0, 26.3, 1.2, "F.SilkS", 0, True),
    ("USB-C PD -> 12.6 V 4.5 A", 14.0, 28.0, 0.8, "F.SilkS", 0, False),
    (REV, 14.0, 29.5, 0.8, "F.SilkS", 0, False),
    # connectors
    ("PD IN", 4.2, 24.6, 0.8, "F.SilkS", 0, True),
    ("12.6 V OUT", 35.6, 23.0, 0.8, "F.SilkS", 0, True),
    # LEDs
    ("PD", 16.5, 22.5, 0.8, "F.SilkS", 0, False),
    ("ON", 28.5, 23.8, 0.8, "F.SilkS", 0, False),
    # back side: pinout + name (mirrored automatically)
    ("e8s pd12v6  " + REV, 20.0, 29.0, 1.0, "B.SilkS", 0, True),
    ("Micro-Fit 3.0:  1 +12.6V  2 GND  3 D+  4 D-", 20.0, 27.0, 0.8, "B.SilkS", 0, False),
    ("USB-C PD 65/100 W in.  Output NOT current limited.", 20.0, 25.0, 0.8, "B.SilkS", 0, False),
]
for L in LABELS: label(*L)

# ---- polarity / pin-1 marks (computed from pad positions so they survive placement edits)
def dot(x, y, d=0.5, layer="F.SilkS"):
    s = pcbnew.PCB_SHAPE(board, pcbnew.SHAPE_T_CIRCLE); s.SetLayer(LAYER[layer])
    s.SetCenter(pt(x, y)); s.SetEnd(pt(x + d / 2, y)); s.SetWidth(mm(0.15)); s.SetFilled(True); board.Add(s)
def bar(x, y, length, vertical, layer="F.SilkS", w=0.2):
    if vertical: line((x, y - length / 2), (x, y + length / 2), layer, w)
    else: line((x - length / 2, y), (x + length / 2, y), layer, w)

# ----------------------------------------------------------------------------- routing
def track(netname, pts, layer="F.Cu", width=0.25):
    for a, b in zip(pts, pts[1:]):
        t = pcbnew.PCB_TRACK(board); t.SetLayer(LAYER[layer]); t.SetWidth(mm(width))
        t.SetStart(pt(*a)); t.SetEnd(pt(*b)); t.SetNet(net(netname)); board.Add(t)

def via(netname, xy, d=VIA_D, drill=VIA_DRILL):
    v = pcbnew.PCB_VIA(board); v.SetPosition(pt(*xy)); v.SetWidth(mm(d)); v.SetDrill(mm(drill))
    v.SetLayerPair(LAYER["F.Cu"], LAYER["B.Cu"]); v.SetNet(net(netname)); board.Add(v)

def zone(netname, layer, poly, priority=0, thermal=True, clearance=0.2, minw=0.2):
    """poly: either ((x0,y0),(x1,y1)) rectangle or a list of >=3 points"""
    z = pcbnew.ZONE(board); z.SetLayer(LAYER[layer]); z.SetNet(net(netname))
    if len(poly) == 2:
        (x0, y0), (x1, y1) = poly; poly = [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]
    z.Outline().NewOutline()
    for x, y in poly: z.Outline().Append(mm(x), mm(y))
    z.SetAssignedPriority(priority)
    z.SetLocalClearance(mm(clearance)); z.SetMinThickness(mm(minw))
    z.SetPadConnection(pcbnew.ZONE_CONNECTION_THERMAL if thermal else pcbnew.ZONE_CONNECTION_FULL)
    z.SetThermalReliefGap(mm(0.3)); z.SetThermalReliefSpokeWidth(mm(0.4))
    z.SetIsFilled(False); board.Add(z); return z

if PLACE_ONLY:   # hand-routing copy: keep zones/labels/marks, drop every track and via
    def track(*a, **k): pass
    def via(*a, **k): pass
exec(open(HERE / "routes_pd12v6.py").read())   # ROUTES live in a sibling file (kept separate for readability)

# ---- fill zones and save
filler = pcbnew.ZONE_FILLER(board); filler.Fill(board.Zones())
board.Save(str(OUT))

# black solder mask + matte: stored in the stackup block (KiCad reads it for 3D/plot colours)
s = OUT.read_text()
s = s.replace('\n\t\t\t\t(color "Black")', '')      # strip any previous run first (idempotent)
s = s.replace('(layer "F.Mask"\n\t\t\t\t(type "Top Solder Mask")', '(layer "F.Mask"\n\t\t\t\t(type "Top Solder Mask")\n\t\t\t\t(color "Black")') \
     .replace('(layer "B.Mask"\n\t\t\t\t(type "Bottom Solder Mask")', '(layer "B.Mask"\n\t\t\t\t(type "Bottom Solder Mask")\n\t\t\t\t(color "Black")')
# KiCad 10 writes a few setup tokens atopile 0.15 (KiCad 9 grammar) cannot parse -> rewrite them.
s = re.sub(r'\(tenting\s*\(front (yes|no)\)\s*\(back (yes|no)\)\s*\)',
           lambda m: "(tenting" + (" front" if m.group(1) == "yes" else "") + (" back" if m.group(2) == "yes" else "") + ")", s)
s = re.sub(r'\n\t\t\((covering|plugging)\s*\(front (yes|no)\)\s*\(back (yes|no)\)\s*\)', '', s)
s = re.sub(r'\n\t\t\((capping|filling) (yes|no)\)', '', s)
# KiCad 10 dropped the net table and writes (net "NAME") everywhere; KiCad 9 (and atopile 0.15)
# expect a (net N "NAME") table after (setup) and numbered references on pads/tracks/vias/zones.
s = s.replace('(version 20260206)', '(version 20241229)', 1).replace('(generator_version "10.0")', '(generator_version "9.0")', 1)
_nets = {code: n.GetNetname() for code, n in board.GetNetInfo().NetsByNetcode().items()}
_table = "".join(f'\n\t(net {code} "{name}")' for code, name in sorted(_nets.items()))
_bycode = {name: code for code, name in _nets.items()}
s = re.sub(r'\(net "([^"]*)"\)', lambda m: f'(net {_bycode[m.group(1)]} "{m.group(1)}")', s)
s = re.sub(r'\(zone\n\t\t\(net (\d+) "([^"]*)"\)', r'(zone\n\t\t(net \1)\n\t\t(net_name "\2")', s)  # zones: number + net_name
s = re.sub(r'\n\t\t\(net (\d+) "[^"]*"\)', r'\n\t\t(net \1)', s)   # segments/vias: number only
_i = s.index("\n\t(footprint")
s = s[:_i] + _table + s[_i:]
OUT.write_text(s)
# footprint silk is stripped on purpose (see above), so the library-mismatch DRC check is noise;
# severities live in the project file, which is also where the black solder mask colour goes.
PRO = OUT.with_suffix(".kicad_pro")
if PLACE_ONLY:   # the manual copy needs its own project + footprint library table next to it
    shutil.copy(PCB.with_suffix(".kicad_pro"), PRO)
    shutil.copy(PCB.with_name("fp-lib-table"), OUT.with_name("fp-lib-table"))
pro = json.loads(PRO.read_text()) if PRO.exists() else {}
sev = pro.setdefault("board", {}).setdefault("design_settings", {}).setdefault("rule_severities", {})
sev["lib_footprint_mismatch"] = "ignore"
sev["starved_thermal"] = "ignore"
if PLACE_ONLY:   # no tracks yet, so the ratsnest and the island pours are expected
    sev["unconnected_items"] = "ignore"; sev["isolated_copper"] = "ignore"   # U1 pin 7 is tied to the exposed pad by a track; the zone spoke is redundant
PRO.write_text(json.dumps(pro, indent=2) + "\n")
print("layout written:", OUT)
