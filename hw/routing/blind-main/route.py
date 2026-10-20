#!/usr/bin/env python3
"""Rebuild the experimental manual power routes without modifying canonical capture."""
from pathlib import Path
import hashlib,json,os,subprocess,sys,uuid
ROOT=Path(__file__).resolve().parents[3];HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'tools'))
from kicad_sexpr import parse,dumps,children,one,walk
from generate_schematics import board_graph
SOURCE=ROOT/'hw/layouts/blind-main/main-test/main-test.kicad_pcb'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 source_hash=sha(SOURCE);work=ROOT/'work/main-route-build';work.mkdir(parents=True,exist_ok=True)
 for name in ['place.py','charger.py','local_power.py','module_supply.py','usb_input.py','usb_controls.py']:
  result=subprocess.run([sys.executable,str(HERE/name)],cwd=ROOT,capture_output=True,text=True)
  (work/(name+'.log')).write_text(result.stdout+result.stderr)
  if result.returncode:raise RuntimeError(name+' failed; inspect '+str(work/(name+'.log')))
 interim=work/'usb-control-route.kicad_pcb';tree=parse(interim.read_text())
 assert not list(walk(tree,'group'))
 def semantic(v):
  if not isinstance(v,list):return v
  return [semantic(x) for x in v if not (isinstance(x,list) and x and x[0]=='uuid')]
 for kind in ('segment','via','zone'):
  slots=[i for i,v in enumerate(tree) if isinstance(v,list) and v and v[0]==kind]
  for i,v in zip(slots,sorted((tree[i] for i in slots),key=lambda v:dumps(semantic(v)))):tree[i]=v
 for i,node in enumerate(walk(tree,'uuid')):
  node[1]=str(uuid.uuid5(uuid.NAMESPACE_URL,'smart-blinds/main-power-checkpoint/'+str(i)))
 for f in children(tree,'footprint'):
  for model in children(f,'model'):
   value=model[1]
   if '${KIPRJMOD}' in value:
    target=Path(value.replace('${KIPRJMOD}',str(work))).resolve()
    assert target.is_file(),'Missing intermediate 3D model: '+value
    model[1]='${KIPRJMOD}/'+os.path.relpath(target,HERE)
 board=HERE/'main-routed.kicad_pcb';board.write_text(dumps(tree)+'\n')
 board.with_suffix('.kicad_pro').write_bytes(interim.with_suffix('.kicad_pro').read_bytes())
 table=(SOURCE.parent/'fp-lib-table').read_text().replace('${KIPRJMOD}','${KIPRJMOD}/'+os.path.relpath(SOURCE.parent,HERE))
 (HERE/'fp-lib-table').write_text(table)
 assert sha(SOURCE)==source_hash and board_graph(SOURCE)==board_graph(board)
 sources=[SOURCE,HERE/'placement.json',HERE/'project-template.json',HERE/'usb-control-routes.json',HERE/'route.py',*[HERE/n for n in ['place.py','charger.py','local_power.py','module_supply.py','usb_input.py','usb_controls.py']]]
 record={'status':'EXPERIMENTAL PARTIAL main power routing; not a fabrication release','source_hashes':{str(p.relative_to(ROOT)):sha(p) for p in sources},'pcb_sha256':sha(board),'project_sha256':sha(board.with_suffix('.kicad_pro')),'segments':len(children(tree,'segment')),'vias':len(children(tree,'via')),'unrouted_work':['USB differential pair and factory access','Pack feed and charge/system distribution','Regenerative clamp and supervisor loops','Full logic and analogue signals','Current/thermal/return-path review and final manufacturing rules']}
 (HERE/'route-record.json').write_text(json.dumps(record,indent=2)+'\n');print(json.dumps(record,indent=2))
if __name__=='__main__':main()
