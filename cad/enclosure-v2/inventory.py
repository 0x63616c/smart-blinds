"""Count exact closed print meshes; this is not a slicer/material purchase estimate."""
from pathlib import Path
import csv,hashlib,json,sys
H=Path(__file__).resolve().parent;sys.path.insert(0,str(H))
from geometry.mesh import stl,topology
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
PARTS={'cover':1,'backplate':1,'guide_bar':1,'button':2,'motor_frame':1,'backing':1,'guard_clamp':1,'tail_keeper':1,'front':1,'rear':1,'spacer':1,'upper_clip':1,'lower_clip':1,'rear_lower':1,'rear_upper':1,'front_lower':1,'front_upper':1,'bearing_block':1,'retainer':1,'wheel':1,'guard':1}
def main():
 source=json.loads((H/'evidence/current-exports.json').read_text());expected={r['part']:r for r in source['outputs']};rows=[]
 for n,q in (PARTS|{'cosmetic_plug':2,'nest':1}).items():
  p=H/'exports'/(n+'.stl');assert sha(p)==expected[n]['sha256'],n;t=topology(stl(p));assert t['closed_edges']and t['connected_components']==1,(n,t)
  rows.append({'part':n,'quantity_per_unit':q if n!='nest'else 0,'shared_quantity':q if n=='nest'else 0,'category':'workshop'if n=='nest'else'optional'if n=='cosmetic_plug'else'installed','file':str(p.relative_to(H)),'sha256':sha(p),'bytes':p.stat().st_size,**t})
 installed=[r for r in rows if r['category']=='installed'];volume=sum(r['volume_mm3']*r['quantity_per_unit']for r in installed)/1000;optional=next(r for r in rows if r['part']=='cosmetic_plug');nest=next(r for r in rows if r['part']=='nest');assert sum(PARTS.values())==22 and len(PARTS)==21
 report={'status':'Dense geometric estimate; not sliced/printed/strength qualified','inputs':{'inventory.py':sha(Path(__file__)),'geometry/mesh.py':sha(H/'geometry/mesh.py'),'evidence/current-exports.json':sha(H/'evidence/current-exports.json')},'installed_pieces_per_unit':22,'distinct_installed_shapes':21,'installed_pieces_for_eight':176,'optional_cap_pieces_per_unit':2,'optional_cap_shapes':1,'new_shared_workshop_pieces':1,'installed_volume_cm3':volume,'optional_caps_volume_cm3':optional['volume_mm3']*2/1000,'new_shared_nest_volume_cm3':nest['volume_mm3']/1000,'density_assumption_g_cm3':1.27,'dense_mass_g_per_unit':volume*1.27,'dense_mass_kg_eight':volume*1.27*8/1000,'parts':rows,'limits':['Print orientation, perimeters/infill, supports, brim and waste not resolved.','Existing eight-piece holder-loading fixture is separate and not newly qualified against the revised restraint.','Silicone pads, barrier, O-rings, ties, electrical parts and hardware are not printed pieces.','The housing tie/inline connector/ring/contents/whole-drive exports are verification operands, not extra printable parts.']}
 (H/'evidence/inventory.json').write_text(json.dumps(report,indent=2)+'\n')
 with (H/'print-list.csv').open('w',newline='')as f:
  w=csv.writer(f,lineterminator='\n');w.writerow(['part','category','quantity_per_unit','shared_quantity','volume_cm3_each','stl','sha256'])
  for r in rows:w.writerow([r['part'],r['category'],r['quantity_per_unit'],r['shared_quantity'],r['volume_mm3']/1000,r['file'],r['sha256']])
 print(json.dumps({k:v for k,v in report.items()if k not in ['inputs','parts','limits']},indent=2))
if __name__=='__main__':main()
