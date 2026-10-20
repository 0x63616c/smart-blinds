"""Eight meaningful clamp faults, tested on isolated AST copies."""
import json,tempfile,copy
from pathlib import Path
import pcbnew
from kicad_sexpr import parse,dumps,children,one
from regen_checks import verify,via_lands

def run(source,m):
 data=json.loads((Path(__file__).resolve().parent/'regen-routes.json').read_text());tree=parse(source.read_text());results=[]
 def reject(name,mutate,validator=verify):
  t=copy.deepcopy(tree);mutate(t)
  with tempfile.TemporaryDirectory(prefix='regen-fault-') as tmp:
   p=Path(tmp)/'fault.kicad_pcb';p.write_text(dumps(t)+'\n');b=pcbnew.LoadBoard(str(p))
   try:
    validator(b,m) if validator is verify else validator(b)
   except AssertionError as e:results.append({'fault':name,'rejected':str(e)[:500]})
   else:raise AssertionError('Fault escaped: '+name)
 def cut(label):
  r=next(r for r in data['routes'] if r['label']==label)
  def f(t):
   targets={tuple(round(x,5) for pt in (a,c) for x in (100+pt[0],175-pt[1])) for a,c in zip(r['uvs'],r['uvs'][1:])};removed=0
   for s in list(children(t,'segment')):
    coords=tuple(round(float(x),5) for k in ('start','end') for x in one(s,k)[1:])
    if one(s,'net')[1]==r['net'] and one(s,'layer')[1]==r['layer'] and coords in targets:t.remove(s);removed+=1
   assert removed
  return f
 for label in ('series-current-bus','control-feedback-midpoint','control-ldo-output-return','control-divider-quiet-ground','control-dump-gate-drive-2','control-latch-cutoff-drive-3'):
  reject('cut '+label,cut(label))
 def bad_via(t):
  v=copy.deepcopy(next(iter(children(t,'via'))));one(v,'at')[1:]=[106.025,149.4];one(v,'net')[1]='lv';one(v,'uuid')[1]='c0dfac37-369a-4afd-b625-1cbb56910c52';t.append(v)
 reject('same-net open via drills thermal FET source solder land',bad_via,via_lands)
 def join_latch_return(t):
  s=parse('(segment (start 117.1 141.05) (end 117.1 142) (width 0.15) (layer "F.Cu") (net "lv") (uuid "808ac858-6476-4557-b7ab-563cc779766d"))');t.append(s)
 reject('latch source shares LDO bypass return',join_latch_return)
 return [r["fault"]+" rejected" for r in results]
