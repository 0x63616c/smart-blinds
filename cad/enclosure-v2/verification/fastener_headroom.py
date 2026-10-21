# Maintained check migrated from a frozen candidate; see evidence/check-origins.json.
from pathlib import Path
import sys
PACKAGE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PACKAGE))
from geometry import operations as ops
"""Conservative source-mesh tool corridors and published nominal headroom."""
from pathlib import Path
import importlib.util, json, hashlib, numpy as np
H = Path(__file__).resolve().parent
R = H.parent
inputs = {}
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()

def bind(p):
    p = R / p
    inputs[str(p.relative_to(R))] = sha(p)
    return p
s = importlib.util.spec_from_file_location('m', bind('geometry/mesh.py'))
m = importlib.util.module_from_spec(s)
s.loader.exec_module(m)
bind(Path(__file__).relative_to(R))
bind('source/definitions.scad')
bind('source/definitions.scad')
bind('source/definitions.scad')
meshes = {n: m.stl(bind('exports/' + n + '.stl')) for n in ['backplate', 'cover', 'drive', 'motor_frame', 'inline_body', 'housing_tie', 'tail_keeper', 'guard_clamp', 'backing']}
rows = []
for x, y in [(45, 103), (109, 107.5), (45, 177)]:
    box = np.array([x - 3, y - 5, 8.4, x + 3, y + 5, 100])
    for n in ['backplate', 'drive']:
        rows.append({'name': f'wall_driver_{x}_{y}_{n}', 'box': box.tolist(), 'pass': not m.mesh_box(meshes[n], box)})
box = np.array([27, 113, 10, 33, 119, 100])
for n in ['motor_frame', 'guard_clamp', 'backing', 'drive']:
    rows.append({'name': 'lock_driver_' + n, 'box': box.tolist(), 'pass': not m.mesh_box(meshes[n], box)})
for x, y in [(12, 131), (106, 131), (12, 177), (106, 177)]:
    box = np.array([x - 1.8, y - 1.8, 71.01, x + 1.8, y + 1.8, 90])
    rows.append({'name': f'cover_driver_{x}_{y}', 'pass': not m.mesh_box(meshes['cover'], box), 'box': box.tolist()})
bounds = {n: np.r_[t.min((0, 1)), t.max((0, 1))].tolist() for n, t in meshes.items()}
body = np.array(bounds['inline_body'])
tie = np.array(bounds['housing_tie'])
nominal = {'housing_bottom_above_arm_mm': body[2] - 64.3, 'remaining_after_0p3_housing_allowance_mm': body[2] - 64.3 - 0.3, 'housing_to_normal_roof_mm': 74.6 - body[5], 'remaining_to_roof_after_0p3_mm': 74.6 - body[5] - 0.3, 'tie_to_recessed_roof_mm': 75.05 - tie[5], 'roof_section_above_tie_relief_mm': 77 - 75.05, 'frame_face_remaining_mm': 2.4, 'tray_side_wing_pack_clearance_basis': 'Complete current frame checked against all3 fan cases in current-tail-report.json'}
assert all((sha(R / p) == h for p, h in inputs.items()))
out = {'inputs': inputs, 'checks': rows, 'bounds': bounds, 'nominal_clearances': nominal, 'passed': all((q['pass'] for q in rows)), 'findings': [q for q in rows if not q['pass']], 'limits': ['Conservative tool-shaft boxes only; hand, exact bit/tip and torque usability remain unqualified', 'Housing floor is intended seating; full-envelope sweep tested separately with0.3mm expansion', 'Arm/tray bonding area,2.4mm recessed rails and new comb web are geometry, not strength/creep certification', 'No inferred maximum allowable printed load or battery-clamp pull force']}
(H / 'fastener-headroom-report.json').write_text(json.dumps(out, indent=2) + '\n')
print(out['passed'], out['findings'], nominal)
