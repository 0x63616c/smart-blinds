from pathlib import Path
import sys,json,hashlib,numpy as np
from manifold3d import Manifold,Mesh,Error
H=Path(__file__).resolve().parent;R=H.parent;sys.path.insert(0,str(R))
from geometry.mesh import stl
inputs={};sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
def load(n):
 p=R/'exports'/(n+'.stl');inputs[str(p.relative_to(R))]=sha(p);t=stl(p);v,i=np.unique(t.reshape(-1,3),axis=0,return_inverse=True);m=Manifold(Mesh(v.astype(np.float32),i.reshape(-1,3).astype(np.uint32)));assert m.status()==Error.NoError;return m
def b(p,s):return Manifold.cube(s).translate(p)
parts={n:load(n)for n in ['front','contents','motor_frame','rear','spacer','pack_fasteners','backing','guard_clamp','tail_keeper']}
# Trial only: raise PCB-crossing link from37 to38.8; existing PCB top38.2 leaves.6.
remove_link=b([40.9,109.4,36.99],[3.2,1.0,1.81])
# Shift local outer wall into free space instead of thinning the screw boss/nut trap.
# Add1mm inside wall, then scoop a radius3.4 clearance around radius2.9 boss.
patch=b([89.8,64.4,62.7],[1.2,7.2,4.6])
scoop=Manifold.cylinder(4.8,3.4,3.4,48).translate([95,68,62.6])
new=(parts['front']+patch)-remove_link-scoop
rows=[]
for n,m in parts.items():
 if n=='front':continue
 q=new^m;rows.append({'pair':['front_candidate',n],'pass':q.is_empty(),'volume':q.volume(),'bounds':None if q.is_empty()else q.bounding_box()})
q=patch^parts['contents'];print('patch contents',q.volume(),q.bounding_box())
print(json.dumps(rows,indent=2));print('newconnected',len(new.decompose()))
(H/'relief-trial.json').write_text(json.dumps({'inputs':inputs,'rows':rows,'connected':len(new.decompose()),'status':'Boolean design trial, not exported SCAD proof'},indent=2)+'\n')
