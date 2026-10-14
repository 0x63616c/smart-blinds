"""Routing style checks that DRC does not do (run under KiCad's bundled Python).

    python3 scripts/check_layout.py layouts/<board>/<board>.kicad_pcb

Fails (exit 1) on:
  * a track segment that is not a multiple of 45 degrees
  * a track that meets a pad centre on a diagonal (it must leave / enter along the pad axis)
  * top copper under a part body: a via anywhere under it, or a track under it that is not just
    entering that part's own pad (that may cross the body overhang, up to OVERHANG mm)
Part bodies come from the footprint or 3D model name (EasyEDA style ..._L<len>-W<wid>..., L along the
pad-to-pad axis);
parts whose name carries no size (connectors) are skipped.
"""
import math, re, sys
import pcbnew

OVERHANG = 0.6          # body overhang a track may cross on its way into the part's own pad
b = pcbnew.LoadBoard(sys.argv[1])
mm = pcbnew.ToMM
pads = [p for f in b.GetFootprints() for p in f.Pads()]
problems = []


def body(fp):
    """(half-length, half-width, to_local) of the part body, or None."""
    m = re.search(r"L(\d+(?:\.\d+)?)-W(\d+(?:\.\d+)?)", " ".join([fp.GetFPIDAsString()] + [x.m_Filename for x in fp.Models()]))
    if not m or fp.GetReference().startswith("H"):
        return None
    pos, a = fp.GetPosition(), math.radians(fp.GetOrientationDegrees())

    def local(x, y):
        dx, dy = x - mm(pos.x), y - mm(pos.y)
        return dx * math.cos(a) - dy * math.sin(a), dx * math.sin(a) + dy * math.cos(a)
    L, W = float(m[1]), float(m[2])
    pl = [local(mm(p.GetPosition().x), mm(p.GetPosition().y)) for p in fp.Pads()]
    sx = max(p[0] for p in pl) - min(p[0] for p in pl)
    sy = max(p[1] for p in pl) - min(p[1] for p in pl)
    if len(pl) > 4 and fp.GetOrientationDegrees() % 180 and "SO" in fp.GetFPIDAsString().upper():
        sx, sy = sy, sx                        # gull-wing IC: the pin rows run along L
    bx, by = (L, W) if sx >= sy else (W, L)
    if len(pl) > 4:                            # ICs: L is the body, leads stick out across it
        bx, by = (min(L, W), max(L, W)) if sx >= sy else (max(L, W), min(L, W))
    return bx / 2, by / 2, local


parts = [(fp, body(fp)) for fp in b.GetFootprints()]
parts = [(fp, bd) for fp, bd in parts if bd]


def in_own_pad(fp, x, y):
    p = pcbnew.VECTOR2I(pcbnew.FromMM(x), pcbnew.FromMM(y))
    return any(q.HitTest(p) for q in fp.Pads())


n = 0
for t in b.GetTracks():
    s, e = t.GetStart(), t.GetEnd()
    x0, y0, x1, y1 = mm(s.x), mm(s.y), mm(e.x), mm(e.y)
    where = f"{t.GetNetname()} {b.GetLayerName(t.GetLayer())} ({x0:.2f},{y0:.2f})->({x1:.2f},{y1:.2f})"
    is_via = t.Type() == pcbnew.PCB_VIA_T
    if not is_via:
        n += 1
        ang = math.degrees(math.atan2(y1 - y0, x1 - x0))
        if min(ang % 45, 45 - ang % 45) > 0.5:
            problems.append(f"odd angle: {where}")
        for q in (s, e):
            for p in pads:
                if p.GetPosition() == q and p.IsOnLayer(t.GetLayer()) and min(ang % 90, 90 - ang % 90) > 0.5:
                    problems.append(f"diagonal pad entry {p.GetParentFootprint().GetReference()}.{p.GetNumber()}: {where}")
    if not is_via and t.GetLayer() != pcbnew.F_Cu:
        continue
    L = math.hypot(x1 - x0, y1 - y0)
    k = max(1, int(L / 0.02))
    for fp, (hx, hy, local) in parts:
        under = 0
        for i in range(k + 1):
            x, y = x0 + (x1 - x0) * i / k, y0 + (y1 - y0) * i / k
            u, v = local(x, y)
            if abs(u) < hx and abs(v) < hy and not in_own_pad(fp, x, y):
                under += 1
        if not under:
            continue
        ref = fp.GetReference()
        if is_via:
            problems.append(f"via under {ref}: {where}")
            continue
        length = L * under / k
        own = in_own_pad(fp, x0, y0) or in_own_pad(fp, x1, y1)
        if length > (OVERHANG if own else 0.02):
            problems.append(f"track under {ref} ({length:.2f} mm{', into its own pad' if own else ''}): {where}")

for p in problems:
    print(p)
print(f"{n} segments, {len(parts)} part bodies, {len(problems)} problems")
sys.exit(1 if problems else 0)
