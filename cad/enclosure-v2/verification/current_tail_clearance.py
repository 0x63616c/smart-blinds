# Maintained check migrated from a frozen candidate; see evidence/check-origins.json.
from pathlib import Path
import sys
PACKAGE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PACKAGE))
from geometry import operations as ops
"""Full retained-tail screen, including source button parts and actual PCB courtyards.
Fixed clamp-seat contact is explicitly separated from free wire runs.
"""
from pathlib import Path
import ast, json, hashlib, math, importlib.util, sys, numpy as np
H = Path(__file__).resolve().parent
R = H.parent
inputs = {}
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()

def bind(p):
    p = R / p
    inputs[str(p.relative_to(R))] = sha(p)
    return p

def funcs(p, names, env):
    ops.into(names, env)
ns = {'np': np, 'math': math}
funcs('geometry/operations.py', ['point_seg', 'point_tri', 'segment_segment', 'seg_tri'], ns)
e = {'np': np, 'math': math, 'ns': ns}
funcs('verification/service_screen.py', ['near'], e)
funcs('geometry/operations.py', ['boxdist'], e)
s = importlib.util.spec_from_file_location('m', bind('geometry/mesh.py'))
m = importlib.util.module_from_spec(s)
s.loader.exec_module(m)
bind(Path(__file__).relative_to(R))
d = json.loads(bind('data/routes.json').read_text())
paths = {n: np.array(d['paths'][n]) for n in ['motor1', 'motor2']}
rows = []
sys.path.insert(0, str(R / 'geometry'))
from kicad_sexpr import parse, children, one
bind('geometry/kicad_sexpr.py')
board = parse(bind('data/physical-board.kicad_pcb').read_text())
courts = {}
for fp in children(board, 'footprint'):
    props = {p[1]: p[2] for p in children(fp, 'property')}
    name = props.get('atopile_address', '')
    at = one(fp, 'at')
    u = float(at[1]) - 100
    v = 175 - float(at[2])
    angle = math.radians(float(at[3]) if len(at) > 3 else 0)
    pts = []
    if name in ['motor_output.landing1', 'motor_output.landing2']:
        continue
    for q in fp:
        if not isinstance(q, list) or q[0] not in ['fp_line', 'fp_rect', 'fp_circle', 'fp_arc', 'fp_poly']:
            continue
        layer = next(iter(children(q, 'layer')), None)
        if layer is None or layer[1] != 'F.CrtYd':
            continue
        for key in ['start', 'end', 'mid', 'center']:
            a = next(iter(children(q, key)), None)
            if a:
                pts.append([float(a[1]), -float(a[2])])
        pp = next(iter(children(q, 'pts')), None)
        if pp:
            pts.extend([[float(a[1]), -float(a[2])] for a in pp[1:] if a[0] == 'xy'])
        if q[0] == 'fp_circle':
            c = np.array([float(one(q, 'center')[1]), -float(one(q, 'center')[2])])
            end = np.array([float(one(q, 'end')[1]), -float(one(q, 'end')[2])])
            rr = np.linalg.norm(end - c)
            pts.extend(((c + np.array([sx, sy]) * rr).tolist() for sx in [-1, 1] for sy in [-1, 1]))
        if q[0] == 'fp_arc':
            raise AssertionError(('new courtyard arc needs explicit extrema', name))
    assert pts, ('missing courtyard', name)
    a = np.array(pts)
    rot = np.array([[math.cos(angle), -math.sin(angle)], [math.sin(angle), math.cos(angle)]])
    uv = a @ rot.T + [u, v]
    lo = uv.min(0)
    hi = uv.max(0)
    box = np.array([101.2, lo[1] - 8, lo[0] + 8, 110.2, hi[1] - 8, hi[0] + 8])
    courts[name] = box
for n, p in paths.items():
    for name, box in courts.items():
        dist = min((e['boxdist'](a, b, box) for a, b in zip(p[:-1], p[1:]))) - 1.2262
        rows.append({'wire': n, 'obstacle': '9mm_' + name, 'clearance_mm': dist, 'pass': dist > 0})
if '--courts-only' not in sys.argv:
    meshes = {n: m.stl(bind('exports/' + n + '.stl')) for n in ['cover', 'guide_bar', 'motor_frame', 'backing', 'guard_clamp']}
    pl = m.stl(bind('exports/button.stl'))
    for y in [22, 42]:
        meshes['button_plunger_' + str(y)] = pl + [109.4, y, 0]
    for n in ['front', 'rear', 'spacer']:
        meshes[n] = m.stl(bind('exports/' + n + '.stl'))
    for n, p in paths.items():
        for name, mesh in meshes.items():
            pp = [p[p[:, 1] <= 63.5], p[p[:, 1] >= 72.5]] if name == 'motor_frame' else [p]
            ds = [e['near'](a, 1.2262, mesh)[0] for a in pp if len(a) > 1]
            dist = min(ds)
            rows.append({'wire': n, 'obstacle': name, 'clearance_or_3mm_lower_bound': dist, 'pass': dist > 0})
if '--courts-only' not in sys.argv:
    fan = json.loads(bind('data/pack-paths.json').read_text())
    for ci, case in enumerate(fan):
        for wi, w in enumerate(case):
            dist, wit = e['near'](np.array(w), 1.23, meshes['motor_frame'])
            rows.append({'wire': 'pack' + str(wi + 1), 'pack_case': ci, 'obstacle': 'complete_motor_frame', 'clearance_or_3mm_lower_bound': dist, 'pass': dist > 0})
assert all((sha(R / p) == h for p, h in inputs.items()))
out = {'inputs': inputs, 'courtyard_body_boxes': {n: b.tolist() for n, b in courts.items()}, 'checks': rows, 'passed': all((q['pass'] for q in rows)), 'findings': [q for q in rows if not q['pass']], 'limits': ['Full actual component courtyard bounds with9mm mounted-height allocation; drawing/tolerance and solder formation remain unqualified', 'Only two intended bare motor solder lands excluded from component-volume check', 'Retained-tail frame contact at its intentional keeper/seat interval is separately represented by groove and soft pad geometry', 'No axial pull force or elastic cable/print acceptance']}
(H / 'current-tail-report.json').write_text(json.dumps(out, indent=2) + '\n')
print('checks', len(rows), 'findings', out['findings'])
