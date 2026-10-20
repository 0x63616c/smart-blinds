#!/usr/bin/env python3
"""Independent physical-geometry and connected-copper checks for partial main routing."""
import argparse,collections,hashlib,json,shutil,subprocess,sys,tempfile
from pathlib import Path
import pcbnew,wx
ROOT=Path(__file__).resolve().parents[3];HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'tools'))
from generate_schematics import board_graph
from kicad_sexpr import parse,children,one,dumps,walk
import check_footprint_clearances as CLEARANCES
SOURCE=ROOT/'hw/layouts/blind-main/main-test/main-test.kicad_pcb'
BOARD=HERE/'main-routed.kicad_pcb'
ANCHORS={'controller.mcu','controller.up','controller.down','usb.connector','pack_connector.header','encoder_port.header','home_port.header','motor_output.landing1','motor_output.landing2'}|{f'regen.r_dump{i}{s}' for i in range(1,5) for s in 'ab'}
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def mm(p):return [round(pcbnew.ToMM(p.x),6),round(pcbnew.ToMM(p.y),6)]
def point(uv):return pcbnew.VECTOR2I(pcbnew.FromMM(100+uv[0]),pcbnew.FromMM(175-uv[1]))
def parts(b):
 result={f.GetFieldText('atopile_address'):f for f in b.GetFootprints()}
 assert len(result)==196 and len(list(b.GetFootprints()))==196
 return result
def pad_signature(p):
 shapes=[(l,p.GetEffectiveShape(l).Format()) for l in p.GetLayerSet().Seq()]
 return (p.GetNumber(),p.GetAttribute(),p.GetShape(),mm(p.GetPosition()),mm(p.GetSize()),round(p.GetOrientationDegrees()%360,6),p.GetDrillShape(),mm(p.GetDrillSize()),mm(p.GetOffset()),list(p.GetLayerSet().Seq()),p.GetNetname(),shapes,
         p.GetLocalSolderMaskMargin(),p.GetLocalSolderPasteMargin(),p.GetLocalSolderPasteMarginRatio())
def fp_signature(f):
 return (str(f.GetFPID().GetLibNickname())+':'+str(f.GetFPID().GetLibItemName()),mm(f.GetPosition()),round(f.GetOrientationDegrees()%360,6),f.GetLayer(),f.GetAttributes(),sorted([pad_signature(p) for p in f.Pads()],key=str))
def zone_signature(z):
 poly=z.Outline();assert poly.OutlineCount()==1
 return ([mm(poly.COutline(0).CPoint(i)) for i in range(poly.COutline(0).PointCount())],list(z.GetLayerSet().Seq()),z.GetDoNotAllowTracks(),z.GetDoNotAllowVias(),z.GetDoNotAllowPads(),z.GetDoNotAllowZoneFills(),z.GetDoNotAllowFootprints())

def copper_components(b,netname,omit_pad=None,include_planes=True):
 """Connected shapes on actual copper, not shared net names or ratsnest edges."""
 nodes=[]
 for f in b.GetFootprints():
  if f.GetAttributes()&pcbnew.FP_BOARD_ONLY:continue
  address=f.GetFieldText('atopile_address')
  for index,p in enumerate(f.Pads()):
   if p.GetNetname()!=netname or (address,p.GetNumber())==omit_pad:continue
   layers=[layer for layer in (pcbnew.F_Cu,pcbnew.In1_Cu,pcbnew.In2_Cu,pcbnew.B_Cu) if p.IsOnLayer(layer)]
   nodes.append({'key':('pad',address,p.GetNumber(),index),'item':p,'shapes':{l:p.GetEffectiveShape(l) for l in layers}})
 for t in b.GetTracks():
  if t.GetNetname()!=netname:continue
  layers=[pcbnew.F_Cu,pcbnew.In1_Cu,pcbnew.In2_Cu,pcbnew.B_Cu] if isinstance(t,pcbnew.PCB_VIA) else [t.GetLayer()]
  assert all(l in (pcbnew.F_Cu,pcbnew.In1_Cu,pcbnew.In2_Cu,pcbnew.B_Cu) for l in layers)
  nodes.append({'key':('route',t.m_Uuid.AsString()),'item':t,'shapes':{l:t.GetEffectiveShape(l) for l in layers}})
 for z in b.Zones():
  if not include_planes or z.GetIsRuleArea() or z.GetNetname()!=netname:continue
  poly=z.GetFilledPolysList(z.GetLayer())
  assert poly.OutlineCount()==1,'Multiple ground islands require explicit partition handling'
  nodes.append({'key':('zone',z.GetZoneName()),'item':z,'shapes':{z.GetLayer():poly}})
 parent=list(range(len(nodes)))
 def find(i):
  while parent[i]!=i:parent[i]=parent[parent[i]];i=parent[i]
  return i
 for i,a in enumerate(nodes):
  for j in range(i):
   c=nodes[j]
   if any(a['shapes'][l].Collide(c['shapes'][l],0) for l in a['shapes'].keys()&c['shapes'].keys()):parent[find(i)]=find(j)
 groups=collections.defaultdict(list)
 for i,n in enumerate(nodes):groups[find(i)].append(n['key'])
 return list(groups.values())


def verify_geometry(path):
 expected=pcbnew.LoadBoard(str(SOURCE));b=pcbnew.LoadBoard(str(path));ep=parts(expected);ap=parts(b)
 plan=json.loads((HERE/'placement.json').read_text())['placements'];assert ep.keys()==ap.keys()==plan.keys()
 moves=[]
 for key,f in ep.items():
  target=plan[key];position=point(target['uv']);angle=target['rotation']
  if key in ANCHORS:
   assert max(abs(a-c) for a,c in zip(mm(f.GetPosition()),mm(position)))<=.000001 and f.GetOrientationDegrees()%360==angle%360,'Mechanical anchor changed: '+key
  if mm(f.GetPosition())!=mm(position) or f.GetOrientationDegrees()%360!=angle%360:moves.append(key)
  f.SetPosition(position);f.SetOrientationDegrees(angle)
  assert fp_signature(f)==fp_signature(ap[key]),'Physical pad/placement changed: '+key
 assert board_graph(SOURCE)==board_graph(path),'Electrical partition changed'
 assert b.GetCopperLayerCount()==4 and b.GetDesignSettings().GetBoardThickness()==expected.GetDesignSettings().GetBoardThickness()
 def drawings(file):
  def semantic(value):
   if not isinstance(value,list):return value
   return [semantic(v) for v in value if not (isinstance(v,list) and v and v[0]=='uuid')]
  return sorted(dumps(semantic(v)) for v in parse(file.read_text()) if isinstance(v,list) and str(v[0]).startswith('gr_'))
 assert drawings(path)==drawings(SOURCE),'Board drawing/outline changed'
 ez={z.GetZoneName():z for z in expected.Zones()};az={z.GetZoneName():z for z in b.Zones()};assert len(az)==len(list(b.Zones()))
 assert len(ez)==13 and set(az)==set(ez)|{'TRIAL_IN1_GND_RETURN'}
 for key in ez:assert az[key].GetIsRuleArea() and zone_signature(ez[key])==zone_signature(az[key]),'Keepout changed: '+key
 ground=az['TRIAL_IN1_GND_RETURN'];assert not ground.GetIsRuleArea() and ground.GetLayer()==pcbnew.In1_Cu and ground.GetNetname()=='lv'
 assert ground.GetFilledPolysList(pcbnew.In1_Cu).OutlineCount()==1
 assert not any(not isinstance(t,pcbnew.PCB_VIA) and t.GetLayer()==pcbnew.In1_Cu for t in b.GetTracks()),'Ground plane used for trace routing'
 manifest=json.loads((ROOT/'hw/placement/footprint-clearances.json').read_text())
 envelopes={e['compiled_alias']:CLEARANCES.bounds(parse((ROOT/e['source']).read_text()),e) for e in manifest['footprints']}
 courts=CLEARANCES.check_board('main',path,envelopes)
 mechanical=json.loads((ROOT/'cad/parameters/retained-interfaces.json').read_text())['controller']
 CLEARANCES.check_wire_source((ROOT/'cad/source/compact_retained.scad').read_text(),mechanical)
 wire=CLEARANCES.check_overboard_wire(path,mechanical['encoder_connector']['over_board_wire_constraint'])
 tree=parse(path.read_text());original=parse(SOURCE.read_text())
 assert dumps(one(one(tree,'setup'),'stackup'))==dumps(one(one(original,'setup'),'stackup')),'Stackup changed'
 ids=[v[1] for v in walk(tree,'uuid')];assert len(ids)==len(set(ids)),'Duplicate UUID'
 return b,{'footprints':196,'mechanical_anchors':len(ANCHORS),'moved_electrical_parts':moves,'preserved_keepouts':13,'courtyards':courts,'encoder_wire_height':wire,'unique_uuids':len(ids)}

def verify_copper(b):
 p=parts(b)
 paths=[
  [('charger.ic',29),('charger.c_pmid_fast',1),('charger.c_pmid1',1)],
  [('charger.ic',25),('charger.c_sys_fast',1),('charger.c_sys1',1)],
  [('charger.ic',28),('charger.inductor',1),('charger.c_boot1',2)],
  [('charger.ic',26),('charger.inductor',2),('charger.c_boot2',2)],
  [('charger.ic',4),('charger.c_boot1',1)], [('charger.ic',19),('charger.c_boot2',1)],
  [('charger.ic',5),('charger.c_regn',1)],
  [('charger.ic',22),('charger.ic',23),('charger.c_bat1',1),('charger.c_bat2',1)],
  [('charger.ic',2),('charger.ic',3),('charger.c_input_fast',1)],
  [('motor.ic',13),('motor.c_fly',1)],[('motor.ic',14),('motor.c_fly',2)],
  [('motor.ic',12),('motor.c_pump',1)],
  [('motor.ic',11),('motor.c_pump',2),('motor.c_vm',1),('motor.c_bulk',1)],
  [('motor.ic',8),('motor_output.landing1',1)],[('motor.ic',10),('motor_output.landing2',1)],
  [('motor.ic',5),('motor.c_ref',1),('motor.r_ref_lo',1),('motor.r_ref_hi',2)],
  [('logic_supply.ic',6),('logic_supply.c_input_fast',1),('logic_supply.c_input',1),('logic_supply.c_input2',1)],
  [('logic_supply.ic',2),('logic_supply.inductor',1)],
  [('logic_supply.inductor',2),('logic_supply.c_output1',1),('logic_supply.c_output2',1),('logic_supply.c_output_fast',1),('logic_supply.ic',3),('controller.mcu',2),('controller.c_bulk',1),('controller.c_bypass',1)],
  [('logic_supply.ic',8),('logic_supply.c_softstart',1)],
  [('logic_supply.ic',7),('logic_supply.r_mode',1)],
  [('logic_supply.ic',5),('logic_supply.r_enable',2)],
  [('logic_supply.ic',1),('logic_supply.r_pg',2)],
  [('charger.ic',27),('charger.c_pmid_fast',2),('charger.c_sys_fast',2),('charger.c_pmid1',2),('charger.c_sys1',2),('charger.c_regn',2),('charger.c_input_fast',2),('charger.c_bat1',2),('charger.c_bat2',2),
   ('motor.ic',9),('motor.ic',15),('motor.ic',17),('motor.c_vm',2),('motor.c_bulk',2),('motor.r_in1',2),('motor.r_in2',2),('motor.r_sleep',2),('motor.r_current',2),('motor.c_ref',2),('motor.r_ref_lo',2),
   ('logic_supply.ic',4),('logic_supply.c_input_fast',2),('logic_supply.c_input',2),('logic_supply.c_input2',2),('logic_supply.c_output1',2),('logic_supply.c_output2',2),('logic_supply.c_output_fast',2),('logic_supply.c_softstart',2),('logic_supply.r_mode',2),
   ('controller.mcu',1),('controller.mcu',28),*[("controller.mcu",n) for n in range(29,38)],('controller.c_bulk',2),('controller.c_bypass',2)],
 ]
 cache={}
 for path in paths:
  nets={next(x.GetNetname() for x in p[a].Pads() if x.GetNumber()==str(n)) for a,n in path};assert len(nets)==1
  net=nets.pop()
  if net not in cache:cache[net]=copper_components(b,net)
  assert any(all(sum(k[:3]==('pad',a,str(n)) for k in g)==sum(pad.GetNumber()==str(n) for pad in p[a].Pads()) for a,n in path) for g in cache[net]),'Disconnected physical copper path: '+str(path)
 local_ground=copper_components(b,'lv',include_planes=False)
 via_items={t.m_Uuid.AsString():t for t in b.GetTracks() if isinstance(t,pcbnew.PCB_VIA)}
 bypass_returns={}
 for address in ('charger.c_regn','charger.c_input_fast'):
  cap=next(pad for pad in p[address].Pads() if pad.GetNumber()=='2')
  group=next(g for g in local_ground if any(k[:3]==('pad',address,'2') for k in g))
  close_vias=[via_items[k[1]] for k in group if k[0]=='route' and k[1] in via_items and (via_items[k[1]].GetPosition()-cap.GetPosition()).EuclideanNorm()<=pcbnew.FromMM(2.5)]
  assert len(close_vias)>=2,'TI minimum two nearby ground vias not met: '+address
  bypass_returns[address]=len(close_vias)
 return {'connected_path_groups':len(paths),'ground_fill_islands':1,'charger_bypass_ground_vias':bypass_returns,'segments':sum(not isinstance(t,pcbnew.PCB_VIA) for t in b.GetTracks()),'vias':sum(isinstance(t,pcbnew.PCB_VIA) for t in b.GetTracks())}

def run_drc(path):
 cli=shutil.which('kicad-cli') or '/Applications/KiCad.app/Contents/MacOS/kicad-cli'
 version=subprocess.check_output([cli,'version'],text=True).strip();assert version.startswith('10.')
 with tempfile.TemporaryDirectory() as d:
  output=Path(d)/'drc.json';r=subprocess.run([cli,'pcb','drc','--severity-all','--all-track-errors','--format','json','-o',str(output),str(path)],capture_output=True,text=True)
  assert r.returncode==0,r.stdout+r.stderr
  report=json.loads(output.read_text())
 assert set(report['included_severities'])=={'error','warning','exclusion'}
 return version,report

def verify_drc(b,report):
 addresses={f.m_Uuid.AsString():f.GetFieldText('atopile_address') for f in b.GetFootprints()}
 allowed={'footprint_type_mismatch':{'charger.inductor','motor.ic','regen.thermostat','usb.connector','controller.mcu'},'lib_footprint_mismatch':{'home_port.header','supervision.watchdog','encoder_port.header','usb.efuse'}}
 found={k:set() for k in allowed}
 for v in report['violations']:
  assert not v.get('excluded',False),'Excluded DRC finding'
  if v['type'] in allowed:
   assert len(v['items'])==1;address=addresses[v['items'][0]['uuid']];assert address in allowed[v['type']]
   found[v['type']].add(address)
  else:assert v['type'] in {'silk_overlap','silk_over_copper','silk_edge_clearance','text_height','text_thickness'},v
 assert found==allowed
 ignored={x['key'] for x in report.get('ignored_checks',[])}
 required={'clearance','shorting_items','copper_edge_clearance','hole_clearance','items_not_allowed','courtyards_overlap','missing_courtyard','malformed_courtyard','footprint_type_mismatch','unconnected_items','track_width','via_dangling','track_dangling','solder_mask_bridge'}
 assert not ignored&required,'Required DRC category disabled'
 return {'remaining_violations':dict(sorted(collections.Counter(v['type'] for v in report['violations']).items())),'unconnected_items':len(report['unconnected_items']),'ignored_checks':sorted(ignored),'exact_inherited_footprint_findings':{k:sorted(v) for k,v in found.items()}}

def main():
 parser=argparse.ArgumentParser();parser.add_argument('--negative-tests',action='store_true');args=parser.parse_args()
 app=wx.App(False);quiet=wx.LogNull()
 record=json.loads((HERE/'route-record.json').read_text())
 for p,h in record['source_hashes'].items():assert sha(ROOT/p)==h,'Stale routing source: '+p
 assert sha(BOARD)==record['pcb_sha256'] and sha(BOARD.with_suffix('.kicad_pro'))==record['project_sha256']
 readset=[BOARD,BOARD.with_suffix('.kicad_pro'),HERE/'checks.py',HERE/'fp-lib-table',ROOT/'cad/parameters/retained-interfaces.json',*[ROOT/p for p in record['source_hashes']]]
 snapshot={str(p.relative_to(ROOT)):sha(p) for p in readset}
 b,geometry=verify_geometry(BOARD);copper=verify_copper(b);version,report=run_drc(BOARD);drc=verify_drc(b,report);faults=[]
 if args.negative_tests:
  negative_boards=[];removed_items=[]
  with tempfile.TemporaryDirectory() as d:
   changed=Path(d)/'changed.kicad_pcb'
   for mode in ['move_usb','alter_pad','alter_rf']:
    bad=pcbnew.LoadBoard(str(BOARD));negative_boards.append(bad);ps=parts(bad)
    if mode=='move_usb':ps['usb.connector'].Move(pcbnew.VECTOR2I(pcbnew.FromMM(.5),0))
    elif mode=='alter_pad':next(iter(ps['motor.ic'].Pads())).SetSize(pcbnew.VECTOR2I(pcbnew.FromMM(1),pcbnew.FromMM(1)))
    else:next(z for z in bad.Zones() if z.GetIsRuleArea()).SetDoNotAllowTracks(False)
    pcbnew.SaveBoard(str(changed),bad)
    try:verify_geometry(changed)
    except AssertionError:faults.append(mode+'_rejected')
    else:raise AssertionError('Accepted injected geometry fault: '+mode)
   for mode in ['cut_module_supply','remove_return_plane','cut_regn_bypass_return']:
    bad=pcbnew.LoadBoard(str(BOARD));negative_boards.append(bad)
    if mode=='remove_return_plane':
     zone=next(z for z in bad.Zones() if not z.GetIsRuleArea());removed_items.append(zone);bad.Remove(zone)
    elif mode=='cut_regn_bypass_return':
     cap=next(p for p in parts(bad)['charger.c_regn'].Pads() if p.GetNumber()=='2')
     selected=[t for t in bad.GetTracks() if not isinstance(t,pcbnew.PCB_VIA) and (t.GetStart()==cap.GetPosition() or t.GetEnd()==cap.GetPosition())];assert len(selected)==2
     for t in selected:removed_items.append(t);bad.Remove(t)
    else:
     selected=[t for t in bad.GetTracks() if not isinstance(t,pcbnew.PCB_VIA) and t.GetLayer()==pcbnew.In2_Cu and abs(pcbnew.ToMM(t.GetLength())-16.19)<.001];assert len(selected)==1
     removed_items.append(selected[0]);bad.Remove(selected[0])
    try:verify_copper(bad)
    except AssertionError:faults.append(mode+'_rejected')
    else:raise AssertionError('Accepted physical copper fault: '+mode)
 assert snapshot=={p:sha(ROOT/p) for p in snapshot},'Sources changed during verification'
 result={'status':'Partial route only; no manufacturing or physical acceptance','source_hashes':{**record['source_hashes'],'hw/routing/blind-main/main-routed.kicad_pcb':sha(BOARD),'hw/routing/blind-main/checks.py':sha(HERE/'checks.py'),'cad/parameters/retained-interfaces.json':sha(ROOT/'cad/parameters/retained-interfaces.json')},'kicad_version':version,'geometry':geometry,'copper':copper,'drc':drc,'negative_controls':faults}
 (HERE/'drc.json').write_text(json.dumps(report,indent=2)+'\n');(HERE/'checks.json').write_text(json.dumps(result,indent=2)+'\n')
 print(json.dumps({'copper':copper,'drc':drc,'negative_controls':faults},indent=2))
if __name__=='__main__':main()
