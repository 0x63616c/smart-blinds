# Maintained check migrated from a frozen candidate; see evidence/check-origins.json.
from pathlib import Path
import sys
PACKAGE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PACKAGE))
from geometry import operations as ops
from pathlib import Path
import ast, numpy as np, math, json, hashlib
H = Path(__file__).resolve().parent
R = H.parent
f = R / 'geometry/operations.py'
n = {'np': np, 'math': math}
ops.into(['point_seg', 'segment_segment'], n)
p = H / 'parking_screen.py'
e = {'np': np, 'math': math, 'ns': n}
ops.into(['wires'], e)
rng = np.random.default_rng(773)
errs = []
for j in range(80):
    a = np.cumsum(rng.normal(size=(15, 3)), axis=0)
    b = np.cumsum(rng.normal(size=(18, 3)), axis=0) + rng.uniform(-8, 8, size=3)
    ra, rb = rng.uniform(0.2, 1.3, size=2)
    exact = math.sqrt(min((float(n['segment_segment'](x, y, b[:-1], b[1:]).min()) for x, y in zip(a[:-1], a[1:])))) - ra - rb
    fast = e['wires'](a, ra, b, rb)
    errs.append(abs(fast - min(3.0, exact)))
assert max(errs) < 1e-10
out = {'inputs': {str(q.relative_to(R)): hashlib.sha256(q.read_bytes()).hexdigest() for q in [Path(__file__), p, f]}, 'comparisons': 80, 'maximum_error_mm': max(errs), 'passed': True}
(H / 'broadphase-controls.json').write_text(json.dumps(out, indent=2) + '\n')
print(out['comparisons'], out['maximum_error_mm'])
