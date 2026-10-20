#!/usr/bin/env python3
"""Deterministic experimental companion route; never edits the canonical PCB."""
import hashlib,json,math,sys,uuid
from pathlib import Path
import pcbnew,wx
ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'tools'))
from generate_schematics import board_graph
from kicad_sexpr import children,parse,dumps
HERE=Path(__file__).resolve().parent
SOURCE=ROOT/'hw/layouts/blind-pack-companion/companion-test/companion-test.kicad_pcb'
MECHANICAL=ROOT/'cad/parameters/retained-interfaces.json'
NS=uuid.UUID('9919e05a-1cce-4b6c-9d42-445b4b1a561d')

def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def point(xy):return pcbnew.VECTOR2I(pcbnew.FromMM(186-xy[0]),pcbnew.FromMM(204-xy[1]))

def main():
 app=wx.App(False);quiet=wx.LogNull()
 before=sha(SOURCE);mechanical_sha=sha(MECHANICAL)
 mech=json.loads(MECHANICAL.read_text())['carrier']
 assert mech['companion_upper_support_trace_relief']['allowed_track_band_local_xy']==[9,94,77,97]
 assert mech['companion_upper_support_trace_relief']['spacer_recess_depth']==.3
 board=pcbnew.LoadBoard(str(SOURCE))
 assert not list(board.GetTracks())
 zones=list(board.Zones());assert all(z.GetIsRuleArea() for z in zones)
 parts={f.GetFieldText('atopile_address'):f for f in board.GetFootprints() if not(f.GetAttributes()&pcbnew.FP_BOARD_ONLY)}
 assert len(parts)==10
 def pad(address,number):return next(p for p in parts['carrier.'+address].Pads() if p.GetNumber()==str(number))
 def net(address,number):return pad(address,number).GetNet()
 for i in range(1,4):
  assert parts[f'carrier.fuse{i}'].GetOrientationDegrees()==90
  parts[f'carrier.fuse{i}'].SetOrientationDegrees(270)
 # Preserve F.Cu support; only the contract's recessed B.Cu window changes.
 upper=next(z for z in zones if z.GetZoneName()=='UPPER_SUPPORT')
 layers=pcbnew.LSET();layers.AddLayer(pcbnew.F_Cu);upper.SetLayerSet(layers)
 identities={};serial=0;routes=[]
 def identity(item,label):identities[item.m_Uuid.AsString()]=str(uuid.uuid5(NS,label))
 def rule(name,box,track_forbidden):
  z=pcbnew.ZONE(board);z.SetIsRuleArea(True);z.SetZoneName(name)
  layers=pcbnew.LSET();layers.AddLayer(pcbnew.B_Cu);z.SetLayerSet(layers)
  z.SetDoNotAllowTracks(track_forbidden);z.SetDoNotAllowVias(True);z.SetDoNotAllowPads(True)
  z.SetDoNotAllowZoneFills(True);z.SetDoNotAllowFootprints(False)
  p=z.Outline();p.NewOutline();x0,y0,x1,y1=box
  for xy in ((x0,y0),(x1,y0),(x1,y1),(x0,y1)):p.Append(point(xy))
  identity(z,'rule/'+name);board.Add(z)
 rule('UPPER_SUPPORT_BACK_LEFT',[4,94,9,97],True)
 rule('UPPER_SUPPORT_BACK_RIGHT',[77,94,82,97],True)
 rule('UPPER_SUPPORT_BACK_COVERED_TRACKS',[9,94,77,97],False)
 for i,box in enumerate(mech['service_fixture_backing']['local_rectangles_xy']):
  rule(f'FIXTURE_BACKING_NO_EXPOSED_{i}',box,False)
 def track(n,layer,width,points,label):
  nonlocal serial
  for a,b in zip(points,points[1:]):
   if a==b:continue
   t=pcbnew.PCB_TRACK(board);t.SetStart(point(a));t.SetEnd(point(b));t.SetWidth(pcbnew.FromMM(width));t.SetLayer(layer);t.SetNet(n)
   identity(t,f'track/{serial}/{label}');serial+=1;board.Add(t)
  routes.append({'label':label,'net':n.GetNetname(),'layer':'F.Cu' if layer==pcbnew.F_Cu else 'B.Cu','width_mm':width,'points_local_xy':points,'length_mm':sum(math.dist(a,b) for a,b in zip(points,points[1:]))})
 def via(n,xy,label):
  v=pcbnew.PCB_VIA(board);v.SetPosition(point(xy));v.SetWidth(pcbnew.FromMM(.9));v.SetDrill(pcbnew.FromMM(.4));v.SetLayerPair(pcbnew.F_Cu,pcbnew.B_Cu);v.SetNet(n)
  identity(v,'via/'+label);board.Add(v)
 for i,x in enumerate((15,41,67),1):
  track(net(f'holder{i}',1),pcbnew.F_Cu,2,[[x,9.9],[x,6.455]],f'cell{i}-unfused-short')
  n=net(f'fuse{i}',2);vx=x+2.4
  track(n,pcbnew.F_Cu,2,[[x,1.545],[vx,1.545]],f'cell{i}-fused-via-entry')
  track(n,pcbnew.F_Cu,2,[[vx,1.4],[vx,4.1]],f'cell{i}-via-bank-front')
  track(n,pcbnew.B_Cu,2,[[vx,1.4],[vx,6.6]],f'cell{i}-via-bank-back')
  track(n,pcbnew.B_Cu,3,[[vx,6.6],[x+4.5,8.7],[x+4.5,21]],f'cell{i}-fused-fanout')
  for j,y in enumerate((1.4,2.3,3.2,4.1)):via(n,[vx,y],f'cell{i}-{j}')
 track(net('fuse1',2),pcbnew.B_Cu,3,[[19.5,21],[41,42.5],[41,89.9],[33.2,97.7],[33.2,100]],'junction1-current-rail')
 track(net('fuse2',2),pcbnew.B_Cu,3,[[45.5,21],[67,42.5],[67,89.9],[57,99.9],[51.2,99.9],[51.2,100]],'junction2-current-rail')
 track(net('fuse3',2),pcbnew.B_Cu,3,[[71.5,21],[76,25.5],[76,76],[71,81],[71,96],[69.2,97.8],[69.2,100]],'raw-top-current-rail')
 track(net('holder1',2),pcbnew.B_Cu,3,[[15,89.9],[15.2,90.1],[15.2,100]],'raw-ground-current-rail')
 board.GetDesignSettings().SetCopperLayerCount(2)
 board.GetDesignSettings().SetBoardThickness(pcbnew.FromMM(1.6))
 board.GetDesignSettings().m_TentViasFront=True;board.GetDesignSettings().m_TentViasBack=True
 output=HERE/'companion-routed.kicad_pcb';pcbnew.SaveBoard(str(output),board)
 text=output.read_text().replace('${KIPRJMOD}/../../../parts/','${KIPRJMOD}/../../parts/')
 for old,new in identities.items():text=text.replace(old,new)
 tree=parse(text)
 assert not children(tree,'group'),'Group references require explicit UUID remapping review'
 # KiCad sorts new items using their random creation UUIDs. Normalize each
 # root-level item's order by its actual geometry before assigning stable IDs.
 # Existing footprint child ordering is inherited unchanged from SOURCE.
 def semantic(value):
  if not isinstance(value,list):return value
  return [semantic(v) for v in value if not(isinstance(v,list) and v and v[0]=='uuid')]
 for kind in ('segment','via','zone'):
  slots=[i for i,v in enumerate(tree) if isinstance(v,list) and v and v[0]==kind]
  ordered=sorted((tree[i] for i in slots),key=lambda v:dumps(semantic(v)))
  for i,v in zip(slots,ordered):tree[i]=v
 uuid_count=[0]
 def rekey(value,path=()):
  if not isinstance(value,list):return
  if value and value[0]=='uuid':
   value[1]=str(uuid.uuid5(NS,'native-item/'+('/'.join(map(str,path)))))
   uuid_count[0]+=1
  else:
   for i,child in enumerate(value):
    if isinstance(child,list):rekey(child,path+(i,))
 rekey(tree)
 output.write_text(dumps(tree)+'\n')
 # SaveBoard copies the canonical project defaults, including ignored checks.
 # Explicitly enable these assembly checks in the routed derivative.
 project=output.with_suffix('.kicad_pro')
 settings=json.loads(project.read_text())
 severities=settings['board']['design_settings']['rule_severities']
 severities['missing_courtyard']='error'
 severities['footprint_type_mismatch']='error'
 project.write_text(json.dumps(settings,indent=2)+'\n')
 (HERE/'fp-lib-table').write_text((SOURCE.parent/'fp-lib-table').read_text().replace('${KIPRJMOD}/../../../parts/','${KIPRJMOD}/../../parts/'))
 assert sha(SOURCE)==before and sha(MECHANICAL)==mechanical_sha
 assert board_graph(SOURCE)==board_graph(output),'Physical pin/net identity changed'
 record={'status':'EXPERIMENTAL hand route; pending DRC, physical and thermal validation','canonical_pcb_sha256':before,'mechanical_sha256':mechanical_sha,'route_source_sha256':sha(Path(__file__)),'routed_pcb_sha256':sha(output),'authorized_deltas':['Three nonpolar fuse footprint rotations90→270 degrees; physical pin/net identities unchanged','F.Cu upper support retained, exact recessed B.Cu covered-track window only','Bottom fixture lands prohibit pads/vias/exposed features; masked tracks only','NativeKiCad10 serialization and equivalent relative model/library paths','All item UUIDs deterministically re-keyed; no group references in this board'],'traces':routes,'unique_item_uuids':uuid_count[0],'vias':{'count':12,'diameter_mm':.9,'drill_mm':.4,'tenting':'front and back'},'current_assumptions':{'total_pack_a':4,'equal_branch_a':2,'not_guaranteed':'Equal current sharing, holder rating, fuse clearing, trace/via temperature and assembly fit'}}
 (HERE/'route-record.json').write_text(json.dumps(record,indent=2)+'\n')
 print(f'Experimental companion: {serial} segments,12 vias; circuit graph unchanged')
if __name__=='__main__':main()
