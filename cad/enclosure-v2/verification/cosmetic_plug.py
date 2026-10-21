"""Optional cap: rigid paths and explicit unqualified soft-ring contact witness."""
from pathlib import Path
import sys,json,hashlib,numpy as np
H=Path(__file__).resolve().parent;R=H.parent;sys.path.insert(0,str(R))
from geometry.mesh import stl
from geometry.operations import swept_check
from manifold3d import Mesh,Manifold,Error
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest();inputs={}
def bind(p):
 p=R/p;inputs[str(p.relative_to(R))]=sha(p);return p
def load(n):
 t=stl(bind('exports/'+n+'.stl'));v,i=np.unique(t.reshape(-1,3),axis=0,return_inverse=True);q=Manifold(Mesh(v.astype(np.float32),i.reshape(-1,3).astype(np.uint32)));assert q.status()==Error.NoError;return q,t
plug,pt=load('cosmetic_plug');ring,rt=load('ring');button,bt=load('button');rows=[]
swept_check(plug,pt,[0,0,10],button,'rigid_plug_removal_without_elastic_ring',rows)
q=ring^button;rows.append({'name':'uncompressed_ring_contact_witness','volume_mm3':q.volume(),'pass':q.volume()>0})
rows.append({'name':'single_connected_print','components':len(plug.decompose()),'pass':len(plug.decompose())==1})
blade=Manifold.cube([8,1.6,.3]).translate([2.1,-.8,78.85]);mm=blade.to_mesh();tri=np.array(mm.vert_properties)[:,:3][np.array(mm.tri_verts)]
swept_check(blade.translate([8,0,0]),tri+[8,0,0],[-8,0,0],button+plug,'nonconductive_blade_approach',rows)
rows.append({'name':'screw_head_gap','clearance_mm':74.8-(62.75+8+2),'pass':74.8>62.75+8+2})
for bore in[4.0,4.2,4.4]:
 gap=(bore-2.5)/2;rows.append({'name':'ring_sensitivity_'+str(bore),'assumed_bore_mm':bore,'radial_squeeze_fraction':1-gap,'gland_fill_nominal':np.pi*.25/(gap*1.2),'pass':0<1-gap<.3,'status':'Planning sensitivity, not qualified printer or ring tolerance'})
bind(Path(__file__).relative_to(R));assert all(sha(R/p)==h for p,h in inputs.items());out={'inputs':inputs,'checks':rows,'passed':all(x['pass']for x in rows),'limits':['Optional nonstructural cosmetic part; underlying mechanism works without it.','70A silicone2.5IDx1CS catalog geometry. No pull, creep, tear, friction or repeated-removal acceptance.','Ring is deliberately shown undeformed for positive contact evidence; no rigid-fit claim.','Blade is a generic envelope, not a sourced tool or lever-force acceptance.']};(H/'cosmetic-report.json').write_text(json.dumps(out,indent=2)+'\n')
