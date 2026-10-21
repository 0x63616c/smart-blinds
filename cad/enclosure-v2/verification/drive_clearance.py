# Maintained check migrated from a frozen candidate; see evidence/check-origins.json.
from pathlib import Path
import sys
PACKAGE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PACKAGE))
from geometry import operations as ops
"""Static triangle-surface audit of the actual multi-part drive reference.
The touching assembly is intentionally not advertised as a single print mesh.
"""
from pathlib import Path
import importlib.util, hashlib, json, ast, math, sys, numpy as np
H = Path(__file__).resolve().parent
R = H.parent
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
inputs = {}

def bind(p):
    p = R / p
    inputs[str(p.relative_to(R))] = sha(p)
    return p
s = importlib.util.spec_from_file_location('mesh', bind('geometry/mesh.py'))
m = importlib.util.module_from_spec(s)
s.loader.exec_module(m)
ns = {'np': np, 'math': math}
ops.into(['point_seg', 'point_tri', 'segment_segment', 'seg_tri', 'tri_tri'], ns)
bind(Path(__file__).relative_to(R))
drive = m.stl(bind('exports/drive.stl'))
pass
import manifold3d
from manifold3d import Manifold, Mesh, Error
None
back = m.stl(bind('exports/backplate.stl'))
v, ix = np.unique(back.reshape(-1, 3), axis=0, return_inverse=True)
solid = Manifold(Mesh(v.astype(np.float32), ix.reshape(-1, 3).astype(np.uint32)))
assert solid.status() == Error.NoError
solid = solid - Manifold.cube([200, 300, 6.01]).translate([-20, -30, 0])
mm = solid.to_mesh()
back = np.array(mm.vert_properties)[:, :3][np.array(mm.tri_verts)]
v, ix = np.unique(drive.reshape(-1, 3), axis=0, return_inverse=True)
ix = ix.reshape(-1, 3)
parent = list(range(len(v)))

def root(i):
    while parent[i] != i:
        parent[i] = parent[parent[i]]
        i = parent[i]
    return i
for a, b, c in ix:
    for j in [b, c]:
        parent[root(j)] = root(a)
witness = {}
for i, (a, b, c) in enumerate(ix):
    witness.setdefault(root(a), drive[i].mean(0))
rows = []
for name, mesh in [('cover', m.stl(bind('exports/cover.stl'))), ('backplate_above_drive_seat', back)]:
    lo = mesh.min(1)
    hi = mesh.max(1)
    best = 1.0
    hit = []
    pairs = 0
    for i, t in enumerate(drive):
        ids = np.where(np.all(hi >= t.min(0) - best, axis=1) & np.all(lo <= t.max(0) + best, axis=1))[0]
        if not len(ids):
            continue
        ds = ns['tri_tri'](t, mesh[ids])
        pairs += len(ds)
        d = math.sqrt(max(0, float(ds.min())))
        best = min(best, d)
        if d < 1e-06:
            hit.append({'triangle': i, 'other': int(ids[int(ds.argmin())]), 'distance_mm': d})
    inside = [p.tolist() for p in witness.values() if m.inside_mesh(p, mesh)]
    rows.append({'obstacle': name, 'surface_gap_or_1mm_lower_bound': best, 'tested_triangle_pairs': pairs, 'surface_findings': hit, 'contained_drive_component_witnesses': inside, 'pass': not hit and (not inside)})
    print(name, 'findings', len(hit), len(inside), flush=True)
assert all((sha(R / p) == h for p, h in inputs.items()))
out = {'inputs': inputs, 'drive_surface_components': len(witness), 'checks': rows, 'passed': all((r['pass'] for r in rows)), 'limits': ['Static exact triangular geometry only, no supplier dimensional tolerance or thermal/load qualification', 'Backplate geometry belowZ6.01 is the deliberately shared drive seat; upright posts and every higher obstacle remain', 'Touching drive assembly is not a single valid printable solid; its eight named prints are checked separately', 'Motor dimensional allowance and chain behavior must still be qualified on the purchased motor/blind']}
(H / 'drive-clearance-report.json').write_text(json.dumps(out, indent=2) + '\n')
