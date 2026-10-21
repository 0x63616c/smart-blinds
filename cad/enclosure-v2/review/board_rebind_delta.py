from pathlib import Path
import sys,json,hashlib
h=Path(__file__).resolve().parent.parent;sys.path.insert(0,str(h/'geometry'));from kicad_sexpr import parse,children,one
s=lambda p:hashlib.sha256(p.read_bytes()).hexdigest();old=h.parent/'enclosure-v2-maintained/data/physical-board.kicad_pcb';new=h/'data/physical-board.kicad_pcb'
def read(p):
 b=parse(p.read_text());rows={}
 for fp in children(b,'footprint'):
  ps={x[1]:x[2]for x in children(fp,'property')};a=one(fp,'at');n=ps['atopile_address'];rows[n]={'ref':ps['Reference'],'pose':[float(a[1])-100,175-float(a[2]),float(a[3])if len(a)>3 else 0],'models':children(fp,'model')}
 return b,rows
ob,o=read(old);nb,n=read(new);assert o.keys()==n.keys();changes=[]
for k in o:
 if o[k]!=n[k]:changes.append({'address':k,'old':o[k],'new':n[k]})
print(json.dumps(changes,indent=2));print('vias',len(children(ob,'via')),len(children(nb,'via')))
outline=lambda b:[q for q in b if isinstance(q,list)and q[0]in['gr_line','gr_arc']and one(q,'layer')and one(q,'layer')[1]=='Edge.Cuts']
d={'inputs':{'data/physical-board.kicad_pcb':s(new),'review/board_rebind_delta.py':s(Path(__file__))},'baseline_board':str(old),'baseline_sha256':s(old),'current_board':'data/physical-board.kicad_pcb','current_sha256':s(new),'footprints':len(n),'rear_vias':len(children(nb,'via')),'part_model_pose_changes':changes,'outline_exact_sexpr_equal':outline(ob)==outline(nb),'status':'Deliberate rebind inventory; actual collision screens separate'};(h/'review/board-rebind-delta.json').write_text(json.dumps(d,indent=2)+'\n')
