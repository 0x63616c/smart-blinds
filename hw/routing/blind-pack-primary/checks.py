#!/usr/bin/env python3
"""Physical copper checks for the intentionally partial primary routing study."""
import argparse,collections,copy,hashlib,json,shutil,subprocess,sys,tempfile
from pathlib import Path
import pcbnew,wx
ROOT=Path(__file__).resolve().parents[3];HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'tools'))
from generate_schematics import board_graph
from kicad_sexpr import children,one,parse,dumps
import check_footprint_clearances as CLEARANCES
SOURCE=ROOT/'hw/layouts/blind-pack-primary/primary-test/primary-test.kicad_pcb'
BOARD=HERE/'primary-routed.kicad_pcb'
MECHANICAL=ROOT/'cad/parameters/retained-interfaces.json'
APPROVED={
 'carrier.protection.shunt':([47,4],0),
 'carrier.protection.r_balance4':([73,4.5],90),
 'carrier.protection.r_charge_gate':([51,1],0),
 'carrier.protection.c_charge_gate':([51.6,7.1],0),
 'carrier.protection.r_pfail':([33.5,1],0),
 **{f'carrier.fuse{i}':([x,4],270) for i,x in enumerate((15,41,67),1)},
}
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def mm(p):return [round(pcbnew.ToMM(p.x),6),round(pcbnew.ToMM(p.y),6)]
def local(p):x,y=mm(p);return [round(x-100,6),round(204-y,6)]
def point(xy):return pcbnew.VECTOR2I(pcbnew.FromMM(100+xy[0]),pcbnew.FromMM(204-xy[1]))
def parts(b):
 result={}
 for f in b.GetFootprints():
  key=f.GetReference() if f.GetAttributes()&pcbnew.FP_BOARD_ONLY else f.GetFieldText('atopile_address')
  assert key not in result,'Duplicate component address'
  result[key]=f
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
def verify_geometry(path):
 expected=pcbnew.LoadBoard(str(SOURCE));b=pcbnew.LoadBoard(str(path));ep=parts(expected);ap=parts(b)
 assert ep.keys()==ap.keys()
 for key,f in ep.items():
  if key in APPROVED:
   xy,angle=APPROVED[key];f.SetPosition(point(xy));f.SetOrientationDegrees(angle)
  assert fp_signature(f)==fp_signature(ap[key]),'Unapproved physical pad/placement delta: '+key
 assert board_graph(SOURCE)==board_graph(path)
 assert b.GetCopperLayerCount()==2 and b.GetDesignSettings().GetBoardThickness()==pcbnew.FromMM(1.6)
 def outline(board):
  result=[]
  for s in board.GetDrawings():
   assert s.GetLayer()==pcbnew.Edge_Cuts,'Unexpected drawing or mask opening'
   result.append((s.GetShape(),mm(s.GetStart()),mm(s.GetEnd()),mm(s.GetArcMid()) if s.GetShape()==pcbnew.SHAPE_T_ARC else None,s.GetWidth()))
  return sorted(result,key=str)
 assert outline(expected)==outline(b)
 mech=json.loads(MECHANICAL.read_text())['carrier']
 ez={z.GetZoneName():z for z in expected.Zones()};az={z.GetZoneName():z for z in b.Zones()}
 assert len(az)==len(list(b.Zones())) and all(z.GetIsRuleArea() for z in b.Zones())
 assert set(az)==set(ez)|{f'FIXTURE_BACKING_NO_EXPOSED_{i}' for i in range(3)}
 for key in ez:assert zone_signature(ez[key])==zone_signature(az[key]),'Existing support/RF boundary changed'
 for i,rect in enumerate(mech['service_fixture_backing']['local_rectangles_xy']):
  z=az[f'FIXTURE_BACKING_NO_EXPOSED_{i}'];s=zone_signature(z)
  x0,y0,x1,y1=rect
  assert sorted([local(point) for point in [z.Outline().COutline(0).CPoint(i) for i in range(4)]])==sorted([[x0,y0],[x1,y0],[x1,y1],[x0,y1]])
  assert s[1:]==([pcbnew.B_Cu],False,True,True,True,False)
 relief=mech['primary_upper_wire_tail_relief']
 assert relief['removed_crossbar_contact_local_xy']==[4,94.5,82,96.5]
 assert relief['maximum_tail_and_fillet_protrusion']==1.5 and relief['nominal_tail_to_barrier_gap']==.5
 rows=[('harness',['harness_pack_positive','harness_pack_ground','harness_gauge_sda','harness_gauge_scl','harness_charger_ntc_sense','harness_charger_ntc_return']),
       ('ntc',['ntc1_sense','ntc1_return','ntc2_sense','ntc2_return','charger_ntc_sense','charger_ntc_return'])]
 for prefix,names in rows:
  for x,name in zip(relief[prefix+'_pad_local_x'],names):
   pads=list(ap['carrier.'+name].Pads());assert len(pads)==1;p=pads[0]
   assert local(p.GetPosition())==[x,relief[prefix+'_pad_local_y']]
   assert p.GetShape()==pcbnew.PAD_SHAPE_CIRCLE and mm(p.GetSize())==[relief[prefix+'_pad_diameter']]*2
   assert p.GetAttribute()==pcbnew.PAD_ATTRIB_PTH
 manifest=json.loads((ROOT/'hw/placement/footprint-clearances.json').read_text())
 envelopes={e['compiled_alias']:CLEARANCES.bounds(parse((ROOT/e['source']).read_text()),e) for e in manifest['footprints']}
 courts=CLEARANCES.check_board('primary',path,envelopes)
 tree=parse(path.read_text());ids=[]
 def walk(v):
  if isinstance(v,list):
   if v and v[0]=='uuid':ids.append(v[1])
   for x in v:walk(x)
 walk(tree);assert len(ids)==len(set(ids)),'Duplicate UUID'
 for fp in children(tree,'footprint'):
  for kind in ('fp_line','fp_rect','fp_poly','fp_circle','fp_arc','fp_text','property'):
   assert not any(one(g,'layer')[1]=='B.Mask' for g in children(fp,kind) if children(g,'layer'))
 for track in children(tree,'segment'):
  assert not children(track,'has_solder_mask') and not children(track,'solder_mask_margin')
 return b,{'electrical_footprints':50,'board_only_holes':4,'courtyards':courts,'unique_uuids':len(ids),'mechanical_tail_rows':12}

def copper_components(b,netname,omit_pad=None):
 """Connected shapes on actual copper, not shared net names or ratsnest edges."""
 nodes=[]
 for f in b.GetFootprints():
  if f.GetAttributes()&pcbnew.FP_BOARD_ONLY:continue
  address=f.GetFieldText('atopile_address')
  for index,p in enumerate(f.Pads()):
   if p.GetNetname()!=netname or (address,p.GetNumber())==omit_pad:continue
   layers=[layer for layer in (pcbnew.F_Cu,pcbnew.B_Cu) if p.IsOnLayer(layer)]
   nodes.append({'key':('pad',address,p.GetNumber(),index),'item':p,'shapes':{l:p.GetEffectiveShape(l) for l in layers}})
 for t in b.GetTracks():
  if t.GetNetname()!=netname:continue
  layers=[pcbnew.F_Cu,pcbnew.B_Cu] if isinstance(t,pcbnew.PCB_VIA) else [t.GetLayer()]
  assert all(l in (pcbnew.F_Cu,pcbnew.B_Cu) for l in layers)
  nodes.append({'key':('route',t.m_Uuid.AsString()),'item':t,'shapes':{l:t.GetEffectiveShape(l) for l in layers}})
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

def verify_current_and_kelvin(b):
 p=parts(b)
 def net(a,n):return next(x.GetNetname() for x in p['carrier.'+a].Pads() if x.GetNumber()==str(n))
 def contains(group,a,n):return any(k[:3]==('pad','carrier.'+a,str(n)) for k in group)
 def contains_all(group,a,n):
  expected=sum(x.GetNumber()==str(n) for x in p['carrier.'+a].Pads())
  return sum(k[:3]==('pad','carrier.'+a,str(n)) for k in group)==expected
 paths=[
  [('holder1',1),('fuse1',1)],[('holder2',1),('fuse2',1)],[('holder3',1),('fuse3',1)],
  [('fuse1',2),('holder2',2),('link_junction1',1)],
  [('fuse2',2),('holder3',2),('link_junction2',1)],
  [('fuse3',2),('link_raw_top',1),*[(f'protection.charge_fet',n) for n in (1,2,3)]],
  [('holder1',2),('link_raw_ground',1),('protection.shunt',1)],
  [('protection.shunt',2),('harness_pack_ground',1)],
  [('harness_pack_positive',1),*[(f'protection.discharge_fet',n) for n in (1,2,3)]],
  [*[(f'protection.{f}_fet',n) for f in ('charge','discharge') for n in (5,6,7,8,9)]],
 ]
 for path in paths:
  groups=copper_components(b,net(*path[0]))
  assert any(all(contains_all(g,a,n) for a,n in path) for g in groups),'Disconnected physical current path: '+str(path)
 kelvin={}
 for pin,shunt,label in ((15,1,'CSP'),(14,2,'CSN')):
  n=net('protection.gauge',pin)
  full=copper_components(b,n)
  assert any(contains(g,'protection.gauge',pin) and contains(g,'protection.shunt',shunt) for g in full),label+' open'
  removed=copper_components(b,n,('carrier.protection.shunt',str(shunt)))
  sense=next(g for g in removed if contains(g,'protection.gauge',pin))
  attached=[k for k in sense if k[0]=='pad']
  assert len(attached)==1 and attached[0][1:3]==('carrier.protection.gauge',str(pin)),label+' joins another pad before its shunt land'
  # No load-current track can join the branch outside the removed shunt landing.
  ids={k[1] for k in sense if k[0]=='route'}
  current=[t for t in b.GetTracks() if t.m_Uuid.AsString() in ids and not isinstance(t,pcbnew.PCB_VIA) and t.GetWidth()>pcbnew.FromMM(.2)]
  assert not current,label+' joins a load-current trace before shunt'
  kelvin[label]={'physical_pads_with_shunt_land_removed':1,'route_items':len(ids)}
 return {'connected_power_paths':len(paths),'kelvin_shape_partitions':kelvin}

def run_drc(path,output):
 cli=shutil.which('kicad-cli') or '/Users/calum/.local/bin/kicad-cli'
 version=subprocess.check_output([cli,'version'],text=True).strip();assert version.startswith('10.')
 r=subprocess.run([cli,'pcb','drc','--severity-all','--all-track-errors','--format','json','--output',str(output),str(path)],capture_output=True,text=True)
 assert r.returncode==0,r.stdout+r.stderr
 report=json.loads(output.read_text())
 assert set(report['included_severities'])=={'error','warning','exclusion'}
 return version,report
def main():
 parser=argparse.ArgumentParser();parser.add_argument('--negative-tests',action='store_true');args=parser.parse_args()
 app=wx.App(False);quiet=wx.LogNull()
 readset=[SOURCE,MECHANICAL,BOARD,HERE/'route.py',HERE/'route-record.json',HERE/'checks.py',HERE/'primary-routed.kicad_pro',HERE/'primary-routed.kicad_dru',ROOT/'tools/generate_schematics.py',ROOT/'tools/kicad_sexpr.py',ROOT/'tools/check_footprint_clearances.py',ROOT/'tools/complete_courtyards.py',ROOT/'hw/placement/footprint-clearances.json']
 manifest=json.loads((ROOT/'hw/placement/footprint-clearances.json').read_text())
 readset.extend(ROOT/e['source'] for e in manifest['footprints'])
 snapshot={str(p.relative_to(ROOT)):sha(p) for p in readset}
 record=json.loads((HERE/'route-record.json').read_text())
 assert sha(SOURCE)==record['canonical_pcb_sha256'] and sha(MECHANICAL)==record['mechanical_sha256'] and sha(BOARD)==record['routed_pcb_sha256'] and sha(HERE/'route.py')==record['route_source_sha256']
 board,geometry=verify_geometry(BOARD);copper=verify_current_and_kelvin(board)
 version,report=run_drc(BOARD,HERE/'drc.json')
 counts=dict(sorted(collections.Counter(v['type'] for v in report['violations']).items()))
 holes={f.m_Uuid.AsString() for f in board.GetFootprints() if f.GetAttributes()&pcbnew.FP_BOARD_ONLY}
 missing=[]
 for v in report['violations']:
  if v['type']=='missing_courtyard':
   assert len(v['items'])==1 and v['items'][0]['uuid'] in holes
   missing.append(v['items'][0]['uuid'])
  else:assert v['type'] in {'silk_edge_clearance','silk_overlap','silk_over_copper'},v
 assert len(missing)==4 and set(missing)==holes
 ignored={v['key'] for v in report.get('ignored_checks',[])}
 required={'clearance','shorting_items','copper_edge_clearance','hole_clearance','items_not_allowed','courtyards_overlap','missing_courtyard','malformed_courtyard','footprint_type_mismatch','unconnected_items'}
 assert not ignored&required
 faults=[]
 if args.negative_tests:
  with tempfile.TemporaryDirectory(prefix='primary-kelvin-negative-') as folder:
   b=pcbnew.LoadBoard(str(BOARD));n=next(p.GetNet() for p in parts(b)['carrier.protection.gauge'].Pads() if p.GetNumber()=='15')
   t=pcbnew.PCB_TRACK(b);t.SetNet(n);t.SetLayer(pcbnew.F_Cu);t.SetWidth(pcbnew.FromMM(.2));t.SetStart(point([45.7,4]));t.SetEnd(point([45.7,8]));b.Add(t)
   try:verify_current_and_kelvin(b)
   except AssertionError:faults.append('same_net_early_Kelvin_join_rejected_by_copper_shape_graph')
   else:raise AssertionError('Same-net Kelvin shortcut accepted')
   b=pcbnew.LoadBoard(str(BOARD))
   t=next(t for t in b.GetTracks() if not isinstance(t,pcbnew.PCB_VIA) and local(t.GetStart())==[29,5.3] and local(t.GetEnd())==[45.7,5.3])
   b.Remove(t)
   try:verify_current_and_kelvin(b)
   except AssertionError:faults.append('open_Kelvin_route_rejected')
   else:raise AssertionError('Open Kelvin route accepted')
 assert snapshot=={k:sha(ROOT/k) for k in snapshot},'Sources changed during checks'
 result={'status':'EXPERIMENTAL PARTIAL: current paths and isolated Kelvin copper checked; signal/bypass routing incomplete','source_hashes':snapshot,'kicad_version':version,'geometry':geometry,'copper':copper,
 'drc':{'remaining_violations':counts,'unconnected_items':len(report['unconnected_items']),'ignored_checks':sorted(ignored)},'negative_controls':faults,
 'limits':['Not a complete route or fabrication release; all unconnected findings are retained.','Narrow current fanouts/1.5mm link necks and actual holders, fuses, shunt and FETs need thermal/fault qualification.','Gauge bypass/filter/ground-return and communication routes remain unfinished.','The independent Kelvin check uses actual pad/track/via shapes and removes each shunt landing; a shared net name alone cannot pass it.','Primary solder tails use the newly coordinated spacer removal; the 0.5mm barrier gap is nominal and requires physical inspection.']}
 (HERE/'checks.json').write_text(json.dumps(result,indent=2)+'\n')
 print(json.dumps({k:v for k,v in result.items() if k not in ('source_hashes','geometry')},indent=2))
if __name__=='__main__':main()
