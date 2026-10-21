# Maintained check migrated from a frozen candidate; see evidence/check-origins.json.
from pathlib import Path
import sys
PACKAGE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PACKAGE))
from geometry import operations as ops
from pathlib import Path
import ast, hashlib, importlib.util, json, sys
import numpy as np
H = Path(__file__).resolve().parent
R = H.parent
pass
from manifold3d import Mesh, Manifold, Error, OpType
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
inputs = {}

def bind(p):
    p = R / p
    inputs[str(p.relative_to(R))] = sha(p)
    return p
s = importlib.util.spec_from_file_location('reader', bind('geometry/mesh.py'))
m = importlib.util.module_from_spec(s)
s.loader.exec_module(m)
bind(Path(__file__).relative_to(R))
report = json.loads(bind('evidence/current-exports.json').read_text())
for p, h in report['inputs'].items():
    assert sha(R / p) == h
    inputs[p] = h
for p in report['outputs']:
    assert sha(R / p['file']) == p['sha256']

def mesh(n):
    t = m.stl(bind('exports/' + n + '.stl'))
    v, i = np.unique(t.reshape(-1, 3), axis=0, return_inverse=True)
    q = Manifold(Mesh(v.astype(np.float32), i.reshape(-1, 3).astype(np.uint32)))
    assert q.status() == Error.NoError
    return (q, t)
cover, ct = mesh('cover')
bar, bt = mesh('guide_bar')
button, pt = mesh('button')
rows = []

def chk(a, b, n):
    q = a ^ b
    assert q.status() == Error.NoError
    rows.append({'name': n, 'volume_mm3': q.volume(), 'bounds': q.bounding_box(), 'pass': q.is_empty()})
    print(n, q.volume(), flush=True)
ops.into(['swept_check'], globals())
cover = cover ^ Manifold.cube([55, 90, 30]).translate([65, -10, 60])
buttons = [button.translate([109.4, y, -0.4]) for y in [22, 42]]
pressed = buttons[0] + buttons[1]
for y in [22, 42]:
    swept_check(button.translate([109.4, y, 20]), pt + [109.4, y, 20], [0, 0, -20.4], cover, 'front_insert_' + str(y))
for n, start, vec in [('rear_approach', [0, 8.5, -16], [0, 0, 15.8]), ('slide', [0, 8.5, -0.2], [0, -8.5, 0]), ('seat', [0, 0, -0.2], [0, 0, 0.2])]:
    swept_check(bar.translate(start), bt + start, vec, cover + pressed, 'bar_' + n)
for y in [22, 42]:
    swept_check(button.translate([109.4, y, -0.4]), pt + [109.4, y, -0.4], [0, 0, 0.4], cover + bar, 'release_' + str(y))
for n, q in [('cover', mesh('cover')[0]), ('bar', bar), ('button', button)]:
    rows.append({'name': n + '_single_piece', 'connected_components': len(q.decompose()), 'volume_mm3': q.volume(), 'pass': len(q.decompose()) == 1})
for y in [22, 42]:
    chk(Manifold.cylinder(40, 1.8, 1.8, 48).translate([109.4, y, 71.6]), cover + bar + button.translate([109.4, y, 0]), 'driver_' + str(y))
assert all((sha(R / p) == v for p, v in inputs.items()))
(H / 'check-report.json').write_text(json.dumps({'inputs': inputs, 'checks': rows, 'passed': all((q['pass'] for q in rows)), 'limits': ['Tool dimensions are allocated generic envelopes, not a purchased tool audit.', 'Assembly motions are rigid nominal geometry; printed strength and friction are not proven.']}, indent=2) + '\n')
