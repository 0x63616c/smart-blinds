"""One-time review against the frozen baseline; not a normal geometry dependency."""
from pathlib import Path
import collections,functools,hashlib,json,math,sys,numpy as np
H=Path(__file__).resolve().parent;R=H.parent;B=R.parent/'enclosure-v2-maintained';sys.path.insert(0,str(R))
from geometry.mesh import stl,canonical_triangles,topology
# Exact planar helper retained from the frozen predecessor; only auxiliary
# service hardware may use it. Printable roles remain exact-triangle checked.
def exact_planar_boundaries(t,scale):
 planes=collections.defaultdict(collections.Counter)
 for tri in t:
  p=[tuple(int(float(x)*scale)for x in v)for v in tri];a,b,c=p
  u=[b[i]-a[i]for i in range(3)];v=[c[i]-a[i]for i in range(3)]
  n=[u[1]*v[2]-u[2]*v[1],u[2]*v[0]-u[0]*v[2],u[0]*v[1]-u[1]*v[0]]
  coeff=n+[-sum(n[i]*a[i]for i in range(3))];g=functools.reduce(math.gcd,map(abs,coeff));assert g,'Degenerate triangle'
  coeff=tuple(x//g for x in coeff)
  if next(x for x in coeff if x)<0:coeff=tuple(-x for x in coeff)
  for i,j in [(0,1),(1,2),(2,0)]:
   edge=tuple(sorted((p[i],p[j])));planes[coeff][edge]+=1 if p[i]<p[j]else -1
 # Directed internal diagonals cancel. Keep nonzero multiplicity, including
 # touching hardware operands; do not pretend this assembly is one print.
 return {k:tuple(sorted((e,c)for e,c in v.items()if c))for k,v in planes.items()}
# Coplanar diagonal changes must pass; a real surface movement must fail.
qa=np.array([[[0,0,0],[1,0,0],[1,1,0]],[[0,0,0],[1,1,0],[0,1,0]]],float)
qb=np.array([[[0,0,0],[1,0,0],[0,1,0]],[[1,0,0],[1,1,0],[0,1,0]]],float)
assert exact_planar_boundaries(qa,16)==exact_planar_boundaries(qb,16)
qc=qb.copy();qc[:,:,2]+=1/16
assert exact_planar_boundaries(qa,16)!=exact_planar_boundaries(qc,16)

sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest();d=json.loads((R/'evidence/baseline.json').read_text());assert sha(B/'checkpoint.json')==d['checkpoint_sha256'];rows=[];inputs={'review/compare_baseline.py':sha(Path(__file__)),'geometry/mesh.py':sha(R/'geometry/mesh.py'),'evidence/baseline.json':sha(R/'evidence/baseline.json')}
for name,oldhash in d['inherited_meshes'].items():
 a=B/'exports'/name;b=R/'exports'/name;assert sha(a)==oldhash
 at,bt=stl(a),stl(b);equal=np.array_equal(canonical_triangles(at),canonical_triangles(bt));role=Path(name).stem;expected_change=role in['front','rear'];geometry_equal=equal;planar=None
 if role=='service_hardware'and not equal:
  same_vertices=np.array_equal(np.unique(at.reshape(-1,3),axis=0),np.unique(bt.reshape(-1,3),axis=0));scale=max(float(x).as_integer_ratio()[1]for x in np.r_[at.ravel(),bt.ravel()]);ab,bb=exact_planar_boundaries(at,scale),exact_planar_boundaries(bt,scale);ta,tb=topology(at),topology(bt);geometry_equal=same_vertices and ab==bb and ta['connected_components']==tb['connected_components']and ta['closed_edges']==tb['closed_edges'];planar={'same_exact_float32_vertices':same_vertices,'binary_integer_scale':scale,'exact_boundaries_equal':ab==bb,'planes':len(ab),'method':'Exact integer-plane directed boundary multiplicities; auxiliary touching hardware only, no tolerance.'}
 assert geometry_equal!=expected_change,(role,geometry_equal)
 inputs['exports/'+name]=sha(b);rows.append({'role':role,'baseline_sha256':oldhash,'new_sha256':sha(b),'exact_float32_triangle_equal':equal,'exact_geometry_equal':geometry_equal,'planar_proof':planar,'expected_change':expected_change,'baseline_volume_mm3':topology(at)['volume_mm3'],'new_volume_mm3':topology(bt)['volume_mm3']})
# Comparator must reject a deliberate changed vertex without rounding.
t=stl(R/'exports/front.stl');bad=t.copy();bad[0,0,0]+=0.01;assert not np.array_equal(canonical_triangles(t),canonical_triangles(bad))
out={'inputs':inputs,'baseline_checkpoint_sha256':d['checkpoint_sha256'],'passed':True,'roles':rows,'exact_unchanged_roles':sum(r['exact_geometry_equal']for r in rows),'exact_triangle_unchanged_roles':sum(r['exact_float32_triangle_equal']for r in rows),'planar_controls':{'alternate_coplanar_diagonal':True,'moved_surface_rejected':True},'changed_roles':[r['role']for r in rows if r['expected_change']],'moved_vertex_control':True,'status':'Exact source-export comparison; front/rear are intentional corrections. No physical qualification.'};assert all(sha(R/p)==h for p,h in inputs.items());(H/'baseline-comparison.json').write_text(json.dumps(out,indent=2)+'\n');print(out['exact_unchanged_roles'],'unchanged roles; changed',out['changed_roles'])
