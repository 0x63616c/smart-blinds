from pathlib import Path
import sys,json,hashlib,numpy as np
from manifold3d import Manifold,Mesh,Error
H=Path(__file__).resolve().parent;R=H.parent;sys.path.insert(0,str(R));from geometry.mesh import stl
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest();inputs={}
def load(n):
 p=R/'exports'/(n+'.stl');inputs[str(p.relative_to(R))]=sha(p);t=stl(p);v,i=np.unique(t.reshape(-1,3),axis=0,return_inverse=True);m=Manifold(Mesh(v.astype(np.float32),i.reshape(-1,3).astype(np.uint32)));assert m.status()==Error.NoError;return m
def b(p,s):return Manifold.cube(s).translate(p)
p={n:load(n)for n in ['front','rear','spacer','contents','pack_fasteners','motor_frame','guard_clamp','backing','tail_keeper','cover','backplate']}
f=p['front'];r=p['rear']
# Full boss-link underside relief includes the nearby spacer edge stop.
f=f-b([36.9,109.0,36.9],[11,2.8,2.2])
# Motor-boss relief adds1mm to inside; physical wall never just pared away.
f=(f+b([89.8,64.4,62.7],[1.2,7.2,4.6]))-Manifold.cylinder(4.8,3.4,3.4,48).translate([95,68,62.6])
# Upper temporary capture: keep an exterior side band, no additional installed piece.
# Each half meets at34.3. Capture keepout extends toX92.6;12/10mm band bridges to existing wall.
f=(f+b([92.6,97.9,34.3],[1.2,9.0,6.7])+b([91.2,97.9,39.8],[2.6,9.0,1.2]))-b([89.3,97.9,34.2],[3.3,9.0,5.6])
r=(r+b([92.6,97.9,27.2],[1.2,9.0,7.1])+b([91.2,97.9,27.2],[2.6,9.0,1.2]))-b([90.8,97.9,28.4],[1.8,9.0,6.0])
# Lower right hook only: local raised side roof with same0.4mm clearance.
f=(f+b([92.6,9.1,37.8],[1.2,1.8,3.2])+b([91.2,9.1,39.8],[2.6,1.8,1.2]))-b([89.3,9.1,37.8],[3.3,1.8,2.0])
rows=[]
for n,a in [('front',f),('rear',r)]:
 for m,q in p.items():
  if m in ['front','rear']:continue
  z=a^q;rows.append({'pair':[n,m],'pass':z.is_empty(),'volume_mm3':z.volume(),'regions':[{'bounds':t.bounding_box(),'volume_mm3':t.volume()}for t in z.decompose()]})
z=f^r;rows.append({'pair':['front','rear'],'pass':z.is_empty(),'volume_mm3':z.volume()})
print(json.dumps([a for a in rows if not a['pass']],indent=2));print('components',len(f.decompose()),len(r.decompose()))
(H/'capture-relief-trial.json').write_text(json.dumps({'inputs':inputs,'checks':rows,'connected_components':{'front':len(f.decompose()),'rear':len(r.decompose())},'status':'Pure Boolean trial, not SCAD export acceptance'},indent=2)+'\n')
