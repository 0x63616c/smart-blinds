# Maintained check migrated from a frozen candidate; see evidence/check-origins.json.
from pathlib import Path
import sys
PACKAGE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PACKAGE))
from geometry import operations as ops
"""Alternative bench latch-tool corridor; exact latch mechanics remain unverified."""
from pathlib import Path
import json, hashlib, importlib.util, numpy as np, ast, math
HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
inputs = {}

def bind(p):
    p = ROOT / p
    inputs[str(p.relative_to(ROOT))] = sha(p)
    return p
s = importlib.util.spec_from_file_location('mesh', bind('geometry/mesh.py'))
m = importlib.util.module_from_spec(s)
s.loader.exec_module(m)
env = {'np': np, 'math': math}
ops.into(['boxdist'], env)
old = json.loads(bind('data/old-front-latch-failure.json').read_text())
actual = json.loads(bind('verification/current-board-report.json').read_text())
boxes = {k: np.array(v) for k, v in actual['component_tail_boxes_xyz'].items()}
tool = np.array([98, -35, 52, 100.8, 80, 55])
rows = []
for name, file in [('front', 'exports/front.stl'), ('rear', 'exports/rear.stl'), ('spacer', 'exports/spacer.stl'), ('frame', 'exports/motor_frame.stl'), ('keeper', 'exports/tail_keeper.stl')]:
    rows.append({'kind': 'actual_mesh', 'name': name, 'collision': m.mesh_box(m.stl(bind(file)), tool)})
for n, b in boxes.items():
    rows.append({'kind': 'component_box', 'name': n, 'collision': m.overlap(b, tool)})
ps = json.loads(bind('data/pack-paths.json').read_text())
au = json.loads(bind('data/pack-path-audit.json').read_text())
for i, case in enumerate(ps):
    for j, pp in enumerate(case):
        r = 1.225 + au['cases'][i]['rows'][j]['curve_chord_error_bound_mm']
        d = min((env['boxdist'](np.array(p), np.array(q), tool) for p, q in zip(pp[:-1], pp[1:]))) - r
        rows.append({'kind': 'pack_wire', 'case': i, 'contact': j + 1, 'clearance_mm': d, 'collision': d <= 0})
rp = json.loads(bind('data/routes.json').read_text())
for n, pp in rp['paths'].items():
    r = rp['audits'][n]['radius_with_assembly_allowance_mm']
    d = min((env['boxdist'](np.array(p), np.array(q), tool) for p, q in zip(pp[:-1], pp[1:]))) - r
    rows.append({'kind': 'ancillary_wire', 'name': n, 'clearance_mm': d, 'collision': d <= 0})
bind(Path(__file__).relative_to(ROOT))
assert all((sha(ROOT / p) == h for p, h in inputs.items()))
report = {'inputs': inputs, 'old_front_tool_failed': old['latch_blade'], 'new_tool_bounds_xyz': tool.tolist(), 'status': 'Unobstructed longitudinal blade corridor only, not proof of latch press direction, force, disengagement stroke or hand usability', 'intended_sequence': 'Cover and ancillary plugs already released; closed joint module on bench. A nonconductive narrow blade approaches along+Y in the right-side channel below the motor tray. Grip the protected plug shell; never pull its wires. Actual contact-tip geometry must follow the exact housing/sample before assembly acceptance.', 'checks': rows, 'passed': not any((r['collision'] for r in rows)), 'findings': [r for r in rows if r['collision']]}
(HERE / 'access-report.json').write_text(json.dumps(report, indent=2) + '\n')
print(json.dumps(report['findings'], indent=2))
