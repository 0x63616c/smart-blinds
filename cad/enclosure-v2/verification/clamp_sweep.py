# Maintained check migrated from a frozen candidate; see evidence/check-origins.json.
from pathlib import Path
import sys
PACKAGE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PACKAGE))
from geometry import operations as ops
"""Exact surface-prism sweep versus continuous sampled cable centerlines.
Capsule/chord bounds are conservative; no printed compression/force claim.
"""
from pathlib import Path
import ast, importlib.util, json, hashlib, math, re, numpy as np
H = Path(__file__).resolve().parent
R = H.parent
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
inputs = {}

def bind(p):
    p = R / p
    inputs[str(p.relative_to(R))] = sha(p)
    return p

def functions(p, names, ns):
    ops.into(names, ns)
ns = {'np': np, 'math': math}
functions('geometry/operations.py', ['point_seg', 'point_tri', 'segment_segment', 'seg_tri'], ns)
env = {'np': np, 'math': math, 'ns': ns}
functions('verification/service_screen.py', ['near'], env)
s = importlib.util.spec_from_file_location('mesh', bind('geometry/mesh.py'))
m = importlib.util.module_from_spec(s)
s.loader.exec_module(m)
bind(Path(__file__).relative_to(R))
src = bind('source/definitions.scad').read_text()
assert 'wire_clamp__bolt_z=62.5' in src and 'wire_clamp__adjustment=.1' in src
paths = json.loads(bind('data/pack-paths.json').read_text())
audit = json.loads(bind('data/pack-path-audit.json').read_text())

def surface_sweep(t, vec):
    v = np.array(vec)
    tri = [t, t + v]
    for i, j in [(0, 1), (1, 2), (2, 0)]:
        tri.extend([np.stack([t[:, i], t[:, j], t[:, j] + v], 1), np.stack([t[:, i], t[:, j] + v, t[:, i] + v], 1)])
    out = np.concatenate(tri)
    return out[np.linalg.norm(np.cross(out[:, 1] - out[:, 0], out[:, 2] - out[:, 0]), axis=1) > 1e-10]
rows = []
for n, vec in [('guard_clamp', [0, 12, 0]), ('backing', [0, 0.4, 0])]:
    t = m.stl(bind('exports/' + n + '.stl'))
    if n == 'backing':
        t = t + [0, -0.35, 0]
    sweep = surface_sweep(t, vec)
    for ci, case in enumerate(paths):
        for wi, w in enumerate(case):
            p = np.array(w)
            rad = 0.925 + audit['cases'][ci]['rows'][wi]['curve_chord_error_bound_mm']
            lo = sweep.min((0, 1))
            hi = sweep.max((0, 1))
            assert not np.all((p[0] >= lo) & (p[0] <= hi)) and (not np.all((p[-1] >= lo) & (p[-1] <= hi)))
            d, wit = env['near'](p, rad, sweep)
            rows.append({'part': n, 'translation': vec, 'case': ci, 'wire': wi + 1, 'minimum_clearance_or_3mm_bound': d, 'pass': d > 0, 'witness': wit if d <= 0 else None})
    print(n, 'findings', sum((not q['pass'] for q in rows if q['part'] == n)), flush=True)
t = m.stl(R / 'exports/backing.stl')
a = t[0].mean(0)
d, _ = env['near'](np.array([a - [0, 1, 0], a + [0, 1, 0]]), 0.925, t)
assert d < 0
assert all((sha(R / p) == h for p, h in inputs.items()))
out = {'inputs': inputs, 'method': 'Each original mesh triangle extruded along the whole translation; endpoint and side surfaces retained without a Boolean union. Distance is from all continuous centerline segments to every prism surface, with maximum nominal cable radius plus original arc chord bound. Both full path endpoints must be outside swept bounds. Thus a nonintersecting result covers translation continuously, rather than merely checking sampled poses.', 'checks': rows, 'passed': all((q['pass'] for q in rows)), 'positive_control_clearance': d, 'limits': ['No free-route 0.3mm allowance at intentional compliant pressure seats; this checks max1.85mm nominal insulation geometry', 'Fan contact-row sensitivity is assumed +/-0.5mm, not a vendor tolerance', 'Guard movement assumes loosened clamp and pad not compressed; actual bending, friction, contact row and loading need physical qualification', 'The backing is checked only through its complete0.4mm adjustment/release range; complete removal is by lifting after guard is removed on the empty bench cassette']}
(H / 'clamp-sweep-report.json').write_text(json.dumps(out, indent=2) + '\n')
