"""Negative controls for physical local paths, independent of native ratsnest counts."""
from pathlib import Path
import copy,json,shutil,tempfile,uuid
import pcbnew
from kicad_sexpr import parse,dumps,children,one
from local_supervision_checks import verify


def run(board,m):
 H=Path(__file__).resolve().parent
 recipes=json.loads((H/'local-supervision-routes.json').read_text())['routes']
 base=parse(board.read_text())
 def uv(n,k):return [round(float(one(n,k)[1])-100,6),round(175-float(one(n,k)[2]),6)]
 def remove_branch(tree,start,end,last=True):
  r=next(r for r in recipes if r['start']==start and r['end']==end)
  edges=[(a,c) for a,c in zip(r['path'],r['path'][1:]) if a[2]==c[2] and a[:2]!=c[:2]];a,c=edges[-1 if last else 0];layer={'F':'F.Cu','B':'B.Cu','I':'In2.Cu'}[a[2]]
  matches=[n for n in children(tree,'segment') if one(n,'net')[1]==r['net'] and one(n,'layer')[1]==layer and max(abs(x-y) for x,y in zip(uv(n,'start'),a[:2]))<.000002 and max(abs(x-y) for x,y in zip(uv(n,'end'),c[:2]))<.000002];assert len(matches)==1,(start,end,matches);tree.remove(matches[0])
 def via_intrusion(tree):
  v=copy.deepcopy(children(tree,'via')[0]);one(v,'at')[1:]=[149.89,167.2];one(v,'net')[1]='lv';one(v,'size')[1]=0.5;one(v,'drill')[1]=0.25;one(v,'uuid')[1]=str(uuid.uuid4());tree.append(v)
 def bridge(tree):
  for a,c in [([52.0,2.79375],[52.0,3.5]),([52.0,3.5],[50.1,3.5])]:
   t=copy.deepcopy(children(tree,'segment')[0]);one(t,'start')[1:]=[100+a[0],175-a[1]];one(t,'end')[1:]=[100+c[0],175-c[1]];one(t,'net')[1]='lv';one(t,'width')[1]=0.15;one(t,'layer')[1]='F.Cu';one(t,'uuid')[1]=str(uuid.uuid4());tree.append(t)
 cases=[('cut-cwd',lambda t:remove_branch(t,['supervision.watchdog',2],['supervision.c_timing',1]),'Local branch open'),('cut-encoder-output-return',lambda t:remove_branch(t,['encoder.ic',2],['encoder.c_output',2]),'Local branch open'),('cut-watchdog-to-mr',lambda t:remove_branch(t,['supervision.watchdog',8],['supervision.supervisor',3]),'Local branch open'),('cut-encoder-enable',lambda t:remove_branch(t,['encoder.gate',4],['encoder.ic',3],False),'Local branch open'),('cut-adc-divider',lambda t:remove_branch(t,['controller.c_adc',1],['controller.r_adc_hi',2]),'Local branch open'),('same-net-via-in-output-cap',via_intrusion,'Ordinary via drill too close to solder land'),('bridge-encoder-ground-away-from-star',bridge,'Encoder capacitor ground branches join outside IC GND land')]

 results=[]
 with tempfile.TemporaryDirectory() as folder:
  for name,change,expect in cases:
   tree=copy.deepcopy(base);change(tree);p=Path(folder)/(name+'.kicad_pcb');p.write_text(dumps(tree)+'\n');shutil.copyfile(board.with_suffix('.kicad_pro'),p.with_suffix('.kicad_pro'))
   b=pcbnew.LoadBoard(str(p))
   try:
    m.verify_all_via_lands(b)
    verify(b,m)
   except (AssertionError,ValueError) as error:
    assert expect in str(error),(name,'wrong failure',str(error))
    results.append('local_'+name+'_rejected')
   else:raise AssertionError('Fault escaped: '+name)
 return results
