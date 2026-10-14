"""Shared plumbing for the scripted KiCad layouts (run under KiCad's bundled Python).

A board script does:

    from pcbkit import Board
    b = Board(pcb_path, layers=4)
    b.place(PLACE, silk_refs=set())          # move footprints, hide/park reference text
    b.reset()                                # wipe generated geometry, save + reload (SWIG quirk)
    b.rules(...); b.outline(...)             # design rules, rounded outline
    b.track(...); b.via(...); b.zone(...)    # routing helpers (also label/dot/bar for silk)
    b.finish(out_path, ...)                  # fill zones, save, downgrade to the KiCad 9 grammar

Coordinates are mm, origin = board top-left, +y down, rotation in degrees (KiCad convention).
Why the odd bits exist:
  * KiCad 10's SWIG wrappers go stale after any Remove(), so removals happen in reset(),
    then the board is saved and reloaded before anything else touches it.
  * atopile 0.15.9 only parses the KiCad 9 file grammar; finish() rewrites the v10 tokens and
    restores the numbered net table.
"""
import json, os, re, shutil, subprocess, tempfile
from pathlib import Path
import pcbnew
from pcbnew import VECTOR2I, FromMM

def mm(v): return FromMM(v)
def pt(x, y): return VECTOR2I(mm(x), mm(y))

LAYER_NAMES = ["F.Cu", "In1.Cu", "In2.Cu", "B.Cu", "Edge.Cuts", "F.SilkS", "B.SilkS",
               "F.Mask", "B.Mask", "F.Fab", "B.Fab", "User.1"]


def save_filled(board, out_path, project_from=None):
    """Save `board` to `out_path` with every zone filled correctly for a file that will be labelled
    KiCad 9 (atopile 0.15.9 only reads that grammar). Returns the reloaded board (keep it alive).

    * Fills come from `kicad-cli pcb drc --refill-zones --save-board`, not pcbnew.ZONE_FILLER: from a
      script the filler runs without the board's clearance rules and stores fills ~0.1 mm (or less)
      from other nets. DRC with --refill-zones hides that, but gerbers are plotted from the stored fill.
    * KiCad 9 stored fills shrunk by half the zone's minimum width and KiCad 10 grows them back by that
      when it opens a pre-10 file, so the fills are stored shrunk. Otherwise every pour comes back
      0.1 mm fatter, into its clearance.
    * The fill runs 10 µm wider than each zone's clearance and the hole clearance: the shrink / regrow
      lands a few µm off at rounded corners and round holes, and the margin absorbs that. The real
      clearances are put back afterwards.
    """
    clear = {z.m_Uuid.AsString(): z.GetLocalClearance() for z in board.Zones()}
    for z in board.Zones():
        z.SetLocalClearance(clear[z.m_Uuid.AsString()] + mm(0.01))
    ds = board.GetDesignSettings()
    hole = ds.m_HoleClearance
    ds.m_HoleClearance = hole + mm(0.01)
    board.Save(str(out_path))
    if project_from is not None and project_from != out_path:      # rules must sit beside the board
        shutil.copy(project_from.with_suffix(".kicad_pro"), out_path.with_suffix(".kicad_pro"))
        shutil.copy(project_from.with_name("fp-lib-table"), out_path.with_name("fp-lib-table"))
    cli = os.environ.get("KICAD_CLI", str(Path.home() / ".local/bin/kicad-cli"))
    with tempfile.TemporaryDirectory() as tmp:
        subprocess.run([cli, "pcb", "drc", "--refill-zones", "--save-board", "-o", f"{tmp}/drc.rpt",
                        str(out_path)], check=True, capture_output=True)
    filled = pcbnew.LoadBoard(str(out_path))
    for z in filled.Zones():
        for layer in z.GetLayerSet().Seq():
            if z.HasFilledPolysForLayer(layer):
                ps = pcbnew.SHAPE_POLY_SET(z.GetFilledPolysList(layer))
                ps.Unfracture()             # stored fills cut a zero-width seam into every hole; shrinking
                ps.Deflate(z.GetMinThickness() // 2, pcbnew.CORNER_STRATEGY_ROUND_ALL_CORNERS, mm(0.002))
                ps.Fracture()               # across one can leave a copper hair touching the hole
                z.SetFilledPolysList(layer, ps)
        z.SetLocalClearance(clear[z.m_Uuid.AsString()])
    filled.GetDesignSettings().m_HoleClearance = hole
    filled.Save(str(out_path))
    for z in board.Zones():
        z.SetLocalClearance(clear[z.m_Uuid.AsString()])
    ds.m_HoleClearance = hole
    return filled


class Board:
    def __init__(self, path, layers=4):
        self.path = path
        self.board = pcbnew.LoadBoard(str(path))
        if self.board is None:
            raise SystemExit(f"pcbnew could not load {path}")
        self.board.SetCopperLayerCount(layers)
        self._refresh()
        self.via_d, self.via_drill = 0.6, 0.3
        self.place_only = False

    def _refresh(self):
        self.fps = {f.GetReference(): f for f in self.board.GetFootprints()}
        self.L = {n: self.board.GetLayerID(n) for n in LAYER_NAMES}

    # ------------------------------------------------------------------ placement
    def place(self, place, silk_refs=(), ref_size=0.8, ref_stroke=0.12, ref_pos=None):
        """Move every footprint. References not in silk_refs go to F.Fab (assembly drawing)."""
        ref_pos = ref_pos or {}
        missing = set(self.fps) - set(place)
        if missing:
            raise SystemExit(f"unplaced footprints: {sorted(missing)}")
        for ref, (x, y, rot) in place.items():
            f = self.fps[ref]
            f.SetPosition(pt(x, y)); f.SetOrientationDegrees(rot)
            for fld in f.GetFields():
                if fld.GetName() == "Reference":
                    on_silk = ref in silk_refs
                    fld.SetVisible(True)
                    fld.SetLayer(self.L["F.SilkS" if on_silk else "F.Fab"])
                    size = ref_size if on_silk else 0.5
                    fld.SetTextSize(VECTOR2I(mm(size), mm(size)))
                    fld.SetTextThickness(mm(ref_stroke if on_silk else 0.08))
                    dx, dy, trot = ref_pos.get(ref, (0.0, 0.0 if not on_silk else -2.0, 0))
                    fld.SetPosition(pt(x + dx, y + dy)); fld.SetTextAngleDegrees(trot)
                    fld.SetKeepUpright(False)
                    fld.SetHorizJustify(pcbnew.GR_TEXT_H_ALIGN_CENTER)
                    fld.SetVertJustify(pcbnew.GR_TEXT_V_ALIGN_CENTER)
                    fld.SetMirrored(False)
                elif fld.GetName() == "Value":
                    fld.SetVisible(False)

    def reset(self, out_path):
        """Delete generated geometry + footprint silk, save to out_path and reload.
        Footprint graphics on User.Comments go too: EasyEDA puts pin-1 circles there and the 3D view
        draws them as grey discs next to the pads."""
        silk = (self.L["F.SilkS"], self.L["B.SilkS"])
        drop = (*silk, self.board.GetLayerID("User.Comments"))
        off = [(f, g) for f in self.fps.values() for g in f.GraphicalItems() if g.GetLayer() in drop]
        drawings = [d for d in self.board.Drawings()
                    if d.GetLayer() in (self.L["Edge.Cuts"], self.L["User.1"], *silk)]
        removed = drawings + list(self.board.GetTracks()) + list(self.board.Zones())
        for item in removed:
            self.board.Remove(item)
        for f, g in off:
            f.Remove(g)
        self.board.Save(str(out_path))
        # Keep every removed wrapper (and the old board) alive until the process exits: if Python
        # frees them, SWIG deletes objects KiCad still references and later wrappers come back as
        # bare SwigPyObjects ("object has no attribute GetFootprints" / "PADS not iterable").
        self._graveyard = getattr(self, "_graveyard", []) + [removed, off, self.board]
        self.board = pcbnew.LoadBoard(str(out_path))
        self._refresh()

    def dump(self):
        for ref in sorted(self.fps):
            for p in self.fps[ref].Pads():
                v = p.GetPosition()
                print(f"{ref:6} {p.GetNumber():6} {p.GetNetname():10} ({v.x/1e6:.3f}, {v.y/1e6:.3f})"
                      f"  size {p.GetSize().x/1e6:.2f}x{p.GetSize().y/1e6:.2f}")

    # ------------------------------------------------------------------ lookups
    def pad(self, ref, num):
        for p in self.fps[ref].Pads():
            if p.GetNumber() == str(num):
                return p
        raise KeyError(f"{ref} pad {num}")

    def P(self, ref, num):
        v = self.pad(ref, num).GetPosition()
        return (round(v.x / 1e6, 3), round(v.y / 1e6, 3))

    def net(self, name):
        n = self.board.FindNet(name)
        if n is None:
            raise KeyError(name)
        return n

    # ------------------------------------------------------------------ rules
    def rules(self, clearance=0.15, track_min=0.15, via=(0.6, 0.3), via_min=(0.45, 0.25),
              edge=0.3, hole=0.25, track=0.25):
        self.via_d, self.via_drill = via
        ds = self.board.GetDesignSettings()
        ds.m_MinClearance = mm(clearance); ds.m_TrackMinWidth = mm(track_min)
        ds.m_ViasMinSize = mm(via_min[0]); ds.m_MinThroughDrill = mm(via_min[1])
        ds.m_CopperEdgeClearance = mm(edge); ds.m_HoleClearance = mm(hole)
        ds.m_SolderMaskMinWidth = mm(0.1)
        nc = ds.m_NetSettings.GetDefaultNetclass()
        nc.SetClearance(mm(clearance)); nc.SetTrackWidth(mm(track))
        nc.SetViaDiameter(mm(via[0])); nc.SetViaDrill(mm(via[1]))

    # ------------------------------------------------------------------ drawing
    def line(self, a, b, layer="Edge.Cuts", w=0.1):
        s = pcbnew.PCB_SHAPE(self.board, pcbnew.SHAPE_T_SEGMENT); s.SetLayer(self.L[layer])
        s.SetStart(pt(*a)); s.SetEnd(pt(*b)); s.SetWidth(mm(w)); self.board.Add(s)

    def arc(self, center, start, end, layer="Edge.Cuts", w=0.1):
        s = pcbnew.PCB_SHAPE(self.board, pcbnew.SHAPE_T_ARC); s.SetLayer(self.L[layer])
        s.SetCenter(pt(*center)); s.SetStart(pt(*start)); s.SetEnd(pt(*end)); s.SetWidth(mm(w))
        self.board.Add(s)

    def rounded_rect(self, x0, y0, x1, y1, r, layer="Edge.Cuts", w=0.1, gaps=()):
        """gaps = [(side, lo, hi)] spans left out of a side ("top"/"right"/"bottom"/"left")"""
        def side(a, b, s):
            spans = sorted((lo, hi) for sd, lo, hi in gaps if sd == s)
            (ax, ay), (bx, by) = a, b
            horiz = ay == by
            lo, hi = (min(ax, bx), max(ax, bx)) if horiz else (min(ay, by), max(ay, by))
            cur = lo
            for g0, g1 in spans:
                if g0 > cur:
                    self.line((cur, ay) if horiz else (ax, cur), (g0, ay) if horiz else (ax, g0), layer, w)
                cur = max(cur, g1)
            if cur < hi:
                self.line((cur, ay) if horiz else (ax, cur), (hi, ay) if horiz else (ax, hi), layer, w)
        side((x0 + r, y0), (x1 - r, y0), "top"); side((x1, y0 + r), (x1, y1 - r), "right")
        side((x1 - r, y1), (x0 + r, y1), "bottom"); side((x0, y1 - r), (x0, y0 + r), "left")
        self.arc((x1 - r, y0 + r), (x1 - r, y0), (x1, y0 + r), layer, w)
        self.arc((x1 - r, y1 - r), (x1, y1 - r), (x1 - r, y1), layer, w)
        self.arc((x0 + r, y1 - r), (x0 + r, y1), (x0, y1 - r), layer, w)
        self.arc((x0 + r, y0 + r), (x0, y0 + r), (x0 + r, y0), layer, w)

    def label(self, text, x, y, size=0.8, layer="F.SilkS", rot=0, bold=False, justify="center"):
        t = pcbnew.PCB_TEXT(self.board); t.SetText(text); t.SetLayer(self.L[layer])
        t.SetPosition(pt(x, y))
        t.SetTextSize(VECTOR2I(mm(size), mm(size)))
        t.SetTextThickness(mm(round(size * (0.2 if bold else 0.15), 3)))
        t.SetTextAngleDegrees(rot); t.SetMirrored(layer.startswith("B."))
        t.SetHorizJustify({"left": pcbnew.GR_TEXT_H_ALIGN_LEFT, "right": pcbnew.GR_TEXT_H_ALIGN_RIGHT}
                          .get(justify, pcbnew.GR_TEXT_H_ALIGN_CENTER))
        self.board.Add(t)

    def dot(self, x, y, d=0.5, layer="F.SilkS"):
        s = pcbnew.PCB_SHAPE(self.board, pcbnew.SHAPE_T_CIRCLE); s.SetLayer(self.L[layer])
        s.SetCenter(pt(x, y)); s.SetEnd(pt(x + d / 2, y)); s.SetWidth(mm(0.1)); s.SetFilled(True)
        self.board.Add(s)

    def bar(self, x, y, length, vertical, layer="F.SilkS", w=0.2):
        if vertical: self.line((x, y - length / 2), (x, y + length / 2), layer, w)
        else: self.line((x - length / 2, y), (x + length / 2, y), layer, w)

    # ------------------------------------------------------------------ copper
    def track(self, netname, pts, layer="F.Cu", width=0.25):
        if self.place_only: return
        for a, b in zip(pts, pts[1:]):
            t = pcbnew.PCB_TRACK(self.board); t.SetLayer(self.L[layer]); t.SetWidth(mm(width))
            t.SetStart(pt(*a)); t.SetEnd(pt(*b)); t.SetNet(self.net(netname)); self.board.Add(t)

    def via(self, netname, xy, d=None, drill=None):
        if self.place_only: return
        v = pcbnew.PCB_VIA(self.board); v.SetPosition(pt(*xy))
        v.SetWidth(mm(d or self.via_d)); v.SetDrill(mm(drill or self.via_drill))
        v.SetLayerPair(self.L["F.Cu"], self.L["B.Cu"]); v.SetNet(self.net(netname)); self.board.Add(v)

    def zone(self, netname, layer, poly, priority=0, thermal=True, clearance=0.2, minw=0.2,
             spoke=0.4, gap=0.3):
        z = pcbnew.ZONE(self.board); z.SetLayer(self.L[layer]); z.SetNet(self.net(netname))
        if len(poly) == 2:
            (x0, y0), (x1, y1) = poly; poly = [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]
        z.Outline().NewOutline()
        for x, y in poly: z.Outline().Append(mm(x), mm(y))
        z.SetAssignedPriority(priority)
        z.SetLocalClearance(mm(clearance)); z.SetMinThickness(mm(minw))
        z.SetPadConnection(pcbnew.ZONE_CONNECTION_THERMAL if thermal else pcbnew.ZONE_CONNECTION_FULL)
        z.SetThermalReliefGap(mm(gap)); z.SetThermalReliefSpokeWidth(mm(spoke))
        z.SetIsFilled(False); self.board.Add(z); return z

    # ------------------------------------------------------------------ output
    def finish(self, out_path, mask="Black", finish=None, project_from=None, severities=None):
        """Save with correct zone fills (save_filled), then patch the file: mask colour, copper finish,
        tented vias, KiCad 10 -> 9 grammar (atopile 0.15.9), net table. Severities go in .kicad_pro."""
        self._graveyard = getattr(self, "_graveyard", []) + [save_filled(self.board, out_path, project_from)]
        s = out_path.read_text()
        s = s.replace('\n\t\t\t\t(color "Black")', '')
        if mask:
            for side, typ in (("F", "Top"), ("B", "Bottom")):
                s = s.replace(f'(layer "{side}.Mask"\n\t\t\t\t(type "{typ} Solder Mask")',
                              f'(layer "{side}.Mask"\n\t\t\t\t(type "{typ} Solder Mask")\n\t\t\t\t(color "{mask}")')
        if finish:
            s = re.sub(r'\(copper_finish "[^"]*"\)', f'(copper_finish "{finish}")', s)
        # vias covered by mask on both sides (cleaner look, KiCad 9 token form)
        s = re.sub(r'\(tenting\s*\(front (yes|no)\)\s*\(back (yes|no)\)\s*\)', "(tenting front back)", s)
        s = re.sub(r'\n\t\t\((covering|plugging)\s*\(front (yes|no)\)\s*\(back (yes|no)\)\s*\)', '', s)
        s = re.sub(r'\n\t\t\((capping|filling) (yes|no)\)', '', s)
        s = s.replace('(version 20260206)', '(version 20241229)', 1) \
             .replace('(generator_version "10.0")', '(generator_version "9.0")', 1)
        nets = {code: n.GetNetname() for code, n in self.board.GetNetInfo().NetsByNetcode().items()}
        table = "".join(f'\n\t(net {code} "{name}")' for code, name in sorted(nets.items()))
        bycode = {name: code for code, name in nets.items()}
        s = re.sub(r'\(net "([^"]*)"\)', lambda m: f'(net {bycode[m.group(1)]} "{m.group(1)}")', s)
        s = re.sub(r'\(zone\n\t\t\(net (\d+) "([^"]*)"\)', r'(zone\n\t\t(net \1)\n\t\t(net_name "\2")', s)
        s = re.sub(r'\n\t\t\(net (\d+) "[^"]*"\)', r'\n\t\t(net \1)', s)
        i = s.index("\n\t(footprint")
        s = s[:i] + table + s[i:]
        out_path.write_text(s)
        pro_path = out_path.with_suffix(".kicad_pro")
        pro = json.loads(pro_path.read_text()) if pro_path.exists() else {}
        sev = pro.setdefault("board", {}).setdefault("design_settings", {}).setdefault("rule_severities", {})
        sev.update(severities or {})
        pro_path.write_text(json.dumps(pro, indent=2) + "\n")
