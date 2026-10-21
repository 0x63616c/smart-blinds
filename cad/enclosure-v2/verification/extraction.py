# Maintained check migrated from a frozen candidate; see evidence/check-origins.json.
from pathlib import Path
import sys
PACKAGE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PACKAGE))
from geometry import operations as ops
"""Rigid co-removal after the independently checked cable parking sequence."""
from pathlib import Path
import importlib.util, hashlib, json, sys, numpy as np
H = Path(__file__).resolve().parent
R = H.parent
pass
from manifold3d import Mesh, Manifold, Error
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
inputs = {}

def bind(p):
    p = R / p
    inputs[str(p.relative_to(R))] = sha(p)
    return p
s = importlib.util.spec_from_file_location('mesh', bind('geometry/mesh.py'))
m = importlib.util.module_from_spec(s)
s.loader.exec_module(m)
bind(Path(__file__).relative_to(R))
import manifold3d
None

def mesh(p):
    t = m.stl(bind(p))
    v, ix = np.unique(t.reshape(-1, 3), axis=0, return_inverse=True)
    q = Manifold(Mesh(v.astype(np.float32), ix.reshape(-1, 3).astype(np.uint32)))
    assert q.status() == Error.NoError
    return (q, t)
B, bt = mesh('exports/backplate.stl')
B = B - Manifold.cube([200, 300, 3.001]).translate([-20, -30, 0])
rows = []

def check(a, b, name):
    q = a ^ b
    assert q.status() == Error.NoError
    rows.append({'name': name, 'volume_mm3': q.volume(), 'empty': q.is_empty(), 'bounds': q.bounding_box(), 'pass': q.is_empty()})
    print(name, q.volume(), flush=True)
heads = []
for x, y in [(45, 103), (109, 107.5), (45, 177)]:
    q = Manifold.cylinder(5, 5, 5, 48).translate([x, y - 2, 3]) + Manifold.cylinder(5, 5, 5, 48).translate([x, y + 2, 3]) + Manifold.cube([10, 4, 5]).translate([x - 5, y - 2, 3])
    heads.append(q)
heads = Manifold.batch_boolean(heads, __import__('manifold3d').OpType.Add)

def swept_check(q, tri, vec, obstacle, name):
    vec = np.array(vec)
    parts = obstacle.decompose()
    bbs = [np.array(p.bounding_box()) for p in parts]
    hits = []
    count = 0
    for idx, p in enumerate(parts):
        for pose in [np.zeros(3), vec]:
            it = q.translate(pose) ^ p
            assert it.status() == Error.NoError
            if not it.is_empty():
                hits.append({'endpoint': pose.tolist(), 'volume_mm3': it.volume(), 'bounds': it.bounding_box()})
    for i, t in enumerate(tri):
        if abs(np.cross(t[1] - t[0], t[2] - t[0]) @ vec) < 1e-10:
            continue
        pts = np.vstack([t, t + vec])
        lo = pts.min(0)
        hi = pts.max(0)
        candidates = [j for j, b in enumerate(bbs) if np.all(hi >= b[:3]) and np.all(lo <= b[3:])]
        if not candidates:
            continue
        prism = Manifold.hull_points(pts)
        assert prism.status() == Error.NoError
        count += 1
        for j in candidates:
            it = prism ^ parts[j]
            assert it.status() == Error.NoError
            if not it.is_empty():
                hits.append({'triangle': i, 'volume_mm3': it.volume(), 'bounds': it.bounding_box()})
    rows.append({'name': name, 'extruded_surface_prisms': count, 'findings': hits, 'pass': not hits})
    print(name, count, 'findings', len(hits), flush=True)
for name, p in [('rear', 'exports/rear.stl'), ('frame', 'exports/motor_frame.stl')]:
    q, t = mesh(p)
    for label, pose, vec in [('slide', [0, 0, 0], [0, 2.5, 0]), ('lift', [0, 2.5, 0], [0, 0, 72])]:
        moving = q.translate(pose)
        tri = t + pose
        for on, ob in [('backplate', B), ('wall_head', heads)]:
            swept_check(moving, tri, vec, ob, name + '_' + label + '_' + on)
rear, _ = mesh('exports/rear.stl')
w = rear.translate([0, 0, 1]) ^ B
assert w.status() == Error.NoError and w.volume() > 1
pack = json.loads(bind('data/pack-paths.json').read_text())
pr = json.loads(bind('data/motor-service.json').read_text())
en = json.loads(bind('data/encoder-parking.json').read_text())
rigid = []
for name, p in [('front', 'exports/front.stl'), ('spacer', 'exports/spacer.stl')] + [(n, 'exports/' + n + '.stl') for n in ['guard_clamp', 'backing', 'tail_keeper', 'motor_frame']]:
    t = m.stl(bind(p))
    rigid.append({'name': name, 'max_y_after_slide': float(t[:, :, 1].max()) + 2.5})
rigid.append({'name': 'retained_pack_fan_all_three_cases', 'max_y_after_slide': max((v[1] for c in pack for w in c for v in w)) + 1.23 + 2.5})
v16 = json.loads(bind('verification/current-board-report.json').read_text())
rigid.append({'name': 'PCB_and_current_component_allocation', 'max_y_after_slide': max(72.0, max((q[4] for q in v16['component_tail_boxes_xyz'].values()))) + 2.5, 'status': 'Conservative component allocation boxes; not a complete vendor-tolerance model'})
for n in ['contents', 'pack_fasteners', 'service_hardware', 'inline_body']:
    t = m.stl(bind('exports/' + n + '.stl'))
    rigid.append({'name': n, 'max_y_after_slide': float(t[:, :, 1].max()) + 2.5})
rigid.append({'name': 'guard_M3_fastener_conservative', 'max_y_after_slide': 115.2 + 3 + 2.5})
maxy = max((q['max_y_after_slide'] for q in rigid))
motor = np.vstack([q['path'] for q in pr['motor_parking_cases'][-1]])
enc = np.array(en['cases'][-1]['path'])
drive = m.stl(bind('exports/drive.stl'))
sep = {'drive_actual_min_y': float(drive[:, :, 1].min()), 'motor_parked_wire_min_y': float(motor[:, 1].min()) - 1.2262, 'encoder_parked_wire_min_y': float(enc[:, 1].min()) - 1.5512, 'motor_whole_family_housing_min_y': 124 - 0.3, 'encoder_receptacle_min_y': en['parked_receptacle_box'][1]}
for n, v in sep.items():
    rows.append({'name': 'forward_separation_' + n, 'moving_max_y': maxy, 'fixed_min_y': v, 'clearance_mm': v - maxy, 'pass': v > maxy})
assert all((sha(R / p) == h for p, h in inputs.items()))
out = {'inputs': inputs, 'library': 'manifold3d3.3.2', 'motion': [[0, 2.5, 0], [0, 0, 72]], 'checks': rows, 'coverage': rigid, 'positive_capture_control_volume_mm3': w.volume(), 'passed': all((q['pass'] for q in rows)), 'limits': ['Exact triangular-prism boundary extrusion plus endpoint solids covers rigid translations; actual flexible parking is a sampled family, not continuous manual-motion proof', 'FlatZ3 seating face intentionally omitted; cleats and all other backplate obstacles retained', 'Actual screw stack, connector variant, motor dimensions, hand support and print tolerances still require qualification', 'All raw cell links stay inside the screwed cassette throughout this removal']}
(H / 'extraction-report.json').write_text(json.dumps(out, indent=2) + '\n')
