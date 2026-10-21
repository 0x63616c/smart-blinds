# Maintained check migrated from a frozen candidate; see evidence/check-origins.json.
from pathlib import Path
import sys
PACKAGE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PACKAGE))
from geometry import operations as ops
"""Complete remaining rigid coverage for the accepted release/lift sequence."""
from pathlib import Path
import ast, sys, hashlib, json, importlib.util, numpy as np
H = Path(__file__).resolve().parent
R = H.parent
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
inputs = {}

def bind(p):
    p = R / p
    inputs[str(p.relative_to(R))] = sha(p)
    return p
pass
import manifold3d
from manifold3d import Mesh, Manifold, Error
None
bind(Path(__file__).relative_to(R))
s = importlib.util.spec_from_file_location('meshlib', bind('geometry/mesh.py'))
m = importlib.util.module_from_spec(s)
s.loader.exec_module(m)
rows = []
env = {'np': np, 'Manifold': Manifold, 'Error': Error, 'rows': rows}
ops.into(['swept_check'], env)
old = json.loads(bind('verification/extraction-report.json').read_text())
assert old['passed']
assert all((sha(R / p) == v for p, v in old['inputs'].items()))

def load(p):
    t = m.stl(bind(p))
    v, ix = np.unique(t.reshape(-1, 3), axis=0, return_inverse=True)
    q = Manifold(Mesh(v.astype(np.float32), ix.reshape(-1, 3).astype(np.uint32)))
    assert q.status() == Error.NoError
    return (q, t)
B, _ = load('exports/backplate.stl')
B = B - Manifold.cube([200, 300, 3.001]).translate([-20, -30, 0])
heads = []
for x, y in [(45, 103), (109, 107.5), (45, 177)]:
    heads.extend([Manifold.cylinder(5, 5, 5, 48).translate([x, y - 2, 3]), Manifold.cylinder(5, 5, 5, 48).translate([x, y + 2, 3]), Manifold.cube([10, 4, 5]).translate([x - 5, y - 2, 3])])
heads = Manifold.batch_boolean(heads, manifold3d.OpType.Add)
for n, p in [(n, 'exports/' + n + '.stl') for n in ['front', 'spacer']] + [(n, 'exports/' + n + '.stl') for n in ['guard_clamp', 'backing', 'tail_keeper', 'contents', 'pack_fasteners', 'inline_body']]:
    q, tri = load(p)
    for label, pose, vec in [('slide', [0, 0, 0], [0, 2.5, 0]), ('lift', [0, 2.5, 0], [0, 0, 72])]:
        for on, ob in [('backplate', B), ('wall_head', heads)]:
            env['swept_check'](q.translate(pose), tri + pose, vec, ob, n + '_' + label + '_' + on)
for p in ['source/definitions.scad', 'source/definitions.scad', 'source/definitions.scad']:
    bind(p)
v16 = json.loads(bind('verification/current-board-report.json').read_text())
arr = np.array(list(v16['component_tail_boxes_xyz'].values()))
boxes = {'current_reviewed_component_tail_allocation': np.r_[arr[:, :3].min(0), arr[:, 3:].max(0)], 'PCB_body': [110.2, -8, 8, 111.8, 72, 62], 'clamp_fasteners': [53.5, 98.3, 60.19, 67, 108.3, 64.81], 'tail_keeper_fasteners': [93.1, 66.1, 63.6, 105.1, 69.9, 73.2], 'lower_clip_fastener': [106.5, -3.31, 4.29, 114.6, 1.31, 8.91], 'upper_clip_fastener': [106.5, 65.69, 62.09, 114.6, 70.31, 66.71], 'guard_fastener': [39, 112.2, 40, 45, 118.2, 54]}
fan = json.loads(bind('data/pack-paths.json').read_text())
a = np.array([p for c in fan for w in c for p in w])
boxes['all_three_pack_fans'] = np.r_[a.min(0) - 1.23, a.max(0) + 1.23]
routes = json.loads(bind('data/routes.json').read_text())
a = np.vstack([routes['paths']['motor1'], routes['paths']['motor2']])
boxes['retained_controller_motor_tails'] = np.r_[a.min(0) - 1.23, a.max(0) + 1.23]
for n, box in boxes.items():
    box = np.array(box)
    q = Manifold.cube(box[3:] - box[:3]).translate(box[:3])
    v = q.to_mesh()
    tri = np.array(v.vert_properties)[:, :3][np.array(v.tri_verts)]
    for label, pose, vec in [('slide', [0, 0, 0], [0, 2.5, 0]), ('lift', [0, 2.5, 0], [0, 0, 72])]:
        for on, ob in [('backplate', B), ('wall_head', heads)]:
            env['swept_check'](q.translate(pose), tri + pose, vec, ob, n + '_' + label + '_' + on)
assert all((sha(R / p) == v for p, v in inputs.items()))
out = {'inputs': inputs, 'retained_prior_checks': len(old['checks']), 'additional_checks': rows, 'declaration_boxes': {k: np.array(v).tolist() for k, v in boxes.items()}, 'passed': all((r['pass'] for r in rows)), 'limits': ['Actual source mesh or declared conservative drawing/hardware allocations; vendor variants and print tolerances remain unqualified', 'Initial Z3 wall-plate seating plane intentionally removed as in the base release check', 'Flexible cable parking is sampled separately; no strength, pressure, motor fit or hand-usability acceptance']}
(H / 'complete-extraction-report.json').write_text(json.dumps(out, indent=2) + '\n')
print('findings', [q['name'] for q in rows if not q['pass']])
