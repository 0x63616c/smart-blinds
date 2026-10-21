# Maintained check migrated from a frozen candidate; see evidence/check-origins.json.
from pathlib import Path
import sys
PACKAGE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PACKAGE))
from geometry import operations as ops
"""Remaining rigid housing/guard motions and accessible screwdriver corridors."""
from pathlib import Path
import ast, sys, importlib.util, json, hashlib, math, numpy as np
H = Path(__file__).resolve().parent
R = H.parent
inputs = {}
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()

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

def load(p):
    t = m.stl(bind(p))
    v, ix = np.unique(t.reshape(-1, 3), axis=0, return_inverse=True)
    q = Manifold(Mesh(v.astype(np.float32), ix.reshape(-1, 3).astype(np.uint32)))
    assert q.status() == Error.NoError
    return (q, t)
solids = {}
tri = {}
for n in ['front', 'rear', 'spacer']:
    solids[n], tri[n] = load('exports/' + n + '.stl')
for n in ['guard_clamp', 'backing', 'motor_frame', 'backplate', 'tail_keeper', 'housing_tie', 'cover']:
    solids[n], tri[n] = load('exports/' + n + '.stl')
for n in ['front', 'rear', 'spacer']:
    env['swept_check'](solids['guard_clamp'], tri['guard_clamp'], [0, 12, 0], solids[n], 'guard_insert_' + n)
env['swept_check'](solids['guard_clamp'], tri['guard_clamp'], [0, 12, 0], solids['backing'].translate([0, -0.35, 0]), 'guard_insert_loosened_backing')
floor = Manifold.cube([13.0502, 40.9002, 1.5502]).translate([93.0499, 64.9999, 63.2999])
q = solids['motor_frame'] - floor
mm = q.to_mesh()
trimmed = np.array(mm.vert_properties)[:, :3][np.array(mm.tri_verts)]
body = np.array([93.15, 79.7, 64.55, 104.95, 149.8, 73.65])
for n in ['front', 'rear', 'spacer', 'guard_clamp', 'backing', 'backplate', 'tail_keeper']:
    hit = m.mesh_box(tri[n], body)
    rows.append({'name': 'motor_body_sweep_' + n, 'bounds': body.tolist(), 'pass': not hit})
rows.append({'name': 'motor_body_sweep_frame_except_seating_floor', 'bounds': body.tolist(), 'pass': not m.mesh_box(trimmed, body)})
old_frame, old_tri = load('data/rejected-motor-frame.stl')
old_floor = Manifold.cube([13.0502, 40.9002, 1.5502]).translate([93.0499, 64.9999, 61.6999])
old_body = Manifold.cube([11.8, 70.1, 9.1]).translate([93.15, 79.7, 62.95])
blocked = old_frame - old_floor ^ old_body
assert blocked.status() == Error.NoError and blocked.volume() > 0.1
enc = [np.array([106.1, 28.125, 57.3, 110.4, 35.875, 73.2]), np.array([106.1, 28.125, 67.3, 110.4, 132.875, 73.2])]
for i, box in enumerate(enc):
    for n in ['front', 'rear', 'spacer', 'guard_clamp', 'backing', 'backplate', 'motor_frame', 'tail_keeper']:
        hit = m.mesh_box(tri[n], box)
        rows.append({'name': f'encoder_body_stage{i}_' + n, 'bounds': box.tolist(), 'pass': not hit})
negative_tie = m.mesh_box(tri['housing_tie'], enc[1])
assert negative_tie, 'Must detect deliberately retained tie-head obstruction'
p = bind('verification/pad_contact.py')
cn = {'np': np, 'math': math}
ops.into(['cylinder_clearance'], cn)
pack = json.loads(bind('data/pack-paths.json').read_text())
for ci, case in enumerate(pack):
    for wi, w in enumerate(case):
        for x in [56.5, 64]:
            d = cn['cylinder_clearance'](np.array(w), x, 108.3, 140, 62.5, 2.0) - 0.3
            rows.append({'name': f'clamp_driver_case{ci}_wire{wi + 1}_x{x}', 'clearance_mm': d, 'pass': d > 0})
assert all((sha(R / p) == h for p, h in inputs.items()))
out = {'inputs': inputs, 'checks': rows, 'passed': all((r['pass'] for r in rows)), 'tie_left_installed_negative_control': negative_tie, 'old_arm_collision_control_mm3': blocked.volume(), 'intentional_floor_mask_margin_mm': 0.0001, 'sequence': ['Cover removed and module OFF/USB disconnected', 'Cut housing tie before any encoder parking; keep motor pair seated on its tray', 'Unplug encoder10mm then park above cassette', 'Unplug motor8mm then park full housing44mm total', 'Remove cassette lock and execute separate exact module extraction', 'Support module on bench before clamp/PCB work'], 'limits': ['Family moving housing box remains a reservation; exact male ears, latch motion and hand use unqualified', 'Each cable path has separate sampled constant-length evidence; rigid box sweep is not cable flex proof', 'Pad force, adjustment and printed strength/creep remain physical gates', 'Tie removed before parking is a real required operation, not omitted in an installed-state claim']}
(H / 'assembly-motion-report.json').write_text(json.dumps(out, indent=2) + '\n')
print('findings', [r['name'] for r in rows if not r['pass']], flush=True)
