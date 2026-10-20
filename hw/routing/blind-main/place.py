from pathlib import Path
import json,sys,os,hashlib,uuid
import wx,pcbnew
sys.path.insert(0,'tools')
from generate_schematics import board_graph
from kicad_sexpr import parse,dumps,walk
app=wx.App(False);quiet=wx.LogNull()
source=Path('hw/layouts/blind-main/main-test/main-test.kicad_pcb').resolve()
out=Path('work/main-route-build/main-controller.kicad_pcb').resolve();out.parent.mkdir(exist_ok=True)
b=pcbnew.LoadBoard(str(source));plan=json.loads(Path('hw/routing/blind-main/placement.json').read_text())
assert not plan['failed'] and not list(b.GetTracks())
for f in b.GetFootprints():
 a=f.GetFieldText('atopile_address');p=plan['placements'][a]
 f.SetPosition(pcbnew.VECTOR2I(pcbnew.FromMM(100+p['uv'][0]),pcbnew.FromMM(175-p['uv'][1])))
 f.SetOrientationDegrees(p['rotation'])
pcbnew.SaveBoard(str(out),b)
# Imported reusable footprint definitions repeat child UUIDs across instances.
# Derivative-only unique IDs make DRC item references unambiguous. No groups or
# item-reference tables occur in this candidate; reject rather than corrupt one.
tree=parse(out.read_text());assert not list(walk(tree,'group'))
# SWIG Models() iteration returns copies; normalize paths in the saved AST.
for model in walk(tree,'model'):
 raw=model[1]
 if '${KIPRJMOD}' in raw:
  target=Path(raw.replace('${KIPRJMOD}',str(source.parent))).resolve()
  assert target.is_file(),'Missing source 3D model: '+raw
  model[1]='${KIPRJMOD}/'+os.path.relpath(target,out.parent)
for i,node in enumerate(walk(tree,'uuid')):
 node[1]=str(uuid.uuid5(uuid.NAMESPACE_URL,'smart-blinds/main-routing/item/'+str(i)))
out.write_text(dumps(tree)+'\n')
assert board_graph(source)==board_graph(out),'Graph changed'
# Checked-in comparative rules are explicit; final stackup/current/process
# acceptance remains separate from these clearance minima.
p=json.loads(Path('hw/routing/blind-main/project-template.json').read_text())
r=p['board']['design_settings']['rules'];r.update(min_clearance=.15,min_copper_edge_clearance=.2,min_hole_clearance=.2,min_hole_to_hole=.25,min_through_hole_diameter=.2,min_track_width=.15,min_via_annular_width=.1,min_silk_clearance=.15,min_text_height=1.,min_text_thickness=.15)
for c in p['net_settings']['classes']:
 c['clearance']=.15;c['track_width']=.2;c['via_diameter']=.6;c['via_drill']=.3
out.with_suffix('.kicad_pro').write_text(json.dumps(p,indent=2)+'\n')
table=(source.parent/'fp-lib-table').read_text().replace('${KIPRJMOD}',str(source.parent))
(out.parent/'fp-lib-table').write_text(table)
print('Wrote experimental copy with unchanged graph:',out)
