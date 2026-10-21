# Maintained check migrated from a frozen candidate; see evidence/check-origins.json.
from pathlib import Path
import sys
PACKAGE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PACKAGE))
from geometry import operations as ops
from pathlib import Path
import runpy, json, numpy as np
H = Path(__file__).resolve().parent
R = H.parent
e = runpy.run_path(str(H / 'button_sequence.py'))
globals().update({k: v for k, v in e.items() if not k.startswith('__')})
bind('verification/button_integration.py')

def load(p):
    t = m.stl(bind(p))
    v, i = np.unique(t.reshape(-1, 3), axis=0, return_inverse=True)
    q = Manifold(Mesh(v.astype(np.float32), i.reshape(-1, 3).astype(np.uint32)))
    assert q.status() == Error.NoError
    return (q, t)
solid = {}
for n in ['motor_frame', 'backing', 'guard_clamp', 'tail_keeper', 'inline_body', 'housing_tie']:
    solid[n] = load('exports/' + n + '.stl')[0]
for n in ['front', 'rear', 'spacer']:
    solid[n] = load('exports/' + n + '.stl')[0]
d = json.loads(bind('verification/current-board-report.json').read_text())
for p, h in d['inputs'].items():
    assert sha(R / p) == h
    inputs[p] = h
boxes = d['component_tail_boxes_xyz']
q = []
for name, b in boxes.items():
    lo = np.array(b[:3])
    hi = np.array(b[3:])
    q.append(Manifold.cube(hi - lo).translate(lo))
q.append(Manifold.cube([1.6, 80, 54]).translate([110.2, -8, 8]))
solid['board_allocations'] = Manifold.batch_boolean(q, OpType.Add)
for n, ob in solid.items():
    chk(bar, ob, 'bar_' + n)
    for y in [22, 42]:
        chk(button.translate([109.4, y, 0]), ob, 'button_' + str(y) + '_' + n)
ob = Manifold.batch_boolean(list(solid.values()), OpType.Add)
for n, q, t in [('bar', bar, bt)] + [('button' + str(y), button.translate([109.4, y, 0]), pt + [109.4, y, 0]) for y in [22, 42]]:
    swept_check(q, t, [0, 0, 35], ob, n + '_cover_remove')
vs = []
for z in [67.1, 69.9]:
    for a in np.arange(6) * np.pi / 3 + np.pi / 6:
        vs.append([4 / np.sqrt(3) * np.cos(a), 4 / np.sqrt(3) * np.sin(a), z])
nut = Manifold.hull_points(vs)
nt = np.asarray(nut.to_mesh().vert_properties)[:, :3][np.asarray(nut.to_mesh().tri_verts)]
swept_check(nut.translate([0, -8, 0]), nt + [0, -8, 0], [0, 8, 0], button, 'nut_side_insert')
for angle in [20, 30]:
    it = nut.rotate([0, 0, angle]) ^ button
    rows.append({'name': 'nut_rotation_witness_' + str(angle), 'volume_mm3': it.volume(), 'pass': it.volume() > 0})
released = sum([button.translate([109.4, y, 0]) for y in [22, 42]], Manifold())
for n, start, vec in [('rear', [0, 8.5, -16], [0, 0, 15.8]), ('slide', [0, 8.5, -0.2], [0, -8.5, 0]), ('seat', [0, 0, -0.2], [0, 0, 0.2])]:
    swept_check(bar.translate(start), bt + start, vec, cover + released, 'bar_released_' + n)
nest, nt = mesh('nest')
chk(nest, cover, 'nest_cover')
for y in [22, 42]:
    raw = nest ^ button.translate([109.4, y, -0.4])
    contact_slab = Manifold.cube([13, 13, 0.0002]).translate([102.9, y - 6.5, 78.3999])
    it = nest - contact_slab ^ button.translate([109.4, y, -0.4])
    rows.append({'name': 'nest_pressed_' + str(y), 'raw_nominal_contact_volume_mm3': raw.volume(), 'contact_plane_z': 78.4, 'float32_contact_slab_half_thickness': 0.0001, 'masked_volume_mm3': it.volume(), 'pass': it.is_empty()})
    witness = nest - contact_slab ^ button.translate([109.4, y, -0.3])
    rows.append({'name': 'nest_0_1mm_interference_control_' + str(y), 'volume_mm3': witness.volume(), 'pass': witness.volume() > 5})
for y in [22, 42]:
    q = nest ^ button.translate([109.4, y, 0])
    rows.append({'name': 'nest_positive_press_' + str(y), 'volume_mm3': q.volume(), 'pass': q.volume() > 1})
import math, ast
ns = {'np': np, 'math': math}
ops.into(['point_seg', 'point_tri', 'segment_segment', 'seg_tri'], ns)
ne = {'np': np, 'math': math, 'ns': ns}
ops.into(['near'], ne)
routes = json.loads(bind('data/routes.json').read_text())
for n, path in routes['paths'].items():
    radius = routes['audits'][n]['radius_with_assembly_allowance_mm'] + 0.0012
    for name, tri in [('bar', bt), ('cover', ct)] + [('button' + str(y), pt + [109.4, y, 0]) for y in [22, 42]]:
        dist, witness = ne['near'](np.array(path), radius, tri)
        rows.append({'name': n + '_' + name + '_wire', 'clearance_or_3mm_lower_bound': dist, 'pass': dist > 0})
head = Manifold.cylinder(2.5, 1.9, 1.9, 48).translate([0, 0, 70.25])
chk(head, button, 'full_adjustment_head_range')
rows.append({'name': 'head_to_loaded_nut_gap', 'minimum_mm': 70.25 - 69.9, 'pass': 70.25 > 69.9})
new_volume = mesh('cover')[0].volume() + bar.volume() + 2 * button.volume()
old = json.loads(bind('data/print-baseline.json').read_text())
old_parts = {x['part']: x for x in old['pieces']}
old_volume = sum((old_parts[n]['quantity_per_unit'] * old_parts[n]['unrounded_volume_cm3'] * 1000 for n in ['cover', 'guide_bar', 'button_face', 'plunger']))
assert all((sha(R / p) == h for p, h in inputs.items()))
out = {'inputs': inputs, 'checks': rows, 'passed': all((x['pass'] for x in rows if not x['name'].startswith('bar_released_'))), 'rejected_alternative_checks': [x for x in rows if x['name'].startswith('bar_released_')], 'new_installed_print_pieces': 22, 'old_installed_print_pieces': 24, 'changed_print_volume_cm3': (new_volume - old_volume) / 1000, 'limits': ['Frozen v13 board authority only, not the later v17 source reconciliation.', 'This does not establish switch maximum overtravel, zero-preload calibration, return reliability, prevailing torque or print strength.', 'Tool and screw envelopes remain nominal allocations; sample validation is required.']}
(H / 'integration-report.json').write_text(json.dumps(out, indent=2) + '\n')
print('integration', out['passed'], 'volume delta', out['changed_print_volume_cm3'])
