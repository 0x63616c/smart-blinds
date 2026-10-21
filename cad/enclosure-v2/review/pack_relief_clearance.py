from pathlib import Path
import hashlib,json,sys,numpy as np
H=Path(__file__).resolve().parent;R=H.parent;sys.path.insert(0,str(R))
from geometry.mesh import stl
from geometry.operations import near
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest();inputs={}
def bind(n):p=R/n;inputs[n]=sha(p);return p
bind('review/pack_relief_clearance.py');bind('geometry/operations.py');bind('geometry/mesh.py');bind('source/definitions.scad');bind('parameters/enclosure-v2.json')
f=json.loads(bind('data/pack-paths.json').read_text());meshes={n:stl(bind('exports/'+n+'.stl'))for n in['front','rear']};rows=[]
for i,case in enumerate(f):
 for j,w in enumerate(case):
  for n,t in meshes.items():
   d,wit=near(np.array(w),1.23,t);rows.append({'row_sensitivity_case':i,'wire':j+1,'part':n,'clearance_or_3mm_lower_bound':d,'pass':d>0,'failure_witness':wit if d<=0 else None})
assert all(sha(R/n)==h for n,h in inputs.items());out={'inputs':inputs,'passed':all(x['pass']for x in rows),'checks':rows,'limits':['Full unchanged polyline geometry checked with1.23mm radius, including1.85mm maximum wire OD plus retained planning allowance.','Three nominal contact-height cases are a sensitivity study, not a vendor contact-position tolerance.','Static free path geometry is not strain relief force or elastic service qualification.']};(H/'pack-relief-clearance.json').write_text(json.dumps(out,indent=2)+'\n');print(len(rows),'checks; min',min(x['clearance_or_3mm_lower_bound']for x in rows),'passed',out['passed']);assert out['passed']
