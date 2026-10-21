"""Exact source-mesh pair/motion checks and retained failing regression witnesses."""
from pathlib import Path
import sys,json,hashlib,numpy as np
from manifold3d import Manifold,Mesh,Error
H=Path(__file__).resolve().parent;R=H.parent;sys.path.insert(0,str(R))
from geometry.mesh import stl,topology
from geometry.operations import swept_check
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest();inputs={}
def bind(n):
 p=R/n;inputs[n]=sha(p);return p
def load(n):
 t=stl(bind(n));v,i=np.unique(t.reshape(-1,3),axis=0,return_inverse=True);s=Manifold(Mesh(v.astype(np.float32),i.reshape(-1,3).astype(np.uint32)));assert s.status()==Error.NoError;return s,t
bind('verification/cassette_reliefs.py');bind('geometry/mesh.py');bind('geometry/operations.py');bind('source/definitions.scad');par=json.loads(bind('parameters/enclosure-v2.json').read_text())
assert par['case']=={'width':118,'height':196,'depth':77,'bottom_y':-11}
assert par['cassette_relief']['link_remaining_width_height']==[3,3.9]
names=['front','rear','spacer','contents','pack_fasteners','motor_frame','guard_clamp','backing','tail_keeper','cover','backplate'];parts={};tris={}
for n in names:parts[n],tris[n]=load('exports/'+n+'.stl')
def b(p,s):return Manifold.cube(s).translate(p)
rows=[]
def check(a,q,n,expected_empty=True):
 assert a.status()==Error.NoError and q.status()==Error.NoError
 hit=a^q;assert hit.status()==Error.NoError
 rows.append({'name':n,'volume_mm3':hit.volume(),'bounds':None if hit.is_empty()else hit.bounding_box(),'expected_empty':expected_empty,'pass':hit.is_empty()==expected_empty})
for n in ['front','rear']:
 for other in names:
  if other in ['front','rear']:continue
  check(parts[n],parts[other],n+'_vs_'+other)
check(parts['front'],parts['rear'],'front_vs_rear')
regressions=[]
for n,obs in [('front','contents'),('front','motor_frame'),('front','spacer'),('rear','spacer')]:
 old,_=load('data/baseline-'+n+'.stl');hit=old^parts[obs];assert hit.status()==Error.NoError and not hit.is_empty();regressions.append({'pair':[n,obs],'volume_mm3':hit.volume(),'regions':[{'volume_mm3':q.volume(),'bounds':q.bounding_box()}for q in hit.decompose()]})
# Thickness/clearance witnesses bind actual retained material rather than just nominal labels.
checks=[('link_gap_0p5_above_actual_FR4',[41,109.5,38.2],[3,.5,.5]),('link_gap_0p5_above_actual_spacer_stop',[42,110.2,38.5],[5,1.2,.5]),('lower_capture_plus_0p3',[89.4,9.2,38.1],[3.1,1.6,1.6])]
for n,p,s in checks:check(parts['front'],b(p,s),n)
check(parts['front'],Manifold.cylinder(5.8,3.3,3.3,48).translate([95,68,63.3]),'motor_boss_plus_0p4')
material=[]
for n,part,p,size in [('motor_recess_1p6_section','front',[89.9,67.9,62.8],[1.6,.2,4.2]),('front_outer_band_1p0_section','front',[92.7,99,35],[1.0,6,4]),('rear_outer_band_1p0_section','rear',[92.7,99,28],[1.0,6,5])]:
 witness=b(p,size);missing=witness-parts[part];assert missing.status()==Error.NoError;material.append({'name':n,'missing_volume_mm3':missing.volume(),'pass':missing.is_empty()})
for n,vec in [('front',[0,0,20]),('rear',[0,0,-20])]:
 for other in ['spacer','contents']:swept_check(parts[n],tris[n],vec,parts[other],n+'_shell_approach_'+other,rows)
tops={n:topology(tris[n])for n in ['front','rear']};assert all(a['closed_edges']and a['connected_components']==1 for a in tops.values())
assert all(sha(R/n)==h for n,h in inputs.items())
out={'inputs':inputs,'passed':all(a['pass']for a in rows+material),'checks':rows,'material_witnesses':material,'topology':tops,'preserved_failure_regressions':regressions,'limits':['No raw/holder/PCB anchors moved; temporary captures remain unchanged.','The new side band is1.2mm nominal; witnesses are inset sections, not a strength calculation.','Motor recess has0.5mm nominal radial clearance and≥1.8mm local nominal wall at its deepest point.','The boss-link remains3×3.9mm nominal; force, creep, insulation and FDM fit require tests.','Shell approach covers rigid±Z20mm strokes. Loaded handling, catch release and flexible harness behavior remain separate gates.']};(H/'cassette-reliefs-report.json').write_text(json.dumps(out,indent=2)+'\n');print('pass',out['passed'],'findings',[a['name']for a in rows+material if not a['pass']]);assert out['passed']
