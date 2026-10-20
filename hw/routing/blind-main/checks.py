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
 plan=json.loads((HERE/'placement.json').read_text())['placements'];plan.update(json.loads((HERE/'usb-data-routes.json').read_text())['final_placement']);plan.update(json.loads((HERE/'local-supervision-routes.json').read_text())['final_placement']);assert ep.keys()==ap.keys()==plan.keys()
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
 assert len(ez)==13 and set(az)==set(ez)|{'TRIAL_IN1_GND_RETURN','USB_LOCAL_IN2_RETURN'}
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
 [('usb.pd',21),('usb.c_1v2',1)], [('usb.pd',23),('usb.c_2v7',1)],
 [('usb.pd',24),('usb.c_vdd',1),('usb.d_vdd',1)],
 [('usb.efuse',7),('usb.c_slew',1)],[('usb.efuse',9),('usb.r_limit',1)],
 [('usb.efuse',1),('usb.r_uv_bottom',1)],[('usb.efuse',2),('usb.r_ov_bottom',1)],
 [('controller.mcu',14),('controller.r_dp',1)],[('controller.mcu',13),('controller.r_dm',1)],
 [('usb.connector','A4B9'),('usb.connector','B4A9'),('usb.efuse',5),('usb.c_raw',1),('usb.tvs_vbus',1),('usb.d_vdd',2)],
 [('usb.efuse',6),('charger.c_input2',1)],
 [('usb.connector','A5'),('usb.tvs_cc',1),('usb.pd',1),('usb.pd',2)],
 [('usb.connector','B5'),('usb.tvs_cc',2),('usb.pd',4),('usb.pd',5)],
 [('usb.efuse',8),('usb.r_uv_bottom',2),('usb.r_ov_bottom',2),('usb.c_slew',2),('usb.r_limit',2),
  ('usb.c_raw',2),('usb.tvs_vbus',2),('charger.c_input2',2),('usb.pd',10),('usb.pd',22),('usb.pd',25),
  ('usb.c_vdd',2),('usb.c_1v2',2),('usb.c_2v7',2),('usb.tvs_cc',3),('controller.usb_esd',1),('controller.usb_esd',2),('controller.usb_esd',4),
  *[('usb.connector',n) for n in ('1','2','3','4','A1B12','B1A12')]],

 [('usb.d_vdd',2),('usb.q_enable',2),('usb.r_base_pull',1),('usb.r_ov_top1',1),('usb.r_raw_dis1',1)],
 [('usb.q_enable',1),('usb.r_base_pull',2),('usb.r_base1',1)],
 [('usb.r_base1',2),('usb.r_base2',1)],
 [('usb.pd',16),('usb.r_base2',2)],
 [('usb.q_enable',3),('usb.r_uv_top1',1)],
 [('usb.r_uv_top1',2),('usb.r_uv_top2',1)],
 [('usb.r_uv_top2',2),('usb.r_uv_bottom',1),('usb.efuse',1)],
 [('usb.r_ov_top1',2),('usb.r_ov_top2',1)],
 [('usb.r_ov_top2',2),('usb.r_ov_bottom',1),('usb.efuse',2)],
 [('usb.r_raw_dis1',2),('usb.r_raw_dis2',1)],
 [('usb.r_raw_dis2',2),('usb.r_raw_dis3',1)],
 [('usb.pd',18),('usb.r_raw_dis3',2)],
 [('charger.c_input2',1),('usb.r_out_dis1',1)],
 [('usb.r_out_dis1',2),('usb.r_out_dis2',1)],
 [('usb.r_out_dis2',2),('usb.r_out_dis3',1)],
 [('usb.pd',9),('usb.r_out_dis3',2)],
 [('usb.pd',12),('usb.r_addr0',1)],
 [('usb.pd',13),('usb.r_addr1',1)],
 [('usb.pd',6),('usb.r_reset',1)],
 [('usb.pd',7),('usb.r_scl',1)],
 [('usb.pd',8),('usb.r_sda',1)],
 [('usb.pd',25),*[(a,2) for a in ['usb.r_addr0','usb.r_addr1','usb.r_reset','usb.r_scl','usb.r_sda']]],

 [('usb.efuse',6),('charger.c_input1',1),('charger.c_input2',1),('charger.c_input_fast',1),('charger.ic',2),('charger.ic',3)],
 [('charger.ic',29),('charger.c_pmid_fast',1),*[(f'charger.c_pmid{i}',1) for i in range(1,5)]],
 [('charger.ic',25),('charger.c_sys_fast',1),*[(f'charger.c_sys{i}',1) for i in range(1,6)]],
 [('charger.ic',27),('charger.c_input1',2),*[(f'charger.c_pmid{i}',2) for i in range(1,5)],*[(f'charger.c_sys{i}',2) for i in range(1,6)]],
 [('charger.ic',8),('charger.ic',9),('charger.c_input_fast',1)],
 [('charger.ic',18),('charger.c_batp',1),('charger.r_batp',2)],
 [('charger.ic',22),('charger.r_batp',1)],
 [('charger.ic',16),('charger.c_ts',1),('charger.r_ts_bottom',1),('charger.r_ts_top',2)],
 [('charger.ic',20),('charger.r_prog',1)],
 [('charger.ic',17),('charger.r_ilim_bottom',1),('charger.r_ilim_top',2)],
 [('charger.ic',5),('charger.r_ts_top',1),('charger.r_ilim_top',1)],
 [('charger.ic',27),('charger.c_batp',2),('charger.c_ts',2),('charger.r_prog',2),('charger.r_ts_bottom',2),('charger.r_ilim_bottom',2)],
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
 local=copper_components(b,'lv',include_planes=False)
 group=next(g for g in local if any(k[:3]==('pad','usb.efuse','8') for k in g))
 via_ids={t.m_Uuid.AsString() for t in b.GetTracks() if isinstance(t,pcbnew.PCB_VIA)}
 local_vias=[k for k in group if k[0]=='route' and k[1] in via_ids]
 assert len(local_vias)==1,'Quiet analog return must meet system ground at one via'
 assert set(k[1:3] for k in group if k[0]=='pad')=={('usb.efuse','8'),('usb.r_uv_bottom','2'),('usb.r_ov_bottom','2'),('usb.c_slew','2'),('usb.r_limit','2')},'Power/other returns enter quiet analog ground'
 return {'connected_path_groups':len(paths),'ground_fill_islands':1,'charger_bypass_ground_vias':bypass_returns,'usb_quiet_ground_vias':len(local_vias),'segments':sum(not isinstance(t,pcbnew.PCB_VIA) for t in b.GetTracks()),'vias':sum(isinstance(t,pcbnew.PCB_VIA) for t in b.GetTracks())}

def verify_distribution_lands(b):
 """Check drill-to-solder-land margin even for same-net open vias.

 Native DRC permits same-net via-in-pad. These ordinary unfilled distribution
 vias must instead leave 0.20 mm from the drill edge to every top solder land.
 The complete explicit fanout list binds this check to the generated geometry.
 """
 records=json.loads((HERE/'charger-power-banks.json').read_text())
 records=[{'address':'charger.c_input1','pin':1,'uv':[[21.1,20.35],[21.9,20.35]]},*records]
 p=parts(b);vias=[t for t in b.GetTracks() if isinstance(t,pcbnew.PCB_VIA)]
 inspected=set();probes=[]
 for record in records:
  pad=next(x for x in p[record['address']].Pads() if x.GetNumber()==str(record['pin']))
  for uv in record['uv']:
   matches=[v for v in vias if v.GetPosition()==point(uv) and v.GetNetCode()==pad.GetNetCode()]
   assert len(matches)==1,'Missing or duplicate distribution via: '+str(uv)
   v=matches[0];assert v.GetDrillValue()==pcbnew.FromMM(.3) and v.GetWidth(pcbnew.F_Cu)==pcbnew.FromMM(.6)
   assert v.m_Uuid.AsString() not in inspected;inspected.add(v.m_Uuid.AsString())
   probe=pcbnew.PCB_VIA(b);probe.SetPosition(v.GetPosition());probe.SetWidth(v.GetDrillValue());probes.append(probe)
   for f in b.GetFootprints():
    for land in f.Pads():
     if land.IsOnLayer(pcbnew.F_Cu):
      assert not probe.GetEffectiveShape(pcbnew.F_Cu).Collide(land.GetEffectiveShape(pcbnew.F_Cu),pcbnew.FromMM(.2)),'Distribution via drill too close to solder land: '+str(mm(v.GetPosition()))+' '+f.GetFieldText('atopile_address')
 assert len(inspected)==38
 return {'checked_vias':len(inspected),'minimum_drill_to_solder_land_mm':.2}

def verify_control_lands(b):
 """Ordinary unfilled control vias must also clear same-net solder lands."""
 p=parts(b);expected={}
 def add(uv,address,pin,diam=.5,drill=.25):
  pad=next(x for x in p[address].Pads() if x.GetNumber()==str(pin))
  key=(round((100+uv[0])*1e6),round((175-uv[1])*1e6))
  value=(pad.GetNetCode(),diam,drill)
  assert key not in expected or expected[key]==value,'Conflicting control via declaration'
  expected[key]=value
 for row in json.loads((HERE/'charger-control-routes.json').read_text()):
  for a,c in zip(row['path'],row['path'][1:]):
   if a[2]!=c[2]:
    assert a[:2]==c[:2];add(a[:2],*row['start'])
 add([24.7,21.4],'charger.ic',8)
 add([35.2,24.15],'charger.c_boot2',2,.6,.3)
 assert len(expected)==17,'Expected sixteen added and one relocated control-area vias'
 removed_ntc=(137400000,150600000)
 assert removed_ntc in expected
 old_net,old_diam,old_drill=expected.pop(removed_ntc)
 assert not any(isinstance(v,pcbnew.PCB_VIA) and v.GetPosition()==pcbnew.VECTOR2I(*removed_ntc) and v.GetNetCode()==old_net for v in b.GetTracks()),'Obsolete NTC via restored'
 assert len(expected)==16
 probes=[]
 for (x,y),(net,diam,drill) in expected.items():
  matches=[v for v in b.GetTracks() if isinstance(v,pcbnew.PCB_VIA) and v.GetPosition()==pcbnew.VECTOR2I(x,y) and v.GetNetCode()==net]
  assert len(matches)==1,'Missing or duplicate control via'
  v=matches[0];assert v.GetWidth(pcbnew.F_Cu)==round(diam*1e6) and v.GetDrillValue()==round(drill*1e6)
  probe=pcbnew.PCB_VIA(b);probe.SetPosition(v.GetPosition());probe.SetWidth(v.GetDrillValue());probes.append(probe)
  for f in b.GetFootprints():
   for land in f.Pads():
    if land.IsOnLayer(pcbnew.F_Cu):
     assert not probe.GetEffectiveShape(pcbnew.F_Cu).Collide(land.GetEffectiveShape(pcbnew.F_Cu),200000),'Control via drill too close to solder land'
 return {'checked_vias':len(expected),'minimum_drill_to_solder_land_mm':.2}

def verify_all_via_lands(b):
 """Keep every ordinary route drill away from every top solder land."""
 probes=[];count=0
 for via in b.GetTracks():
  if not isinstance(via,pcbnew.PCB_VIA):continue
  probe=pcbnew.PCB_VIA(b);probe.SetPosition(via.GetPosition());probe.SetWidth(via.GetDrillValue());probes.append(probe)
  for footprint in b.GetFootprints():
   for land in footprint.Pads():
    if land.IsOnLayer(pcbnew.F_Cu):
     assert not probe.GetEffectiveShape(pcbnew.F_Cu).Collide(land.GetEffectiveShape(pcbnew.F_Cu),200000),'Ordinary via drill too close to solder land'
  count+=1
 assert count==257,'Unexpected ordinary via inventory'
 return {'checked_vias':count,'minimum_drill_to_solder_land_mm':.2,'scope':'All route vias, including same-net lands; footprint thermal holes require separate process review'}

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
 readset=[BOARD,BOARD.with_suffix('.kicad_pro'),HERE/'checks.py',HERE/'regen_checks.py',HERE/'regen_faults.py',HERE/'regen_analog.py',HERE/'usb_data_checks.py',HERE/'usb_data_faults.py',HERE/'local_supervision_checks.py',HERE/'local_supervision_faults.py',HERE/'fp-lib-table',ROOT/'cad/parameters/retained-interfaces.json',*[ROOT/p for p in record['source_hashes']]]
 snapshot={str(p.relative_to(ROOT)):sha(p) for p in readset}
 b,geometry=verify_geometry(BOARD);copper=verify_copper(b);copper['distribution_via_solder_land_margin']=verify_distribution_lands(b);copper['control_via_solder_land_margin']=verify_control_lands(b);copper['all_route_via_solder_land_margin']=verify_all_via_lands(b);from regen_checks import verify as verify_regen, verify_layout as verify_regen_layout;copper['regenerative_clamp']=verify_regen(b,sys.modules[__name__]);copper['regenerative_clamp_layout']=verify_regen_layout(b,sys.modules[__name__]);from usb_data_checks import verify as verify_usb;copper['usb_data']=verify_usb(b,sys.modules[__name__]);from local_supervision_checks import verify as verify_local;copper['local_supervision']=verify_local(b,sys.modules[__name__]);version,report=run_drc(BOARD);drc=verify_drc(b,report);faults=[]
 if args.negative_tests:
  negative_boards=[];removed_items=[]
  with tempfile.TemporaryDirectory() as d:
   changed=Path(d)/'changed.kicad_pcb'
   for mode,a,pin in [('cut_vac_sense','charger.ic',9),('cut_batp_sense','charger.ic',18),('cut_ilim_input','charger.ic',17),('cut_ts_return','charger.c_ts',2),('cut_prog_input','charger.ic',20),('cut_usb_charger_feed','charger.c_input_fast',1),('cut_pmid_bulk','charger.c_pmid4',1),('cut_sys_bulk','charger.c_sys5',1),('cut_input_ground','charger.c_input1',2)]:
    bad=pcbnew.LoadBoard(str(BOARD));negative_boards.append(bad)
    pad=next(p for p in parts(bad)[a].Pads() if p.GetNumber()==str(pin))
    selected=[t for t in bad.GetTracks() if (isinstance(t,pcbnew.PCB_VIA) or t.GetLayer()==pcbnew.F_Cu) and t.GetNetCode()==pad.GetNetCode() and t.GetEffectiveShape(pcbnew.F_Cu).Collide(pad.GetEffectiveShape(pcbnew.F_Cu),0)]
    assert selected,(mode,'No physical branch')
    for t in selected:removed_items.append(t);bad.Remove(t)
    try:verify_copper(bad)
    except AssertionError:faults.append(mode+'_rejected')
    else:raise AssertionError('Accepted distribution open: '+mode)
   bad=pcbnew.LoadBoard(str(BOARD));negative_boards.append(bad)
   via=next(t for t in bad.GetTracks() if isinstance(t,pcbnew.PCB_VIA) and t.GetPosition()==point([49.85,19.06]))
   pad=next(p for p in parts(bad)['charger.c_sys5'].Pads() if p.GetNumber()=='1')
   pad.SetPosition(via.GetPosition())
   try:verify_distribution_lands(bad)
   except AssertionError as error:
    assert 'Distribution via drill too close to solder land' in str(error),error
    faults.append('same_net_open_via_in_solder_land_rejected')
   else:raise AssertionError('Accepted distribution via in solder land')
   bad=pcbnew.LoadBoard(str(BOARD));negative_boards.append(bad)
   via=next(t for t in bad.GetTracks() if isinstance(t,pcbnew.PCB_VIA) and t.GetPosition()==pcbnew.VECTOR2I(124700000,153600000))
   pad=next(p for p in parts(bad)['charger.ic'].Pads() if p.GetNumber()=='8');pad.SetPosition(via.GetPosition())
   try:verify_control_lands(bad)
   except AssertionError as error:
    assert 'Control via drill too close to solder land' in str(error),error
    faults.append('same_net_control_via_in_solder_land_rejected')
   else:raise AssertionError('Accepted control via in solder land')
   bad=pcbnew.LoadBoard(str(BOARD));negative_boards.append(bad)
   pad=next(p for p in parts(bad)['usb.c_raw'].Pads() if p.GetNumber()=='2')
   via=next(t for t in bad.GetTracks() if isinstance(t,pcbnew.PCB_VIA) and t.GetPosition()==pcbnew.VECTOR2I(120850000,164400000))
   assert via.GetNetCode()==pad.GetNetCode();via.SetPosition(pad.GetPosition())
   try:verify_all_via_lands(bad)
   except AssertionError as error:
    assert 'Ordinary via drill too close to solder land' in str(error),error
    faults.append('same_net_existing_via_in_solder_land_rejected')
   else:raise AssertionError('Accepted existing ordinary via in solder land')
   for mode,a,pin in [('cut_pd_enable','usb.pd',16),('cut_uv_divider','usb.r_uv_top2',2),('cut_raw_discharge','usb.pd',18),('cut_address_ground','usb.r_addr0',2)]:
    bad=pcbnew.LoadBoard(str(BOARD));negative_boards.append(bad)
    pad=next(p for p in parts(bad)[a].Pads() if p.GetNumber()==str(pin))
    selected=[t for t in bad.GetTracks() if not isinstance(t,pcbnew.PCB_VIA) and t.GetLayer()==pcbnew.F_Cu and t.GetNetCode()==pad.GetNetCode() and t.GetEffectiveShape(pcbnew.F_Cu).Collide(pad.GetEffectiveShape(pcbnew.F_Cu),0)]
    assert selected,(mode,'No physical branch')
    for t in selected:removed_items.append(t);bad.Remove(t)
    try:verify_copper(bad)
    except AssertionError:faults.append(mode+'_rejected')
    else:raise AssertionError('Accepted USB control open: '+mode)
   for mode in ['move_usb','alter_pad','alter_rf']:
    bad=pcbnew.LoadBoard(str(BOARD));negative_boards.append(bad);ps=parts(bad)
    if mode=='move_usb':ps['usb.connector'].Move(pcbnew.VECTOR2I(pcbnew.FromMM(.5),0))
    elif mode=='alter_pad':next(iter(ps['motor.ic'].Pads())).SetSize(pcbnew.VECTOR2I(pcbnew.FromMM(1),pcbnew.FromMM(1)))
    else:next(z for z in bad.Zones() if z.GetIsRuleArea()).SetDoNotAllowTracks(False)
    pcbnew.SaveBoard(str(changed),bad)
    try:verify_geometry(changed)
    except AssertionError:faults.append(mode+'_rejected')
    else:raise AssertionError('Accepted injected geometry fault: '+mode)
   for mode in ['cut_module_supply','remove_return_plane','cut_regn_bypass_return','cut_pd_bypass','cut_usb_input','remove_usb_quiet_return','join_usb_quiet_to_input_return']:
    bad=pcbnew.LoadBoard(str(BOARD));negative_boards.append(bad)
    if mode=='remove_return_plane':
     zone=next(z for z in bad.Zones() if not z.GetIsRuleArea());removed_items.append(zone);bad.Remove(zone)
    elif mode=='cut_regn_bypass_return':
     cap=next(p for p in parts(bad)['charger.c_regn'].Pads() if p.GetNumber()=='2')
     selected=[t for t in bad.GetTracks() if not isinstance(t,pcbnew.PCB_VIA) and (t.GetStart()==cap.GetPosition() or t.GetEnd()==cap.GetPosition())];assert len(selected)==2
     for t in selected:removed_items.append(t);bad.Remove(t)
    elif mode=='cut_module_supply':
     selected=[t for t in bad.GetTracks() if not isinstance(t,pcbnew.PCB_VIA) and t.GetLayer()==pcbnew.In2_Cu and abs(pcbnew.ToMM(t.GetLength())-16.19)<.001];assert len(selected)==1
     removed_items.append(selected[0]);bad.Remove(selected[0])
    elif mode=='cut_pd_bypass':
     cap=next(p for p in parts(bad)['usb.c_1v2'].Pads() if p.GetNumber()=='1')
     selected=[t for t in bad.GetTracks() if not isinstance(t,pcbnew.PCB_VIA) and (t.GetStart()==cap.GetPosition() or t.GetEnd()==cap.GetPosition())];assert len(selected)==1
     removed_items.append(selected[0]);bad.Remove(selected[0])
    elif mode=='cut_usb_input':
     selected=[t for t in bad.GetTracks() if not isinstance(t,pcbnew.PCB_VIA) and t.GetLayer()==pcbnew.B_Cu and {tuple(mm(t.GetStart())),tuple(mm(t.GetEnd()))}=={(126.6,169.2),(124.8,169.2)}];assert len(selected)==1
     removed_items.append(selected[0]);bad.Remove(selected[0])
    elif mode=='remove_usb_quiet_return':
     selected=[t for t in bad.GetTracks() if isinstance(t,pcbnew.PCB_VIA) and mm(t.GetPosition())==[128.4,166.23]];assert len(selected)==1
     removed_items.append(selected[0]);bad.Remove(selected[0])
    elif mode=='join_usb_quiet_to_input_return':
     fp=parts(bad);a=next(p for p in fp['usb.efuse'].Pads() if p.GetNumber()=='8');c=next(p for p in fp['usb.c_raw'].Pads() if p.GetNumber()=='2')
     bridge=pcbnew.PCB_TRACK(bad);bridge.SetStart(a.GetPosition());bridge.SetEnd(c.GetPosition());bridge.SetLayer(pcbnew.F_Cu);bridge.SetWidth(pcbnew.FromMM(.2));bridge.SetNetCode(a.GetNetCode());bad.Add(bridge)
    try:verify_copper(bad)
    except AssertionError:faults.append(mode+'_rejected')
    else:raise AssertionError('Accepted physical copper fault: '+mode)
 if args.negative_tests:
  from regen_faults import run as regen_faults
  faults.extend(regen_faults(BOARD,sys.modules[__name__]))
  from usb_data_faults import run as usb_faults
  faults.extend(usb_faults(BOARD,sys.modules[__name__]))
  from local_supervision_faults import run as local_faults
  faults.extend(local_faults(BOARD,sys.modules[__name__]))
 assert snapshot=={p:sha(ROOT/p) for p in snapshot},'Sources changed during verification'
 result={'status':'Partial route only; no manufacturing or physical acceptance','source_hashes':{**record['source_hashes'],'hw/routing/blind-main/main-routed.kicad_pcb':sha(BOARD),'hw/routing/blind-main/checks.py':sha(HERE/'checks.py'),'cad/parameters/retained-interfaces.json':sha(ROOT/'cad/parameters/retained-interfaces.json')},'kicad_version':version,'geometry':geometry,'copper':copper,'drc':drc,'negative_controls':faults}
 (HERE/'drc.json').write_text(json.dumps(report,indent=2)+'\n');(HERE/'checks.json').write_text(json.dumps(result,indent=2)+'\n')
 print(json.dumps({'copper':copper,'drc':drc,'negative_controls':faults},indent=2))
if __name__=='__main__':main()
