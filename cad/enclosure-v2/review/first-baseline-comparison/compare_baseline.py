"""One-time review against the frozen baseline; not a normal geometry dependency."""
from pathlib import Path
import hashlib,json,sys,numpy as np
H=Path(__file__).resolve().parent;R=H.parent;B=R.parent/'enclosure-v2-maintained';sys.path.insert(0,str(R))
from geometry.mesh import stl,canonical_triangles,topology
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest();d=json.loads((R/'evidence/baseline.json').read_text());assert sha(B/'checkpoint.json')==d['checkpoint_sha256'];rows=[];inputs={'review/compare_baseline.py':sha(Path(__file__)),'geometry/mesh.py':sha(R/'geometry/mesh.py'),'evidence/baseline.json':sha(R/'evidence/baseline.json')}
for name,oldhash in d['inherited_meshes'].items():
 a=B/'exports'/name;b=R/'exports'/name;assert sha(a)==oldhash
 at,bt=stl(a),stl(b);equal=np.array_equal(canonical_triangles(at),canonical_triangles(bt));role=Path(name).stem;expected_change=role in['front','rear'];assert equal!=expected_change,(role,equal)
 inputs['exports/'+name]=sha(b);rows.append({'role':role,'baseline_sha256':oldhash,'new_sha256':sha(b),'exact_float32_triangle_equal':equal,'expected_change':expected_change,'baseline_volume_mm3':topology(at)['volume_mm3'],'new_volume_mm3':topology(bt)['volume_mm3']})
# Comparator must reject a deliberate changed vertex without rounding.
t=stl(R/'exports/front.stl');bad=t.copy();bad[0,0,0]+=0.01;assert not np.array_equal(canonical_triangles(t),canonical_triangles(bad))
out={'inputs':inputs,'baseline_checkpoint_sha256':d['checkpoint_sha256'],'passed':True,'roles':rows,'exact_unchanged_roles':sum(r['exact_float32_triangle_equal']for r in rows),'changed_roles':[r['role']for r in rows if r['expected_change']],'moved_vertex_control':True,'status':'Exact source-export comparison; front/rear are intentional corrections. No physical qualification.'};assert all(sha(R/p)==h for p,h in inputs.items());(H/'baseline-comparison.json').write_text(json.dumps(out,indent=2)+'\n');print(out['exact_unchanged_roles'],'unchanged roles; changed',out['changed_roles'])
