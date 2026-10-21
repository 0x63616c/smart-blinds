# Maintained check migrated from a frozen candidate; see evidence/check-origins.json.
from pathlib import Path
import sys
PACKAGE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PACKAGE))
from geometry import operations as ops
"""Independent pinned Manifold3D solid check of unchanged source meshes.
No healing/rounding, no CGAL failure reclassified as empty. Model-only evidence.
"""
from pathlib import Path
import hashlib, importlib.util, sys, json, numpy as np
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
solid = {}
records = []
for n, p in [(n, 'exports/' + n + '.stl') for n in ['backplate', 'cover', 'motor_frame', 'backing', 'guard_clamp', 'tail_keeper', 'inline_body', 'housing_tie']] + [(n, 'exports/' + n + '.stl') for n in ['front', 'rear', 'spacer']]:
    t = m.stl(bind(p))
    v, ix = np.unique(t.reshape(-1, 3), axis=0, return_inverse=True)
    so = Manifold(Mesh(v.astype(np.float32), ix.reshape(-1, 3).astype(np.uint32)))
    assert so.status() == Error.NoError, (n, so.status())
    solid[n] = so
    records.append({'part': n, 'volume_mm3': so.volume(), 'status': str(so.status()), 'bounds': so.bounding_box(), 'shells': len(so.decompose())})

def box(lo, hi):
    return Manifold.cube(np.array(hi) - lo).translate(lo)
rows = []

def test(a, b, label):
    q = a ^ b
    assert q.status() == Error.NoError
    v = q.volume()
    rows.append({'name': label, 'volume_mm3': v, 'bounds': q.bounding_box(), 'empty': q.is_empty(), 'pass': q.is_empty(), 'status': str(q.status())})
    print(label, v, flush=True)
for n in ['motor_frame', 'backing', 'guard_clamp', 'tail_keeper', 'inline_body', 'housing_tie', 'front', 'rear', 'spacer']:
    test(solid[n], solid['cover'], n + '_cover')
for a in ['backing', 'tail_keeper']:
    for b in ['front', 'rear', 'spacer']:
        test(solid[a], solid[b], a + '_' + b)
for n in ['front', 'rear', 'spacer']:
    test(solid['guard_clamp'], solid[n], 'guard_clamp_' + n)
w = box([50, 50, 76], [50.5, 50.5, 76.5]) ^ solid['cover']
assert w.status() == Error.NoError and abs(w.volume() - 0.125) < 1e-05
assert (box([50, 50, 35], [51, 51, 36]) ^ solid['cover']).is_empty()
assert all((sha(R / p) == h for p, h in inputs.items()))
out = {'inputs': inputs, 'library': 'manifold3d3.3.2', 'source': 'https://github.com/elalish/manifold', 'method': 'Exact original STL coordinates welded by identical vertex values; float32 interchange, no repair, smoothing or tolerance expansion. Pinned independent Boolean engine. Imported manifold validity checked before each operation.', 'meshes': records, 'checks': rows, 'controls': 2, 'passed': all((q['pass'] for q in rows)), 'limits': ['Static source geometry, not print tolerance, strength or physical fit', 'Earlier CGAL import errors remain failed; this is independent evidence on same mesh hashes']}
(H / 'solid-report.json').write_text(json.dumps(out, indent=2) + '\n')
