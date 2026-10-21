# Maintained check migrated from a frozen candidate; see evidence/check-origins.json.
from pathlib import Path
import sys
PACKAGE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PACKAGE))
from geometry import operations as ops
"""Narrow source-bound checks of explicit line/arc service states. No physical flex claim."""
from pathlib import Path
import ast, hashlib, importlib.util, json, math, numpy as np
H = Path(__file__).resolve().parent
R = H.parent
inputs = {}
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()

def bind(p):
    p = R / p
    inputs[str(p.relative_to(R))] = sha(p)
    return p
src = bind('geometry/operations.py')
ns = {'np': np, 'math': math}
ops.into(['point_seg', 'point_tri', 'segment_segment', 'seg_tri'], ns)
s = importlib.util.spec_from_file_location('mesh', bind('geometry/mesh.py'))
m = importlib.util.module_from_spec(s)
s.loader.exec_module(m)
bind(Path(__file__).relative_to(R))
d = json.loads(bind('data/motor-service.json').read_text())
route = json.loads(bind('data/routes.json').read_text())
meshes = {n: m.stl(bind('exports/' + n + '.stl')) for n in ['drive', 'backplate', 'cover', 'motor_frame']}
port = np.array([3, 145, 20, 8, 161, 36])
drive = meshes['drive']
reserved = np.all((drive >= port[:3] - 1e-05) & (drive <= port[3:] + 1e-05), axis=(1, 2))
meshes['drive_outside_provisional_rear_lead_allocation'] = drive[~reserved]
del meshes['drive']

def near(path, rad, mesh):
    lo = mesh.min(1)
    hi = mesh.max(1)
    best = 3.0
    wit = None
    for i, (p, q) in enumerate(zip(path[:-1], path[1:])):
        ix = np.where(np.all(hi >= np.minimum(p, q) - rad - best, axis=1) & np.all(lo <= np.maximum(p, q) + rad + best, axis=1))[0]
        if not len(ix):
            continue
        ds = ns['seg_tri'](p, q, mesh[ix])
        m0 = math.sqrt(max(0, float(ds.min()))) - rad
        if m0 < best:
            best = m0
            wit = {'segment': i, 'from': p.tolist(), 'to': q.tolist(), 'triangle': mesh[ix[int(ds.argmin())]].tolist()}
    return (best, wit)
rows = []
for ci in range(len(d['cases'])):
    paths = {f'motor{i + 1}': (np.array(q['path']), 1.2262) for i, q in enumerate(d['cases'][ci])}
    paths['encoder'] = (np.array(d['encoder_cases'][ci]['path']), 1.5512)
    for name, (p, r) in paths.items():
        for mn, mesh in meshes.items():
            if mn == 'cover' and ci > 0:
                continue
            dist, wit = near(p, r, mesh)
            rows.append({'state': ci, 'shift_mm': ci * 0.5, 'item': name, 'fixed': mn, 'clearance_or_3mm_lower_bound': dist, 'pass': dist > 0, 'witness': wit if dist <= 0 else None})
    for i, (n, (p, r)) in enumerate(paths.items()):
        for nn, (pp, rr) in list(paths.items())[i + 1:]:
            if n.startswith('motor') and nn.startswith('motor'):
                other = pp
            elif ci == 0:
                other = pp
            else:
                continue
            dist = math.sqrt(min((float(ns['segment_segment'](a, b, other[:-1], other[1:]).min()) for a, b in zip(p[:-1], p[1:])))) - r - rr
            rows.append({'state': ci, 'item': n, 'fixed': nn, 'clearance_or_3mm_lower_bound': dist, 'pass': dist > 0})
    print('state', ci, 'findings', sum((not x['pass'] for x in rows if x['state'] == ci)), flush=True)
assert all((sha(R / p) == h for p, h in inputs.items()))
out = {'inputs': inputs, 'status': 'Sampled explicit constant-length service states; no continuous sweep/physical flexibility qualification. Cover only checked installed. Only the separately declared rear cable allocation surface is excluded, not accepted as owned motor geometry. All original failures are retained under initial-service.', 'checks': rows, 'passed': all((x['pass'] for x in rows)), 'findings': [x for x in rows if not x['pass']]}
(H / 'service-check.json').write_text(json.dumps(out, indent=2) + '\n')
print('findings', len(out['findings']))
