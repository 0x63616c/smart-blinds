#!/usr/bin/env python3
"""Independent geometry/DRC checks of the experimental nativeKiCad10 route."""
import argparse,collections,copy,hashlib,json,math,shutil,subprocess,sys,tempfile
from pathlib import Path
import pcbnew,wx
ROOT=Path(__file__).resolve().parents[3];HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'tools'))
from generate_schematics import board_graph
import check_footprint_clearances as CLEARANCES
from kicad_sexpr import children,one,parse,dumps,node,Atom
SOURCE=ROOT/'hw/layouts/blind-pack-companion/companion-test/companion-test.kicad_pcb'
BOARD=HERE/'companion-routed.kicad_pcb';MECHANICAL=ROOT/'cad/parameters/retained-interfaces.json'

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def xy(p):return [round(pcbnew.ToMM(p.x),6),round(pcbnew.ToMM(p.y),6)]
def local(p):x,y=xy(p);return [186-x,204-y]
def box(vertices):return [min(p[0] for p in vertices),min(p[1] for p in vertices),max(p[0] for p in vertices),max(p[1] for p in vertices)]
def intersect(a,b):return min(a[2],b[2])-max(a[0],b[0])>1e-6 and min(a[3],b[3])-max(a[1],b[1])>1e-6

def zone_signature(z):
 p=z.Outline();assert p.OutlineCount()==1
 return {'points':[[p.COutline(0).CPoint(i).x,p.COutline(0).CPoint(i).y] for i in range(p.COutline(0).PointCount())],
 'layers':list(z.GetLayerSet().Seq()),'track':z.GetDoNotAllowTracks(),'via':z.GetDoNotAllowVias(),'pad':z.GetDoNotAllowPads(),'fill':z.GetDoNotAllowZoneFills(),'footprint':z.GetDoNotAllowFootprints()}

def pad_signature(p):
 return (p.GetNumber(),p.GetAttribute(),p.GetShape(),xy(p.GetPosition()),xy(p.GetSize()),round(p.GetOrientationDegrees()%360,6),
         p.GetDrillShape(),xy(p.GetDrillSize()),xy(p.GetOffset()),list(p.GetLayerSet().Seq()),p.GetNetname())

def fp_signature(f):
 return {'id':str(f.GetFPID().GetLibNickname())+':'+str(f.GetFPID().GetLibItemName()),'position':xy(f.GetPosition()),'rotation':round(f.GetOrientationDegrees()%360,6),'layer':f.GetLayer(),
 'attributes':f.GetAttributes(),'pads':sorted([pad_signature(p) for p in f.Pads()],key=str)}

def footprints(b):
 out={}
 for f in b.GetFootprints():
  key=f.GetReference() if f.GetAttributes()&pcbnew.FP_BOARD_ONLY else f.GetFieldText('atopile_address')
  assert key not in out,'Duplicate footprint identity'
  out[key]=f
 return out

def verify_geometry(path):
 expected=pcbnew.LoadBoard(str(SOURCE));actual=pcbnew.LoadBoard(str(path));mech=json.loads(MECHANICAL.read_text())['carrier']
 assert mech['companion_upper_support_trace_relief']['allowed_track_band_local_xy']==[9,94,77,97]
 assert mech['companion_upper_support_trace_relief']['spacer_recess_depth']==.3
 e=footprints(expected);a=footprints(actual)
 assert set(e)==set(a)
 for key in e:
  if key in {'carrier.fuse1','carrier.fuse2','carrier.fuse3'}:e[key].SetOrientationDegrees(270)
  assert fp_signature(e[key])==fp_signature(a[key]),'Unapproved footprint/pad delta: '+key
 assert board_graph(SOURCE)==board_graph(path),'Physical pin/net graph changed'
 manifest=json.loads((ROOT/'hw/placement/footprint-clearances.json').read_text())
 envelopes={e['compiled_alias']:CLEARANCES.bounds(parse((ROOT/e['source']).read_text()),e) for e in manifest['footprints']}
 court=CLEARANCES.check_board('companion',path,envelopes)
 assert actual.GetCopperLayerCount()==2 and actual.GetDesignSettings().GetBoardThickness()==pcbnew.FromMM(1.6)
 # Board outline and any non-footprint mask opening are explicit review boundaries.
 def drawings(b):
  result=[]
  for s in b.GetDrawings():
   assert s.GetLayer()==pcbnew.Edge_Cuts,'Unreviewed drawing/mask opening'
   result.append((s.GetShape(),xy(s.GetStart()),xy(s.GetEnd()),xy(s.GetArcMid()) if s.GetShape()==pcbnew.SHAPE_T_ARC else None,s.GetWidth()))
  return sorted(result,key=str)
 assert drawings(expected)==drawings(actual),'Board outline changed'
 ez={z.GetZoneName():z for z in expected.Zones()};az={z.GetZoneName():z for z in actual.Zones()}
 assert len(az)==len(list(actual.Zones())),'Duplicate rule area'
 assert all(z.GetIsRuleArea() for z in actual.Zones()),'This route deliberately has no copper fills'
 for name,z in ez.items():
  sig=zone_signature(z)
  if name=='UPPER_SUPPORT':sig['layers']=[pcbnew.F_Cu]
  assert name in az and zone_signature(az[name])==sig,'Existing support/RF area changed: '+name
 new={'UPPER_SUPPORT_BACK_LEFT':([4,94,9,97],True),'UPPER_SUPPORT_BACK_RIGHT':([77,94,82,97],True),
      'UPPER_SUPPORT_BACK_COVERED_TRACKS':([9,94,77,97],False)}
 for i,b in enumerate(mech['service_fixture_backing']['local_rectangles_xy']):new[f'FIXTURE_BACKING_NO_EXPOSED_{i}']=(b,False)
 assert set(az)==set(ez)|set(new),'Rule-area membership changed'
 for name,(bounds,forbid_track) in new.items():
  z=az[name];sig=zone_signature(z);poly=z.Outline().COutline(0)
  pts=[local(poly.CPoint(i)) for i in range(poly.PointCount())];x0,y0,x1,y1=bounds
  assert sorted(pts)==sorted([[x0,y0],[x1,y0],[x1,y1],[x0,y1]])
  assert sig['layers']==[pcbnew.B_Cu] and sig['track']==forbid_track and sig['via'] and sig['pad'] and sig['fill'] and not sig['footprint'],name
 tree=parse(path.read_text())
 ids=[]
 def collect(value):
  if isinstance(value,list):
   if value and value[0]=='uuid':ids.append(value[1])
   for child in value:collect(child)
 collect(tree)
 assert len(ids)==len(set(ids)),'Duplicate item UUIDs corrupt DRC instance attribution'
 # PCB tracks are mask-covered unless explicit mask openings or enabled exposure are added.
 for fp in children(tree,'footprint'):
  assert not any(one(g,'layer')[1]=='B.Mask' for kind in ('fp_line','fp_rect','fp_poly','fp_circle','fp_arc','fp_text','property') for g in children(fp,kind) if children(g,'layer')),'Unreviewed footprint mask graphic'
 for s in children(tree,'segment'):
  assert not children(s,'solder_mask_margin') and not children(s,'has_solder_mask'),'Exposed track option added'
 band=[9,94,77,97];covered_nets=set();vias=0;tracks=[]
 for t in actual.GetTracks():
  if isinstance(t,pcbnew.PCB_VIA):
   vias+=1;assert t.IsTented(pcbnew.F_Cu) and t.IsTented(pcbnew.B_Cu),'Via no longer tented'
   assert t.GetWidth(pcbnew.F_Cu)==pcbnew.FromMM(.9) and t.GetWidth(pcbnew.B_Cu)==pcbnew.FromMM(.9) and t.GetDrillValue()==pcbnew.FromMM(.4)
  else:
   assert t.GetLayer() in (pcbnew.F_Cu,pcbnew.B_Cu),'Unexpected copper layer'
   assert t.GetWidth()>=pcbnew.FromMM(2),'Current neck narrower than2mm'
   p,q=local(t.GetStart()),local(t.GetEnd());r=pcbnew.ToMM(t.GetWidth())/2
   bb=[min(p[0],q[0])-r,min(p[1],q[1])-r,max(p[0],q[0])+r,max(p[1],q[1])+r]
   if intersect(bb,band):
    assert t.GetLayer()==pcbnew.B_Cu,'Track crosses F.Cu support'
    covered_nets.add(t.GetNetname())
   tracks.append({'net':t.GetNetname(),'layer':pcbnew.LayerName(t.GetLayer()),'width_mm':pcbnew.ToMM(t.GetWidth()),'length_mm':pcbnew.ToMM(t.GetLength()),'start_local_xy':p,'end_local_xy':q})
 assert vias==12 and len(tracks)==35
 wanted={next(iter(a['carrier.'+n].Pads())).GetNetname() for n in ('link_raw_ground','link_junction1','link_junction2','link_raw_top')}
 assert covered_nets==wanted,'Four distinct raw rails must cross the recess'
 # Actual soldermask openings from pads cannot reach any backing/window band.
 for f in a.values():
  for p in f.Pads():
   if not p.IsOnLayer(pcbnew.B_Mask):continue
   rect=p.GetBoundingBox();margin=.1
   corners=[local(rect.GetOrigin()),local(rect.GetEnd())];b=box(corners);b=[b[0]-margin,b[1]-margin,b[2]+margin,b[3]+margin]
   assert not any(intersect(b,area) for area in [band]+mech['service_fixture_backing']['local_rectangles_xy']),'Pad mask opening enters a covered contact band'
 return {'footprints':len(a),'electrical_footprints':10,'board_only_holes':4,'tracks':len(tracks),'vias':vias,
 'covered_support_rail_nets':sorted(covered_nets),'copper_fill_zones':0,'courtyards':court,'unique_item_uuids':len(ids),'track_summary':tracks}

def drc(path,output):
 cli=shutil.which('kicad-cli') or '/Users/calum/.local/bin/kicad-cli'
 version=subprocess.check_output([cli,'version'],text=True).strip();assert version.startswith('10.')
 before=sha(path)
 r=subprocess.run([cli,'pcb','drc','--severity-all','--all-track-errors','--format','json','--output',str(output),str(path)],capture_output=True,text=True)
 assert r.returncode==0,r.stdout+r.stderr
 assert sha(path)==before
 report=json.loads(output.read_text());assert set(report['included_severities'])=={'error','warning','exclusion'}
 return version,report

def verify_remaining_findings(report,path):
 # Report these four inherited mechanical features explicitly. This is not a
 # blanket exemption for missing component courtyards or a fabrication waiver.
 b=pcbnew.LoadBoard(str(path));holes={}
 for f in b.GetFootprints():
  if f.GetAttributes()&pcbnew.FP_BOARD_ONLY:
   assert f.GetReference() in {'H1','H2','H3','H4'}
   assert all(p.GetAttribute()==pcbnew.PAD_ATTRIB_NPTH for p in f.Pads())
   holes[f.m_Uuid.AsString()]=f.GetReference()
 seen=[]
 for finding in report['violations']:
  if finding['type']=='missing_courtyard':
   assert len(finding['items'])==1
   uid=finding['items'][0]['uuid']
   assert uid in holes,'Purchased component courtyard missing'
   seen.append(uid)
  else:
   assert finding['type'] in {'silk_edge_clearance','silk_over_copper'},'New route DRC failure: '+str(finding)
 assert len(seen)==4 and set(seen)==set(holes),'Mechanical courtyard finding set changed'
 return sorted(holes.values())

def main():
 parser=argparse.ArgumentParser();parser.add_argument('--negative-tests',action='store_true');args=parser.parse_args()
 app=wx.App(False);quiet=wx.LogNull()
 record=json.loads((HERE/'route-record.json').read_text())
 assert sha(SOURCE)==record['canonical_pcb_sha256'] and sha(MECHANICAL)==record['mechanical_sha256'] and sha(BOARD)==record['routed_pcb_sha256']
 assert sha(HERE/'route.py')==record['route_source_sha256']
 start={str(p.relative_to(ROOT)):sha(p) for p in [SOURCE,MECHANICAL,BOARD,HERE/'route.py',HERE/'companion-routed.kicad_dru',HERE/'companion-routed.kicad_pro',HERE/'checks.py',ROOT/'hw/placement/footprint-clearances.json',ROOT/'tools/check_footprint_clearances.py',ROOT/'tools/complete_courtyards.py',ROOT/'hw/parts/blind-holders/BAT-TH_BH-21700-A5BJ001.kicad_mod',ROOT/'hw/parts/blind-carrier/FUSE-SMD_L6.1-W2.7.kicad_mod',ROOT/'hw/parts/blind-pack-features/WirePad18.kicad_mod',ROOT/'hw/parts/blind-pack-features/MountingHole_M3_3.4mm.kicad_mod']}
 geom=verify_geometry(BOARD);version,report=drc(BOARD,HERE/'drc.json')
 counts=dict(sorted(collections.Counter(x['type'] for x in report['violations']).items()))
 missing_mechanical=verify_remaining_findings(report,BOARD)
 assert not report['unconnected_items'],'Route remains unconnected'
 ignored={x['key'] for x in report.get('ignored_checks',[])}
 required={'clearance','shorting_items','copper_edge_clearance','hole_clearance','items_not_allowed','courtyards_overlap','missing_courtyard','malformed_courtyard','footprint_type_mismatch','unconnected_items'}
 assert not ignored&required,'Required DRC category disabled'
 faults=[]
 if args.negative_tests:
  with tempfile.TemporaryDirectory(prefix='companion-route-negative-') as folder:
   folder=Path(folder);base=parse(BOARD.read_text())
   # Real copper discontinuity: nominal source net labels remain unchanged.
   bad=copy.deepcopy(base);target=next(x for x in children(bad,'segment') if abs(float(one(x,'start')[2])-161.5)<1e-6 and abs(float(one(x,'end')[2])-114.1)<1e-6)
   bad.remove(target);p=folder/'open.kicad_pcb';p.write_text(dumps(bad)+'\n');shutil.copy2(HERE/'companion-routed.kicad_dru',p.with_suffix('.kicad_dru'));shutil.copy2(HERE/'companion-routed.kicad_pro',p.with_suffix('.kicad_pro'))
   _,r=drc(p,folder/'open.json');assert r['unconnected_items'];faults.append('removed_current_rail_detected_by_actual_DRC')
   # Geometry checks reject a weakened support-zone policy, independently of net labels.
   bad=copy.deepcopy(base);z=next(z for z in children(bad,'zone') if one(z,'name')[1]=='UPPER_SUPPORT_BACK_COVERED_TRACKS');one(one(z,'keepout'),'vias')[1]=Atom('allowed')
   p=folder/'permissive.kicad_pcb';p.write_text(dumps(bad)+'\n')
   try:verify_geometry(p)
   except AssertionError:faults.append('support_via_permission_rejected')
   else:raise AssertionError('Permissive support accepted')
   bad=copy.deepcopy(base);bad.append(parse('(gr_rect (start 160 108) (end 161 109) (stroke (width 0) (type default)) (fill solid) (layer "B.Mask"))'))
   p=folder/'mask.kicad_pcb';p.write_text(dumps(bad)+'\n')
   try:verify_geometry(p)
   except AssertionError:faults.append('new_soldermask_opening_rejected')
   else:raise AssertionError('Mask opening accepted')
   bad_report=copy.deepcopy(report)
   finding=next(x for x in bad_report['violations'] if x['type']=='missing_courtyard')
   finding['items'][0]['uuid']=footprints(pcbnew.LoadBoard(str(BOARD)))['carrier.fuse1'].m_Uuid.AsString()
   try:verify_remaining_findings(bad_report,BOARD)
   except AssertionError:faults.append('purchased_component_missing_courtyard_not_exempted')
   else:raise AssertionError('Component missing-courtyard finding accepted')
 assert start=={k:sha(ROOT/k) for k in start},'Inputs changed during verification'
 result={'status':'EXPERIMENTAL: connected shape-checked companion route; physical/thermal/fabrication acceptance remains open','kicad_version':version,'source_hashes':start,
 'geometry':geom,'drc':{'all_severities':report['included_severities'],'remaining_violations':counts,'missing_courtyards_board_only_NPTH':missing_mechanical,'unconnected_items':0,'ignored_checks':sorted(ignored)},'negative_controls':faults,
 'limits':['Six inherited silkscreen findings and four board-only NPTH missing-courtyard errors remain; no waivers were added.','Three unrelated KiCad checks retain their default disabled state; included severities do not enable disabled checks.','Covered B.Cu tracks use the mechanically allocated0.3mm spacer relief; printed tolerance and contact wear are unqualified.','Copper-loss estimates do not qualify current capacity, holders, fuse clearing, thermal behavior or battery assembly.','Canonical circuit and placement remain authority; only three nonpolar fuse rotations and documented rule-area deltas are approved.']}
 (HERE/'checks.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({k:v for k,v in result.items() if k!='geometry'},indent=2))
if __name__=='__main__':main()
