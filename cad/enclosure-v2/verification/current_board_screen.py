# Maintained check migrated from a frozen candidate; see evidence/check-origins.json.
from pathlib import Path
import sys
PACKAGE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PACKAGE))
from geometry import operations as ops
"""All current component allocations,120 rear vias and actual connector holes.
This is a pure parse/mesh screen, with no native KiCad process.
"""
from pathlib import Path
import sys, importlib.util, json, hashlib, math, numpy as np
H = Path(__file__).resolve().parent
R = H.parent
inputs = {}
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()

def bind(p):
    p = R / p
    inputs[str(p.relative_to(R))] = sha(p)
    return p
sys.path.insert(0, str(R / 'geometry'))
from kicad_sexpr import parse, children, one
bind('geometry/kicad_sexpr.py')
bind(Path(__file__).relative_to(R))
boardpath = bind('data/physical-board.kicad_pcb')
assert sha(boardpath) == '03a6b3dc624e2cf0e83f8cfdd90f64dc52071fb2b8387deb0e22949903981e74'
board = parse(boardpath.read_text())
assert len(children(board, 'footprint')) == 206
s = importlib.util.spec_from_file_location('mesh', bind('geometry/mesh.py'))
m = importlib.util.module_from_spec(s)
s.loader.exec_module(m)
tail = json.loads(bind('verification/current-tail-report.json').read_text())
assert all((sha(R / p) == h for p, h in tail['inputs'].items()))
boxes = {n: np.array(q) for n, q in tail['courtyard_body_boxes'].items()}
assert len(boxes) == 204
meshes = {n: m.stl(bind(p)) for n, p in [('frame', 'exports/motor_frame.stl'), ('front', 'exports/front.stl'), ('rear', 'exports/rear.stl'), ('spacer', 'exports/spacer.stl'), ('guard', 'exports/guard_clamp.stl')]}
for fp in children(board, 'footprint'):
    props = {p[1]: p[2] for p in children(fp, 'property')}
    n = props.get('atopile_address')
    if n not in ['pack_connector.header', 'usb.connector']:
        continue
    at = one(fp, 'at')
    u = float(at[1]) - 100
    v = 175 - float(at[2])
    ang = math.radians(float(at[3]) if len(at) > 3 else 0)
    rot = np.array([[math.cos(ang), -math.sin(ang)], [math.sin(ang), math.cos(ang)]])
    for i, p in enumerate(children(fp, 'pad')):
        if p[2] not in ['thru_hole', 'np_thru_hole']:
            continue
        a = one(p, 'at')
        sz = one(p, 'size')
        uv = rot @ np.array([float(a[1]), -float(a[2])]) + [u, v]
        r = max(float(sz[1]), float(sz[2])) / 2 + 0.25
        boxes[n + '_tail_' + str(i)] = np.array([111.8001, uv[1] - r - 8, uv[0] - r + 8, 113.7, uv[1] + r - 8, uv[0] + r + 8])
rows = []
for n, q in boxes.items():
    for stage in ['installed', 'continuous_minusY8_bench_slide']:
        box = q.copy()
        if stage != 'installed':
            box[1] -= 8
        for mn, t in meshes.items():
            rows.append({'part': n, 'stage': stage, 'obstacle': mn, 'collision': m.mesh_box(t, box)})
vias = []
for i, v in enumerate(children(board, 'via')):
    at = one(v, 'at')
    u = float(at[1]) - 100
    vv = 175 - float(at[2])
    r = float(one(v, 'size')[1]) / 2
    box = np.array([111.799, vv - r - 8, u - r + 8, 111.811, vv + r - 8, u + r + 8])
    vias.append({'index': i, 'uv': [u, vv], 'diameter_mm': 2 * r, 'collision': m.mesh_box(meshes['frame'], box)})
assert len(vias) == 120
assert m.mesh_box(meshes['frame'], np.array([111.799, 7.25, 6.75, 111.811, 7.75, 7.25]))
assert all((sha(R / p) == h for p, h in inputs.items()))
out = {'inputs': inputs, 'component_tail_boxes_xyz': {n: q.tolist() for n, q in boxes.items()}, 'component_checks': rows, 'rear_vias': vias, 'positive_contact_control': True, 'passed': not any((r['collision'] for r in rows + vias)), 'findings': [r for r in rows + vias if r['collision']], 'limits': ['Nine millimetre mounted body extrusions from all204 actual component courtyards, not manufacturer-tolerance proofs', 'Actual connector hole poses with conservative3.5mm terminal/peg projection below component face', 'The two bare motor landing pads are deliberate wire terminations, not component bodies', 'PCB edge guidance, physical hand grip, solder-mask abrasion, frame creep and clamp force remain prototype tests']}
(H / 'current-board-report.json').write_text(json.dumps(out, indent=2) + '\n')
print('checks', len(rows), 'vias', len(vias), 'findings', out['findings'])
