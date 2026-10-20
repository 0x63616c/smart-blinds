#!/usr/bin/env python3
"""Scoped copper-resistance arithmetic from actual checked route dimensions."""
import hashlib,json,math,sys
from pathlib import Path
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[2]
sys.path.insert(0,str(ROOT/'tools'))
from kicad_sexpr import parse,children,one

def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 checked=json.loads((HERE/'checks.json').read_text());board=HERE/'companion-routed.kicad_pcb'
 assert digest(board)==checked['source_hashes'][str(board.relative_to(ROOT))]
 fps={}
 for fp in children(parse(board.read_text()),'footprint'):
  props={x[1]:x[2] for x in children(fp,'property')}
  if 'atopile_address' in props:fps[props['atopile_address']]=fp
 def net(address,number):
  p=next(p for p in children(fps['carrier.'+address],'pad') if p[1]==str(number))
  n=one(p,'net');assert len(n)==2,'NativeKiCad10 expected';return str(n[1])
 unfused=[net('holder'+str(i),1) for i in (1,2,3)]
 fused=[net('fuse'+str(i),2) for i in (1,2,3)];ground=net('holder1',2)
 tracks=checked['geometry']['track_summary'];scenarios={}
 # 0.5mΩ/square: TI SSZP640. Width/tolerance/temperature sensitivity is not a thermal solution.
 for label,currents in [('balanced_2A_each_companion_cell',[2,2,2]),('cell1_carries4A_other_cells2A',[4,2,2]),('cell1_absent_other_cells2A',[0,2,2]),('all_companion_cells4A_stress_only',[4,4,4])]:
  items=[];total=0
  for track in tracks:
   n=track['net'];p,q=track['start_local_xy'],track['end_local_xy']
   if n in unfused:i=unfused.index(n);current=currents[i]
   elif n==ground:current=currents[0]
   elif n in fused:
    i=fused.index(n)
    # These links branch from the next cell's actual negative terminal at local y89.9.
    current=(currents[i]-currents[i+1]) if i<2 and min(p[1],q[1])>=89.9-1e-6 else currents[i]
   else:raise AssertionError('Unexpected current-carrying net '+n)
   resistance=.0005*track['length_mm']/track['width_mm'];power=current**2*resistance;total+=power
   items.append({'net':n,'length_mm':track['length_mm'],'width_mm':track['width_mm'],'current_a':current,'resistance_ohm':resistance,'loss_w':power})
  # Four nominal equal via barrels per cell; conservatively count both front/back bank rails at full branch current above.
  via_one=1.724e-5*1.6/(math.pi*.4*.018)
  via_loss=sum(i*i*(via_one/4) for i in currents)
  scenarios[label]={'companion_cell_currents_a':currents,'middle_link_currents_a':[currents[0]-currents[1],currents[1]-currents[2]],
  'trace_loss_25c_nominal_w':total,'via_loss_20c_nominal_w':via_loss,'total_copper_loss_nominal_w':total+via_loss,
  'trace_loss_70c_and_minus20pct_width_w':total*1.18/0.8,'per_segment':items}
 balanced=scenarios['balanced_2A_each_companion_cell']
 result={'status':'Scoped resistance/loss estimate, not current rating or temperature prediction',
 'sources':{'ti_sheet_resistance':'https://www.ti.com/lit/pdf/sszp640','jlc_average_barrel_and_width_tolerance':'https://jlcpcb.com/capabilities/pcb-capabilities'},
 'source_hashes':{'pcb':digest(board),'checks':digest(HERE/'checks.json'),'calculator':digest(Path(__file__))},
 'finished_copper_nominal_um':35,'trace_total_length_mm':sum(t['length_mm'] for t in tracks),
 'balanced_companion_series_path_voltage_loss_v':balanced['total_copper_loss_nominal_w']/2,
 'scenarios':scenarios,
 'limits':['Each scenario prescribes cell currents; copper geometry does not establish equal current sharing.',
 '4A branch cases are transient/fault planning only;3A branch fuses and holders are not approved for sustained4A operation.',
 '1oz sheet resistance is nominal;70C/width sensitivity is illustrative, not a solved board temperature.',
 'Via barrel calculation uses18um average plating, not a specified minimum; pads/spreading and hot spots need separate analysis.',
 'Both via-bank front/back rails are conservatively counted at full branch current, although current divides between vias.',
 'Fuse, holder, cell, solder, intercarrier wire, primary shunt/FET and connector losses are excluded.']}
 (HERE/'copper-losses.json').write_text(json.dumps(result,indent=2)+'\n')
 print(json.dumps({'series_path_drop_v':result['balanced_companion_series_path_voltage_loss_v'],'scenarios':{k:{x:y for x,y in v.items() if x!='per_segment'} for k,v in scenarios.items()}},indent=2))
if __name__=='__main__':main()
