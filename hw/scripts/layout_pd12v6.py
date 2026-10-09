#!/usr/bin/env python3
"""Deterministic placement + routing for the pd12v6 board.

Run with KiCad's bundled Python (it has `pcbnew`):

    /Applications/KiCad.app/Contents/Frameworks/Python.framework/Versions/Current/bin/python3 \
        scripts/layout_pd12v6.py

It rewrites hw/layouts/pd12v6/pd12v6.kicad_pcb in place: footprints are moved to the
coordinates below, all old tracks/vias/zones/outline are deleted and regenerated.
Re-run it after every `ato build` so the layout is always reproducible from source.

Coordinates are mm, origin = board top-left, +y is DOWN (KiCad convention).
Rotation is KiCad's (degrees, counter-clockwise on screen).
"""
import sys, re, json, pathlib
import pcbnew
from pcbnew import VECTOR2I, FromMM

HERE = pathlib.Path(__file__).resolve().parent
PCB = HERE.parent / "layouts" / "pd12v6" / "pd12v6.kicad_pcb"

# ----------------------------------------------------------------------------- board
W, H, RAD = 41.0, 36.0, 2.0            # outline (mm) and corner radius
CLEARANCE, TRACK_MIN = 0.15, 0.15      # JLCPCB 2-layer capability is 0.127 mm
VIA_D, VIA_DRILL = 0.6, 0.3
PWR_VIA_D, PWR_VIA_DRILL = 0.8, 0.4

# ----------------------------------------------------------------------------- placement
# ref: (x, y, rot).  Power flows left -> right along the top; PD controller bottom-left;
# current-limit op-amp bottom-centre; XT30 on the right edge, USB-C on the left edge.
PLACE = {
    # mounting holes
    "H1": (3.0, 3.0, 0), "H2": (W - 3.0, 3.0, 0), "H3": (3.0, H - 3.0, 0), "H4": (W - 3.0, H - 3.0, 0),
    # USB-C, opening faces -x and overhangs the left edge ~1 mm
    "USBC1": (4.2, 15.0, 270),
    # buck input: 2x10u + 100n, VBUS bus along y ~ 7.2
    "C5": (7.7, 5.5, 90), "C4": (10.8, 5.5, 90), "C6": (10.9, 9.5, 0),
    "U1": (16.5, 8.0, 270),               # VIN/BOOT/EN/RT on the left column, SW/GND/COMP/FB right
    "C1": (16.5, 4.3, 0),                 # boot cap above U1 (BOOT left, SW right)
    "D1": (22.6, 5.3, 90),                # catch diode: K bottom (SW), A top (GND)
    "L1": (30.5, 9.0, 0),
    # under U1: UVLO + RT on the left column, FB/COMP network on the right, FB clamp diode
    "R14": (10.1, 11.3, 0), "R15": (12.0, 11.9, 270), "R11": (13.6, 11.9, 270),
    "D2": (16.5, 12.4, 0),
    "R4": (19.5, 12.0, 270), "R3": (20.8, 12.0, 90),
    "C2": (22.7, 9.4, 0), "R2": (22.7, 11.3, 0), "C3": (23.7, 12.4, 0),
    # TVS right of the USB-C
    "D3": (11.1, 18.5, 270),
    # PD controller + PD LED
    "U3": (15.0, 22.5, 0), "C12": (10.8, 25.5, 180),
    "R8": (12.8, 17.4, 270), "R1": (14.2, 17.4, 90), "LED2": (12.6, 14.5, 180),
    # data header under the USB-C
    "J1": (6.3, 22.5, 0),
    # output: caps under L1, XT30 on the right edge, output LED top-right
    "C9": (20.2, 17.5, 270), "C10": (23.3, 17.5, 270),
    "CN1": (34.3, 21.0, 270),
    "LED1": (38.8, 8.0, 90), "R7": (38.8, 11.0, 270),
    # current limit: shunt bottom-right, op-amp bottom-centre
    "R13": (32.0, 31.5, 180),
    "U2": (22.7, 31.5, 180),
    "R12": (18.2, 33.4, 90), "C11": (18.2, 29.5, 90),
    "R9": (19.6, 24.0, 0), "R10": (19.6, 25.8, 180), "R6": (22.1, 25.8, 0),
    "C7": (24.55, 26.2, 180), "R5": (27.0, 26.2, 0), "C8": (26.2, 34.0, 0),
}

# ----------------------------------------------------------------------------- helpers
def mm(v): return FromMM(v)
def pt(x, y): return VECTOR2I(mm(x), mm(y))

board = pcbnew.LoadBoard(str(PCB))
if board is None:
    sys.exit(f"pcbnew could not load {PCB}")
fps = {f.GetReference(): f for f in board.GetFootprints()}
LAYER = {n: board.GetLayerID(n) for n in ["F.Cu", "B.Cu", "Edge.Cuts", "F.SilkS", "B.SilkS", "F.Mask", "B.Mask", "F.Fab", "User.1"]}

# ---- placement + footprint cosmetics.
# NOTE: every Remove() (zones, drawings, footprint graphics) corrupts the other SWIG wrappers in
# KiCad 10's pcbnew module, so all removals happen here first, then the board is saved + reloaded.
missing = set(fps) - set(PLACE)
if missing: sys.exit(f"unplaced footprints: {sorted(missing)}")
for ref, (x, y, rot) in PLACE.items():
    f = fps[ref]
    f.SetPosition(pt(x, y))
    f.SetOrientationDegrees(rot)
    for fld in f.GetFields():                # clean silkscreen; refs stay in the fab outputs
        if fld.GetName() == "Reference": fld.SetVisible(False)
# footprint silkscreen is dropped entirely (0603 outlines collide on a board this dense);
# the board gets its own labels instead (see labels() below). F.Fab keeps every outline.
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
    return (v.x / 1e6, v.y / 1e6)

def net(name):
    n = board.FindNet(name)
    if n is None: raise KeyError(name)
    return n

# ---- wipe generated geometry (tracks, vias, zones, outline) so the script is idempotent.
_old_drawings = [d for d in board.Drawings()
                 if d.GetLayer() in (LAYER["Edge.Cuts"], LAYER["User.1"]) or isinstance(d, pcbnew.PCB_TEXT)]
_old_tracks = list(board.GetTracks())
_old_zones = list(board.Zones())
for item in _old_drawings + _old_tracks + _old_zones:
    board.Remove(item)
for f, g in _off:
    f.Remove(g)
# save + reload so every SWIG wrapper is fresh (see note above)
board.Save(str(PCB))
board = pcbnew.LoadBoard(str(PCB))
fps = {f.GetReference(): f for f in board.GetFootprints()}
LAYER = {n: board.GetLayerID(n) for n in LAYER}

# ---- design rules
ds = board.GetDesignSettings()
ds.m_MinClearance = mm(CLEARANCE)
ds.m_TrackMinWidth = mm(TRACK_MIN)
ds.m_ViasMinSize = mm(0.5)
ds.m_MinThroughDrill = mm(0.3)
ds.m_CopperEdgeClearance = mm(0.3)
ds.m_HoleClearance = mm(0.25)
ds.m_SolderMaskMinWidth = mm(0.1)
nc = ds.m_NetSettings.GetDefaultNetclass()
nc.SetClearance(mm(CLEARANCE)); nc.SetTrackWidth(mm(0.25)); nc.SetViaDiameter(mm(VIA_D)); nc.SetViaDrill(mm(VIA_DRILL))

# unnumbered thermal-via pads in U1's footprint and the USB-C shell pegs are GND
for ref in ("U1",):
    for p in fps[ref].Pads():
        if p.GetNumber() == "": p.SetNet(net("GND"))

# ---- outline: rounded rectangle
def outline():
    def line(a, b):
        s = pcbnew.PCB_SHAPE(board, pcbnew.SHAPE_T_SEGMENT); s.SetLayer(LAYER["Edge.Cuts"])
        s.SetStart(pt(*a)); s.SetEnd(pt(*b)); s.SetWidth(mm(0.1)); board.Add(s)
    def arc(center, start, end):
        s = pcbnew.PCB_SHAPE(board, pcbnew.SHAPE_T_ARC); s.SetLayer(LAYER["Edge.Cuts"])
        s.SetCenter(pt(*center)); s.SetStart(pt(*start)); s.SetEnd(pt(*end)); s.SetWidth(mm(0.1)); board.Add(s)
    r = RAD
    line((r, 0), (W - r, 0)); line((W, r), (W, H - r)); line((W - r, H), (r, H)); line((0, H - r), (0, r))
    # arcs: KiCad arcs go counter-clockwise (on screen, y down) from start to end
    arc((W - r, r), (W - r, 0), (W, r))        # top-right
    arc((W - r, H - r), (W, H - r), (W - r, H))  # bottom-right
    arc((r, H - r), (r, H), (0, H - r))        # bottom-left
    arc((r, r), (0, r), (r, 0))                # top-left
outline()

# ---- silkscreen labels (text, x, y, size, layer, rotation); edit freely
LABELS = [
    ("e8s pd12v6",  20.5,  1.6, 0.9, "F.SilkS", 0),
    ("USB-C PD IN",  5.2, 29.8, 0.8, "F.SilkS", 0),
    ("D-",           3.76, 24.1, 0.8, "F.SilkS", 0),
    ("D+",           6.3,  24.1, 0.8, "F.SilkS", 0),
    ("GND",          8.84, 24.1, 0.8, "F.SilkS", 0),
    ("12.6V",       33.4,  3.2, 0.8, "F.SilkS", 0),
    ("-",           39.0, 13.4, 1.2, "F.SilkS", 0),
    ("+",           39.0, 28.6, 1.2, "F.SilkS", 0),
    ("PD",          15.4, 14.9, 0.8, "F.SilkS", 0),
    ("ON",          38.8,  5.6, 0.8, "F.SilkS", 0),
    ("e8s pd12v6  USB-C PD -> 12.6 V / 4.5 A", 20.5, 29.6, 0.9, "B.SilkS", 0),
]
def label(text, x, y, size, layer, rot):
    t = pcbnew.PCB_TEXT(board); t.SetText(text); t.SetLayer(LAYER[layer]); t.SetPosition(pt(x, y))
    t.SetTextSize(VECTOR2I(mm(size), mm(size))); t.SetTextThickness(mm(round(size * 0.15, 2)))
    t.SetTextAngleDegrees(rot); t.SetMirrored(layer.startswith("B."))
    board.Add(t)
for L in LABELS: label(*L)

# ----------------------------------------------------------------------------- routing
def track(netname, pts, layer="F.Cu", width=0.25):
    for a, b in zip(pts, pts[1:]):
        t = pcbnew.PCB_TRACK(board); t.SetLayer(LAYER[layer]); t.SetWidth(mm(width))
        t.SetStart(pt(*a)); t.SetEnd(pt(*b)); t.SetNet(net(netname)); board.Add(t)

def via(netname, xy, d=VIA_D, drill=VIA_DRILL):
    v = pcbnew.PCB_VIA(board); v.SetPosition(pt(*xy)); v.SetWidth(mm(d)); v.SetDrill(mm(drill))
    v.SetLayerPair(LAYER["F.Cu"], LAYER["B.Cu"]); v.SetNet(net(netname)); board.Add(v)

def zone(netname, layer, rect, priority=0, thermal=True):
    z = pcbnew.ZONE(board); z.SetLayer(LAYER[layer]); z.SetNet(net(netname))
    (x0, y0), (x1, y1) = rect
    z.Outline().NewOutline()
    for x, y in ((x0, y0), (x1, y0), (x1, y1), (x0, y1)): z.Outline().Append(mm(x), mm(y))
    z.SetAssignedPriority(priority)
    z.SetLocalClearance(mm(0.2)); z.SetMinThickness(mm(0.2))
    z.SetPadConnection(pcbnew.ZONE_CONNECTION_THERMAL if thermal else pcbnew.ZONE_CONNECTION_FULL)
    z.SetThermalReliefGap(mm(0.3)); z.SetThermalReliefSpokeWidth(mm(0.4))
    z.SetIsFilled(False); board.Add(z); return z

exec(open(HERE / "routes_pd12v6.py").read())   # ROUTES live in a sibling file (kept separate for readability)

# ---- fill zones and save
filler = pcbnew.ZONE_FILLER(board); filler.Fill(board.Zones())
board.Save(str(PCB))

# black solder mask + matte: stored in the stackup block (KiCad reads it for 3D/plot colours)
s = PCB.read_text()
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
PCB.write_text(s)
# footprint silk is stripped on purpose (see above), so the library-mismatch DRC check is noise;
# severities live in the project file, which is also where the black solder mask colour goes.
PRO = PCB.with_suffix(".kicad_pro")
pro = json.loads(PRO.read_text()) if PRO.exists() else {}
pro.setdefault("board", {}).setdefault("design_settings", {}).setdefault("rule_severities", {})["lib_footprint_mismatch"] = "ignore"
PRO.write_text(json.dumps(pro, indent=2) + "\n")
print("layout written:", PCB)
