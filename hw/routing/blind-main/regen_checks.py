"""Independent physical-copper and plane-free return checks for local clamp."""
import pcbnew,collections,json,math
from pathlib import Path

def via_lands(b):
 count=0
 for v in b.GetTracks():
  if not isinstance(v,pcbnew.PCB_VIA):continue
  drill=pcbnew.PCB_VIA(b);drill.SetPosition(v.GetPosition());drill.SetWidth(v.GetDrillValue())
  for f in b.GetFootprints():
   for p in f.Pads():
    if p.IsOnLayer(pcbnew.F_Cu):assert not drill.GetEffectiveShape(pcbnew.F_Cu).Collide(p.GetEffectiveShape(pcbnew.F_Cu),200000),('Via drill violates solder land margin',f.GetFieldText('atopile_address'),p.GetNumber())
  count+=1
 return count

def verify(b,m):
 parts=m.parts(b);nets=collections.defaultdict(list)
 for a,f in parts.items():
  if not a.startswith('regen.'):continue
  for i,p in enumerate(f.Pads()):
   if p.GetNumber() and p.GetNetname():nets[p.GetNetname()].append((a,p.GetNumber()))
 required={n:ends for n,ends in nets.items() if len(ends)>1}
 for n,ends in required.items():
  groups=m.copper_components(b,n)
  assert any(all(sum(k[:3]==('pad',a,p) for k in g)==sum(q.GetNumber()==p for q in parts[a].Pads()) for a,p in ends) for g in groups),('Local clamp net disconnected',n,ends)
 # No analog/control ground return may share load return copper before the plane.
 groups=m.copper_components(b,'lv',include_planes=False)
 expectations=[
  ('load',('regen.q_thermal','1'),{('regen.q_thermal',str(i)) for i in (1,2,3)},4),
  ('detector',('regen.detector','2'),{('regen.detector','2'),('regen.detector','3'),('regen.r_threshold_bottom','2')},1),
  ('ldo',('regen.thermal_supply','2'),{('regen.thermal_supply','2'),('regen.c_thermal_input','2'),('regen.c_thermal_output','2')},1),
 ]
 vias={t.m_Uuid.AsString() for t in b.GetTracks() if isinstance(t,pcbnew.PCB_VIA)}
 details={}
 for name,anchor,expected,nvia in expectations:
  g=next(g for g in groups if ('pad',*anchor) in [k[:3] for k in g]);actual={k[1:3] for k in g if k[0]=='pad'}
  assert actual==expected,('Ground topology changed',name,actual,expected)
  count=sum(k[0]=='route' and k[1] in vias for k in g);assert count==nvia,('Ground plane entries changed',name,count,nvia)
  details[name]={'pads':[list(x) for x in sorted(actual)],'plane_entry_vias':count}
 return {'connected_local_nets':len(required),'ground_topologies':details,'route_vias_checked':via_lands(b),'external_outputs_not_yet_routed':['thermal_ok to main final AND','G to main fault-indication MOSFET']}


def verify_layout(b,m):
 """Independent load endpoints and exact filled-plane return witness."""
 parts=m.parts(b)
 paths=[[(f'regen.r_dump{i}a',1) for i in range(1,5)]+[('motor.c_bulk',1),('motor.ic',11)],
 *[[(f'regen.r_dump{i}a',2),(f'regen.r_dump{i}b',1)] for i in range(1,5)],
 [(f'regen.r_dump{i}b',2) for i in range(1,5)]+[('regen.q_dump',i) for i in range(5,10)],
 [('regen.q_dump',i) for i in range(1,4)]+[('regen.q_thermal',i) for i in range(5,10)],
 [('regen.q_thermal',i) for i in range(1,4)]+[('motor.c_bulk',2)]]
 for ends in paths:
  net=next(p.GetNetname() for p in parts[ends[0][0]].Pads() if p.GetNumber()==str(ends[0][1]))
  groups=m.copper_components(b,net)
  assert any(all(sum(k[:3]==('pad',a,str(n)) for k in group)==sum(p.GetNumber()==str(n) for p in parts[a].Pads()) for a,n in ends) for group in groups),('Open clamp load group',ends)
 plane=pcbnew.SHAPE_POLY_SET()
 for z in b.Zones():
  if not z.GetIsRuleArea() and z.GetLayer()==pcbnew.In1_Cu and z.GetNetname()=='lv':plane.BooleanAdd(z.GetFilledPolysList(pcbnew.In1_Cu))
 path=[[6.8,24],[9,23.4],[23.6,22.5],[28.6,22.3],[32.6,20.8],[41,22],[43.8,21.8],[45.9,20.8]]
 for a,c in zip(path,path[1:]):
  t=pcbnew.PCB_TRACK(b);t.SetStart(m.point(a));t.SetEnd(m.point(c));t.SetWidth(pcbnew.FromMM(1.2));t.SetLayer(pcbnew.In1_Cu)
  swept=pcbnew.SHAPE_POLY_SET();t.TransformShapeToPolygon(swept,pcbnew.In1_Cu,0,500,pcbnew.ERROR_OUTSIDE);swept.BooleanSubtract(plane)
  assert swept.Area()<1,'Filled plane no longer contains complete 1.2 mm return witness'
 data=json.loads((Path(__file__).resolve().parent/'regen-routes.json').read_text())
 from regen_analog import verify as analog
 return {'connected_load_groups':len(paths),'return_corridor':{'width_mm':1.2,'uvs':path,'length_mm':sum(math.dist(a,c) for a,c in zip(path,path[1:])),'scope':'Complete swept polygon contained in actual filled plane; not current distribution or ampacity'},'sensitive_branch_review':analog(b,data)}
