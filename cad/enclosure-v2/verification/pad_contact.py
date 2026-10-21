# Maintained check migrated from a frozen candidate; see evidence/check-origins.json.
from pathlib import Path
import sys
PACKAGE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PACKAGE))
from geometry import operations as ops
from pathlib import Path
import ast, json, math, hashlib, re, numpy as np
H = Path(__file__).resolve().parent
R = H.parent
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
f = R / 'geometry/operations.py'
ns = {'np': np, 'math': math}
ops.into(['point_seg', 'segment_segment'], ns)
p = R / 'data/pack-paths.json'
cases = json.loads(p.read_text())
rows = []
hardware = []
source = (R / 'source/definitions.scad').read_text()
bolt_z = float(re.search('wire_clamp__bolt_z=([.0-9]+)', source)[1])
adjustment = float(re.search('^wire_clamp__adjustment=([.0-9]+)', source, re.M)[1])
assert bolt_z == 62.5 and adjustment == 0.1

def cylinder_clearance(w, x, y0, y1, z, r, hexagon=False):
    a = w[:-1]
    d = w[1:] - a

    def ds(t):
        q = a + t[:, None] * d
        points = q[:, [0, 2]] - [x, z]
        rad = np.maximum(np.linalg.norm(points, axis=1) - r, 0)
        if hexagon:
            vertices = np.array([[r * math.cos(ang), r * math.sin(ang)] for ang in np.arange(6) * math.pi / 3 + math.pi / 6])
            dd = []
            cross = []
            for aa, bb in zip(vertices, np.roll(vertices, -1, axis=0)):
                edge = bb - aa
                tt = np.clip((points - aa) @ edge / (edge @ edge), 0, 1)
                dd.append(np.linalg.norm(points - aa - tt[:, None] * edge, axis=1))
                cross.append(edge[0] * (points[:, 1] - aa[1]) - edge[1] * (points[:, 0] - aa[0]))
            rad = np.where(np.all(np.array(cross) >= -1e-10, axis=0), 0, np.min(dd, axis=0))
        ax = np.maximum(np.maximum(y0 - q[:, 1], q[:, 1] - y1), 0)
        return rad * rad + ax * ax
    lo = np.zeros(len(a))
    hi = np.ones(len(a))
    g = (math.sqrt(5) - 1) / 2
    for _ in range(70):
        c = hi - g * (hi - lo)
        e = lo + g * (hi - lo)
        choose = ds(c) < ds(e)
        hi = np.where(choose, e, hi)
        lo = np.where(choose, lo, c)
    return math.sqrt(float(np.minimum.reduce([ds((lo + hi) / 2), ds(np.zeros(len(a))), ds(np.ones(len(a)))]).min())) - 0.93
for ci, case in enumerate(cases):
    for i, w in enumerate(case):
        w = np.array(w)
        j = np.where((w[:-1, 2] <= 43) & (w[1:, 2] > 43))[0][0]
        a, b = w[j:j + 2]
        q = a + (43 - a[2]) / (b[2] - a[2]) * (b - a)
        overlaps = {str(adj): 99.65 + 0.508 + adj - (q[1] - 0.925) for adj in [-0.25, 0, 0.1, 0.15]}
        rows.append({'row_case': ci, 'wire': i + 1, 'section_z_mm': 43, 'centre': q.tolist(), 'assumed_max_OD_mm': 1.85, 'nominal_compression_depth_along_Y_mm': overlaps, 'pad_contact_at_trial_plus0p1': bool(overlaps['0.1'] > 0), 'limits': 'Projected nominal contact, not physical squeeze/friction/axial capacity. Fan and body OD uncertain; smaller actualOD may need pad or setting revision.'})
        for x in [56.5, 64]:
            for name, y0, y1, rad in [('shank', 98.3, 106.3, 1), ('head', 106.3, 108.3, 1.9), ('nut', 99.05, 100.65, 2.31)]:
                d = cylinder_clearance(w, x, y0, y1, bolt_z, rad, False)
                hardware.append({'case': ci, 'wire': i + 1, 'bolt_x': x, 'part': name, 'finite_cylinder_clearance_mm': d, 'pass': d > 0})
files = [Path(__file__), f, p, R / 'source/definitions.scad']
out = {'inputs': {str(p.relative_to(R)): sha(p) for p in files}, 'contact': rows, 'hardware': hardware, 'passed': all((q['pad_contact_at_trial_plus0p1'] for q in rows)) and all((q['pass'] for q in hardware)), 'remaining': ['No pull, torque, creep or insulation damage test', 'M2nut and screw geometry is nominal, not supplier-qualified', 'Adjustment trial0.1 and limit0.15 do not establish universal OD coverage', 'Pad material SG-30 GP .020inch planningcandidate, stock/laser-cut tolerance unqualified']}
(H / 'pad-contact.json').write_text(json.dumps(out, indent=2) + '\n')
print('passed', out['passed'], 'min_hardware', min((q['finite_cylinder_clearance_mm'] for q in hardware)))
