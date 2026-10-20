#!/usr/bin/env python3
"""Conservative balanced-current copper estimate for the partial primary route."""
import collections,hashlib,json,math,sys
from pathlib import Path
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[2]
sys.path.insert(0,str(ROOT/'tools'))
from kicad_sexpr import children,one,parse
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def key(net,layer,width,a,b):
 # KiCad's double-to-integer conversion can truncate a coordinate by 1 nm.
 # Match at 10 nm, then use the saved copper's actual lengths for arithmetic.
 return (net,layer,round(width,6),tuple(sorted((tuple(round(v,5) for v in a),tuple(round(v,5) for v in b)))))
def main():
 board=HERE/'primary-routed.kicad_pcb';record=json.loads((HERE/'route-record.json').read_text());checked=json.loads((HERE/'checks.json').read_text())
 assert sha(board)==checked['source_hashes'][str(board.relative_to(ROOT))]==record['routed_pcb_sha256']
 actual=[];lengths={}
 for s in children(parse(board.read_text()),'segment'):
  def xy(tag):
   p=one(s,tag);return [float(p[1])-100,204-float(p[2])]
  k=key(one(s,'net')[1],one(s,'layer')[1],float(one(s,'width')[1]),xy('start'),xy('end'))
  actual.append(k);lengths[k]=math.dist(xy('start'),xy('end'))
 planned=[];items=[];total=0
 for r in record['routes']:
  length=0
  for a,b in zip(r['points_local_xy'],r['points_local_xy'][1:]):
   if a!=b:
    k=key(r['net'],r['layer'],r['width_mm'],a,b);planned.append(k);length+=lengths[k]
  label=r['label']
  if label.startswith(('CSP','CSN')):current=0
  elif label.startswith(('junction1-current','junction2-current','cell','raw-top-current','raw-top-link','raw-top-short','raw-ground-link')):current=2
  elif label.startswith(('junction2-link','junction2-short')):current=0
  elif '-source-pin' in label:current=4/3
  else:current=4
  # The junction1 label includes its zero-current inter-carrier tail. Counting
  # the entire label at 2 A deliberately overestimates the balanced case.
  resistance=.0005*length/r['width_mm'];loss=current**2*resistance;total+=loss
  items.append({'label':label,'width_mm':r['width_mm'],'length_mm':length,'assumed_current_a':current,'resistance_ohm':resistance,'loss_w':loss})
 assert collections.Counter(actual)==collections.Counter(planned),'Loss dimensions differ from actual copper'
 via_r=1.724e-5*1.6/(math.pi*.4*.018)
 via_power=(3*2**2+4*4**2)*via_r/4
 result={'status':'Conservative balanced-current estimate for partial routing, not a thermal/current qualification',
 'source_hashes':{'board':sha(board),'route_record':sha(HERE/'route-record.json'),'checks':sha(HERE/'checks.json'),'calculator':sha(Path(__file__))},
 'assumed_pack_current_a':4,'assumed_each_parallel_cell_a':2,'nominal_finished_copper_um':35,
 'trace_loss_25c_nominal_w':total,'via_loss_20c_nominal_w':via_power,'total_copper_loss_nominal_w':total+via_power,
 'trace_loss_70c_minus20pct_width_w':total*1.18/.8,'per_route':items,
 'sources':['https://www.ti.com/lit/pdf/sszp640','https://jlcpcb.com/capabilities/pcb-capabilities'],
 'limits':['Not a temperature prediction, current rating or verified equal-sharing result.',
 'Entire source buses/drain tabs are conservatively charged 4 A despite branching; source pins assume equal 4/3 A.',
 'Both faces of each via bank are counted at full branch current; junction1 inter-carrier tail also counts 2 A although balanced current is zero.',
 'Four power via barrels per bank use 18um average plating, not a specified minimum.',
 'Excludes cells, holder contacts, fuse elements, solder, harnesses, shunt and protection FET losses.',
 'Signals/bypass and ground-return paths are unfinished; no complete board release is implied.']}
 (HERE/'copper-losses.json').write_text(json.dumps(result,indent=2)+'\n')
 print(json.dumps({k:v for k,v in result.items() if k not in ('per_route','source_hashes')},indent=2))
if __name__=='__main__':main()
