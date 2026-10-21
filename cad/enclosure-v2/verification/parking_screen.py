# Maintained check migrated from a frozen candidate; see evidence/check-origins.json.
from pathlib import Path
import sys
PACKAGE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PACKAGE))
from geometry import operations as ops
"""Narrow sampled service with true fixed cable order. No physical flex qualification."""
from pathlib import Path
import ast, importlib.util, hashlib, json, math, numpy as np
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
ns2 = {'np': np, 'math': math, 'ns': ns}
functions('verification/service_screen.py', ['near'], ns2)
near = ns2['near']
s = importlib.util.spec_from_file_location('mesh', bind('geometry/mesh.py'))
m = importlib.util.module_from_spec(s)
s.loader.exec_module(m)
bind(Path(__file__).relative_to(R))
d = json.loads(bind('data/motor-service.json').read_text())
e = json.loads(bind('data/encoder-parking.json').read_text())
pack = json.loads(bind('data/pack-paths.json').read_text())
meshes = {n: m.stl(bind('exports/' + n + '.stl')) for n in ['drive', 'backplate', 'motor_frame', 'guard_clamp', 'backing']}
for n in ['front', 'rear', 'spacer']:
    meshes[n] = m.stl(bind('exports/' + n + '.stl'))
port = np.array([3, 145, 20, 8, 161, 36])
drive = meshes['drive']
reserved = np.all((drive >= port[:3] - 1e-05) & (drive <= port[3:] + 1e-05), axis=(1, 2))
meshes['drive'] = drive[~reserved]
rows = []

def wires(a, ra, b, rb):
    best = 3.0 + ra + rb
    lo = np.minimum(b[:-1], b[1:])
    hi = np.maximum(b[:-1], b[1:])
    for p, q in zip(a[:-1], a[1:]):
        gap = np.maximum(np.maximum(lo - np.maximum(p, q), np.minimum(p, q) - hi), 0)
        ix = np.where(np.einsum('ij,ij->i', gap, gap) <= best * best)[0]
        if len(ix):
            best = min(best, math.sqrt(max(0, float(ns['segment_segment'](p, q, b[ix], b[ix + 1]).min()))))
    return best - ra - rb
assert wires(np.array([[0.0, 0, 0], [10, 0, 0]]), 1, np.array([[5.0, -5, 0], [5, 5, 0]]), 1) == -2
assert abs(wires(np.array([[0.0, 0, 0], [10, 0, 0]]), 1, np.array([[0.0, 0, 4], [10, 0, 4]]), 1) - 2) < 1e-12
assert abs(wires(np.array([[0.0, 0, 0], [10, 0, 0]]), 1, np.array([[0.0, 0, 10], [10, 0, 10]]), 1) - 3) < 1e-12
states = [('encoder', i, [q], d['cases'][0]) for i, q in enumerate(d['encoder_cases'] + e['cases'])]
states += [('motor', i, q, [e['cases'][-1]]) for i, q in enumerate(d['cases'] + d['motor_parking_cases'])]
for stage, idx, paths, other in states:
    for wi, q in enumerate(paths):
        p = np.array(q['path'])
        r = 1.5512 if stage == 'encoder' else 1.2262
        for name, t in meshes.items():
            dist, wit = near(p, r, t)
            rows.append({'stage': stage, 'state': idx, 'wire': wi, 'obstacle': name, 'clearance_or_3mm_lower_bound': dist, 'pass': dist > 0, 'witness': wit if dist <= 0 else None})
        for j, qq in enumerate(other):
            rr = 1.2262 if stage == 'encoder' else 1.5512
            dist = wires(p, r, np.array(qq['path']), rr)
            rows.append({'stage': stage, 'state': idx, 'wire': wi, 'obstacle': 'other_harness' + str(j), 'clearance_or_3mm_lower_bound': dist, 'pass': dist > 0})
        for ci, case in enumerate(pack):
            for j, pp in enumerate(case):
                dist = wires(p, r, np.array(pp), 1.23)
                rows.append({'stage': stage, 'state': idx, 'wire': wi, 'obstacle': 'pack' + str(j), 'pack_case': ci, 'clearance_or_3mm_lower_bound': dist, 'pass': dist > 0})
    if stage == 'motor':
        dist = wires(np.array(paths[0]['path']), 1.2262, np.array(paths[1]['path']), 1.2262)
        rows.append({'stage': stage, 'state': idx, 'wire': 0, 'obstacle': 'motor_pair', 'clearance_or_3mm_lower_bound': dist, 'pass': dist > 0})
    print(stage, idx, 'findings', sum((not q['pass'] for q in rows if q['stage'] == stage and q['state'] == idx)), flush=True)
assert all((sha(R / p) == h for p, h in inputs.items()))
out = {'inputs': inputs, 'sequence': ['cover removed', 'motor housing tie cut and pair kept on tray', 'encoder unplug and park', 'motor unplug and park', 'rigid module extraction pending separate sweep'], 'checks': rows, 'passed': all((q['pass'] for q in rows)), 'findings': [q for q in rows if not q['pass']], 'limits': ['Sampled states, not continuous motion proof', 'Actual motor rear lead envelope and contact housing still provisional', 'OD/hand access/bending forces/axial pull strength and actual installed cut length unqualified', 'All three assumed pack contact-row sensitivity cases checked; these are not vendor tolerances']}
(H / 'parking-report.json').write_text(json.dumps(out, indent=2) + '\n')
print('findings', len(out['findings']))
