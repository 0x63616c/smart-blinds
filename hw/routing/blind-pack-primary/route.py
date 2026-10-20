#!/usr/bin/env python3
"""Experimental primary current/Kelvin route; canonical captures stay unchanged."""
import hashlib,json,math,sys,uuid,os
from pathlib import Path
import pcbnew,wx
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[2]
sys.path.insert(0,str(ROOT/'tools'))
from generate_schematics import board_graph
from kicad_sexpr import children,parse,dumps
sys.path.insert(0,str(HERE.parent/'carrier-finish'))
import finish
SOURCE=ROOT/'hw/layouts/blind-pack-primary/primary-test/primary-test.kicad_pcb'
MECHANICAL=ROOT/'cad/parameters/retained-interfaces.json'
NS=uuid.UUID('1e906c2a-0859-4c1f-b8df-85cd01877b2c')
MOVES={
 'protection.shunt':([47,4],0),
 'protection.r_balance4':([73,4.5],90),
 'protection.r_charge_gate':([51,1],0),
 'protection.c_charge_gate':([51.6,7.1],0),
 'protection.r_pfail':([31.8,6.4],90),
 'protection.gauge':([28,4.8],0),
 'protection.r_aoldo':([34,6.9],0),
 'protection.r_balance3':([10.5,4.5],90),
 'protection.c_pump':([27.75,1.0],0),
 'protection.c_reg3':([33.8,3.2],90),
 'protection.c_reg2':([22.5,5.5],0),
 'protection.c_supply':([24.7,1.2],180),
 'protection.r_pack_sense':([31.8,1.6],180),
 'protection.r_supply':([75.8,6.5],0),
 'protection.r_balance1':([21,1.4],0),
}
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def point(xy):return pcbnew.VECTOR2I(pcbnew.FromMM(100+xy[0]),pcbnew.FromMM(204-xy[1]))
def main():
 app=wx.App(False);quiet=wx.LogNull();before=sha(SOURCE);mechanical_sha=sha(MECHANICAL)
 mech=json.loads(MECHANICAL.read_text())['carrier']
 b=pcbnew.LoadBoard(str(SOURCE));assert not list(b.GetTracks())
 assert all(z.GetIsRuleArea() for z in b.Zones())
 parts={f.GetFieldText('atopile_address').removeprefix('carrier.'):f for f in b.GetFootprints() if not(f.GetAttributes()&pcbnew.FP_BOARD_ONLY)}
 assert len(parts)==50
 for address,(position,rotation) in MOVES.items():
  parts[address].SetPosition(point(position));parts[address].SetOrientationDegrees(rotation)
 for i in range(1,4):parts[f'fuse{i}'].SetOrientationDegrees(270)
 def pad(a,n):return next(p for p in parts[a].Pads() if p.GetNumber()==str(n))
 def net(a,n):return pad(a,n).GetNet()
 routes=[];vias=[];serial=0
 def track(n,layer,width,points,label):
  nonlocal serial
  for a,c in zip(points,points[1:]):
   if a==c:continue
   t=pcbnew.PCB_TRACK(b);t.SetStart(point(a));t.SetEnd(point(c));t.SetWidth(pcbnew.FromMM(width));t.SetLayer(layer);t.SetNet(n);b.Add(t);serial+=1
  routes.append({'label':label,'net':n.GetNetname(),'layer':pcbnew.LayerName(layer),'width_mm':width,'points_local_xy':points,'length_mm':sum(math.dist(a,c) for a,c in zip(points,points[1:]))})
 def via(n,xy,label,power=True,compact=False):
  diameter,drill=(.9,.4) if power else ((.50,.25) if compact else (.6,.3))
  assert not compact or (not power and 24<=xy[0]<=36 and 0.6<=xy[1]<=12), "Fine signal via outside reviewed gauge escape"
  v=pcbnew.PCB_VIA(b);v.SetPosition(point(xy));v.SetWidth(pcbnew.FromMM(diameter));v.SetDrill(pcbnew.FromMM(drill));v.SetLayerPair(pcbnew.F_Cu,pcbnew.B_Cu);v.SetNet(n);b.Add(v)
  vias.append({'label':label,'net':n.GetNetname(),'xy':xy,'diameter_mm':diameter,'drill_mm':drill})
 def bank(n,x,ys,label):
  for i,y in enumerate(ys):via(n,[x,y],f'{label}-{i}')
  for layer in (pcbnew.F_Cu,pcbnew.B_Cu):track(n,layer,2,[[x,ys[0]],[x,ys[-1]]],label+'-bank-'+pcbnew.LayerName(layer))
 F=pcbnew.F_Cu;B=pcbnew.B_Cu
 for i,x in enumerate((15,41,67),1):
  track(net(f'holder{i}',1),F,2,[[x,9.9],[x,6.455]],f'cell{i}-short-unfused')
 # The middle branch crosses the Kelvin corridor on F.Cu before changing layers.
 for i,x in ((1,15),(3,67)):
  n=net(f'fuse{i}',2);vx=x+2.4
  track(n,F,2,[[x,1.545],[vx,1.545]],f'cell{i}-fused-exit')
  bank(n,vx,[1.4,2.3,3.2,4.1],f'cell{i}')
  track(n,B,2,[[vx,4.1],[vx,6.6]],f'cell{i}-bank-extension')
  track(n,B,3,[[vx,6.6],[x+4.5,8.7],[x+4.5,21]],f'cell{i}-fanout')
 n=net('fuse2',2)
 track(n,F,2,[[41,1.545],[37.2,1.545],[37.2,11]],'cell2-fused-front-crossing')
 bank(n,37.2,[11,11.9,12.8,13.7],'cell2')
 track(n,B,3,[[37.2,13.7],[37.2,30],[67,59.8],[67,89.9]],'junction2-current-rail')
 track(net('fuse1',2),B,3,[[19.5,21],[41,42.5],[41,89.9],[33.2,97.7],[33.2,100]],'junction1-current-rail')
 track(n,B,3,[[67,89.9],[63,89.9]],'junction2-link-approach')
 track(n,B,1.5,[[63,89.9],[56,91.5],[56,98]],'junction2-short-wire-row-neck')
 track(n,B,3,[[56,98],[54,100],[51.2,100]],'junction2-link')
 track(net('fuse3',2),B,3,[[71.5,21],[76,25.5],[76,76],[74,78],[74,91.8]],'raw-top-current-rail')
 track(net('fuse3',2),B,1.5,[[74,91.8],[74,98]],'raw-top-short-wire-row-neck')
 track(net('fuse3',2),B,3,[[74,98],[72,100],[69.2,100]],'raw-top-link')
 ground=net('holder1',2);pack_ground=net('protection.shunt',2);raw=net('fuse3',2);pack=net('harness_pack_positive',1)
 track(ground,B,1.5,[[15,89.9],[7.6,92.5],[7.6,96],[11.6,100],[15.2,100]],'raw-ground-link')
 track(ground,F,5,[[15,89.9],[15,84],[11,80],[11,20]],'raw-ground-current-long')
 track(ground,F,4,[[11,20],[45.5,20]],'raw-ground-current-across')
 track(ground,F,3,[[45.5,20],[45.5,11]],'raw-ground-current-approach')
 track(ground,F,2,[[45.5,11],[45.5,8],[44.145,6.645],[44.145,5.5]],'shunt-raw-current-entry')
 # Separate source pin fanouts; no accidental gate/drain bridge.
 for number,y in ((1,5.475),(2,4.825),(3,4.175)):
  track(raw,F,.35,[[52.6,y],[51.8,y]],f'charge-source-pin{number}')
 track(raw,F,.8,[[51.8,4.175],[51.8,6.1],[53.2,7.5],[53.2,9.3]],'charge-source-bus')
 bank(raw,53.2,[9.3,10.2,11.1,12],'charge-source')
 track(raw,B,2,[[53.2,9.3],[53.2,3.0]],'raw-top-feed-protection')
 track(raw,B,3,[[53.2,3.0],[69.4,3.0]],'raw-top-feed-across')
 for number,y in ((1,3.525),(2,4.175),(3,4.825)):
  track(pack,F,.35,[[59.4,y],[60.1,y]],f'discharge-source-pin{number}')
 track(pack,F,.8,[[60.1,4.825],[60.1,2.5],[63.5,2.5]],'discharge-source-bus')
 track(pack,F,2,[[63.5,2.5],[63.5,11.3],[62.8,12]],'discharge-source-bus-wide')
 track(pack,F,5,[[62.8,12],[57,17.8],[57,75],[47,85],[47,94.8]],'protected-positive-trunk')
 # Join both drain paddles and every peripheral drain land explicitly.
 drain=net('protection.charge_fet',9)
 track(drain,F,2,[[54.36,4.5],[57.64,4.5]],'common-drain-spine')
 for x in (54,58):
  track(drain,F,.35,[[x,3.085],[x,5.915]],f'drain-paddle-tabs-{x}')
 for x in (55.5,56.5):
  track(drain,F,.35,[[x,3.525],[x,5.475]],f'drain-peripheral-bus-{x}')
 track(pack_ground,F,1.5,[[49.855,5.5],[49.855,9.3]],'shunt-pack-current-exit')
 bank(pack_ground,49.855,[9.3,10.2,11.1,12],'pack-ground-shunt')
 track(pack_ground,B,3,[[49.855,9.3],[45.5,9.3]],'pack-ground-low-transition')
 track(pack_ground,B,3,[[45.5,9.3],[45.5,19]],'pack-ground-low-approach')
 track(pack_ground,B,5,[[45.5,19],[45.5,23.7],[45.8,24]],'pack-ground-low')
 bank(pack_ground,45.8,[24,24.9,25.8,26.7],'pack-ground-crossing-low')
 track(pack_ground,F,5,[[45.8,26.7],[45.8,44]],'pack-ground-front-crossing')
 bank(pack_ground,45.8,[44,44.9,45.8,46.7],'pack-ground-crossing-high')
 track(pack_ground,B,5,[[45.8,46.7],[53,53.9],[53,88]],'protected-ground-trunk')
 track(pack_ground,B,3,[[53,88],[53,94.8]],'protected-ground-output-approach')
 power_route_labels=[r['label'] for r in routes]
 # Kelvin points are inner shunt-land edges; neither path carries load current.
 track(ground,F,.2,[[28.25,6.71],[28.25,7.25],[28.4,8.0]],'CSP-pin-escape')
 via(ground,[28.4,8.0],'CSP-gauge',False)
 via(ground,[45.7,4],'CSP-shunt',False)
 track(ground,F,.2,[[45.7,4],[44.9,4]],'CSP-inner-land')
 track(pack_ground,F,.2,[[28.75,6.71],[28.75,7.25],[29.4,8.6]],'CSN-pin-escape')
 via(pack_ground,[29.4,8.6],'CSN-gauge',False)
 via(pack_ground,[48.3,4],'CSN-shunt',False)
 track(pack_ground,F,.2,[[48.3,4],[49.1,4]],'CSN-inner-land')
 exec((HERE/'signals.py').read_text())
 exec((HERE/'gates.py').read_text())
 for i,rect in enumerate(mech['service_fixture_backing']['local_rectangles_xy']):
  z=pcbnew.ZONE(b);z.SetIsRuleArea(True);z.SetZoneName(f'FIXTURE_BACKING_NO_EXPOSED_{i}')
  ls=pcbnew.LSET();ls.AddLayer(B);z.SetLayerSet(ls)
  z.SetDoNotAllowTracks(False);z.SetDoNotAllowVias(True);z.SetDoNotAllowPads(True);z.SetDoNotAllowZoneFills(True);z.SetDoNotAllowFootprints(False)
  poly=z.Outline();poly.NewOutline();x0,y0,x1,y1=rect
  for p in ((x0,y0),(x1,y0),(x1,y1),(x0,y1)):poly.Append(point(p))
  b.Add(z)
 ds=b.GetDesignSettings();ds.SetCopperLayerCount(2);ds.SetBoardThickness(pcbnew.FromMM(1.6));ds.m_TentViasFront=True;ds.m_TentViasBack=True
 output=HERE/'primary-routed.kicad_pcb';pcbnew.SaveBoard(str(output),b)
 tree=parse(output.read_text().replace('${KIPRJMOD}/../../../parts/','${KIPRJMOD}/'+os.path.relpath(ROOT/'hw/parts',HERE)+'/'))
 assert not children(tree,'group')
 finish.finish_board(tree,21)
 def semantic(v):
  if not isinstance(v,list):return v
  return [semantic(x) for x in v if not(isinstance(x,list) and x and x[0]=='uuid')]
 for kind in ('segment','via','zone'):
  slots=[i for i,v in enumerate(tree) if isinstance(v,list) and v and v[0]==kind]
  for i,v in zip(slots,sorted((tree[i] for i in slots),key=lambda v:dumps(semantic(v)))):tree[i]=v
 def rekey(v,path=()):
  if not isinstance(v,list):return
  if v and v[0]=='uuid':v[1]=str(uuid.uuid5(NS,'item/'+('/'.join(map(str,path)))))
  else:
   for i,x in enumerate(v):
    if isinstance(x,list):rekey(x,path+(i,))
 rekey(tree);output.write_text(dumps(tree)+'\n')
 project=output.with_suffix('.kicad_pro');settings=json.loads(project.read_text())
 settings['board']['design_settings']['rules']['min_through_hole_diameter']=.25
 for name in ('missing_courtyard','footprint_type_mismatch'):settings['board']['design_settings']['rule_severities'][name]='error'
 project.write_text(json.dumps(settings,indent=2)+'\n')
 finish.write_libraries()
 finish.write_table(SOURCE.parent/'fp-lib-table',HERE)
 assert sha(SOURCE)==before and sha(MECHANICAL)==mechanical_sha
 assert board_graph(SOURCE)==board_graph(output)
 record={'status':'EXPERIMENTAL connected routing candidate; see independent checks and unresolved layout/physical qualification gates',
 'canonical_pcb_sha256':before,'mechanical_sha256':mechanical_sha,'route_source_sha256':sha(Path(__file__)),'routed_pcb_sha256':sha(output),
 'route_dependency_hashes':{name:sha(HERE/name) for name in ('route.py','signals.py','gates.py','primary-routed.kicad_pro','primary-routed.kicad_dru')},
 'finish_dependencies':finish.dependencies(),
 'load_route_labels':power_route_labels,'placement_deltas':MOVES,'additional_deltas':['Three nonpolar fuses 90→270 degrees','Native KiCad 10 serialization, stable unique UUIDs and equivalent relative library/model paths','Inward backing lands reject exposed features; no copper fills','Narrow fuse, holder, resistor and FET silkscreen edits; text/polarity, pads and all non-silk geometry unchanged; matching routed-project libraries'],
 'segments':serial,'routes':routes,'vias':vias,'current_planning_a':4,'branch_planning_a':2}
 (HERE/'route-record.json').write_text(json.dumps(record,indent=2)+'\n')
 print(f'Primary candidate route: {serial} segments, {len(vias)} vias; graph unchanged')
if __name__=='__main__':main()
