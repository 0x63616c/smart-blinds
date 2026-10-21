"""Finish an explicitly rebound successor only when current source evidence agrees."""
from pathlib import Path
import json,hashlib
H=Path(__file__).resolve().parent;sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
def read(n):return json.loads((H/n).read_text())
def bound(d):
 for n,h in d.get('inputs',{}).items():
  p=(H/n).resolve();assert p.is_relative_to(H.resolve())and p.is_file()and sha(p)==h,('stale or external input',n)
run=read('evidence/verification-run.json');bound(run);assert run['passed']and run['complete']and len(run['jobs'])==17
mc=read('review/manifest-selection-controls.json');bound(mc);assert mc['passed']and mc['current_roles']==30 and len(mc['controls'])==5
for j in run['jobs']:
 assert j['passed']and sha(H/j['report'])==j['report_sha256']and sha(H/'verification'/(j['name']+'.log'))==j['log_sha256'];d=read(j['report']);bound(d);assert d['passed']
ex=read('evidence/current-exports.json');bound(ex)
for x in ex['outputs']:assert sha(H/x['file'])==x['sha256']
re=read('verification/cassette-reliefs-report.json');assert re['passed']and len(re['preserved_failure_regressions'])==4
inv=read('evidence/inventory.json');bound(inv);assert inv['installed_pieces_per_unit']==22
for x in inv['parts']:assert sha(H/x['file'])==x['sha256']and x['closed_edges']and x['connected_components']==1
co=read('review/baseline-comparison.json');bound(co);assert co['passed']and co['exact_unchanged_roles']==28 and set(co['changed_roles'])=={'front','rear'}
assert co['exact_triangle_unchanged_roles']==27 and all(co['planar_controls'].values())
assert sha(H/'references/historical-maintained/checkpoint.json')==co['baseline_checkpoint_sha256']
br=read('review/board-rebind-delta.json');bound(br);assert br['current_sha256']=='03a6b3dc624e2cf0e83f8cfdd90f64dc52071fb2b8387deb0e22949903981e74'and br['rear_vias']==120 and br['outline_exact_sexpr_equal']
pa=read('review/pack-relief-clearance.json');bound(pa);assert pa['passed']and len(pa['checks'])==36
rr=read('review/render-report.json');bound(rr);assert len(rr['outputs'])==4
for r in rr['outputs']:assert sha(H/r['file'])==r['sha256']
vr=read('review/visual-review.json');bound(vr);assert vr['inspected']and len(vr['images'])==4
for r in vr['images']:assert sha(H/r['file'])==r['sha256']
files={str(p.relative_to(H)):sha(p)for p in sorted(H.rglob('*'))if p.is_file()and'__pycache__'not in str(p)and p.name!='checkpoint.json'}
out={'status':'Frozen bounded cassette-relief successor with fresh nominal checks; physical assembly qualification remains','files':files,'physical_board_sha256':br['current_sha256'],'rear_vias':120,'fresh_jobs':17,'baseline_checkpoint_sha256':co['baseline_checkpoint_sha256'],'unchanged_export_roles':28,'changed_print_shapes':['front','rear'],'installed_print_pieces':22,'exterior_mm':[118,196,77],'physical_assembly_accepted':False,'limitations':['Two cassette source operands remain inherited meshes.','Nominal source geometry and finite rigid/sampled-wire checks do not prove print strength, insulation, hand/catch access, loaded handling or flexible-cable behavior.','Optional home-sensor path remains unfinished.','No purchase or fabrication release.']};(H/'checkpoint.json').write_text(json.dumps(out,indent=2)+'\n');print('Frozen',len(files),'files; SHA256',sha(H/'checkpoint.json'))
