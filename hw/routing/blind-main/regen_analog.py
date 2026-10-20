"""Actual-copper neighbor and intervening-plane audit; not noise acceptance."""
import pcbnew,math

def verify(b,data):
 P=lambda uv:pcbnew.VECTOR2I(pcbnew.FromMM(100+uv[0]),pcbnew.FromMM(175-uv[1]))
 L={'F.Cu':pcbnew.F_Cu,'B.Cu':pcbnew.B_Cu,'In2.Cu':pcbnew.In2_Cu}
 def track(r,a,c):
  t=pcbnew.PCB_TRACK(b);t.SetStart(P(a));t.SetEnd(P(c));t.SetWidth(pcbnew.FromMM(r['width_mm']));t.SetLayer(L[r['layer']]);return t

 def gap(a,c):
  if a.Collide(c,0):return 0.
  lo=0;hi=100000000
  for _ in range(25):
   mid=(lo+hi)//2
   if a.Collide(c,mid):hi=mid
   else:lo=mid
  return hi/1e6

 def poly(t,layer):
  o=pcbnew.SHAPE_POLY_SET();t.TransformShapeToPolygon(o,layer,0,500,pcbnew.ERROR_OUTSIDE);return o
 plane=pcbnew.SHAPE_POLY_SET()
 for z in b.Zones():
  if not z.GetIsRuleArea() and z.GetLayer()==pcbnew.In1_Cu:plane.BooleanAdd(z.GetFilledPolysList(pcbnew.In1_Cu))
 hot={'c_boot1-1':'charger SW1','2':'charger SW2','regen-2-1':'clamp switched drain','series_mid':'series MOSFET midpoint','hv':'PACK / clamp supply'}
 report={'scope':'XY edge distances and actual In1 shielding at projected crossings only. No capacitance/inductance estimate or noise acceptance. Existing unchanged branches remain outside these changed-branch length comparisons.','signals':{}}
 for net,label,prefix in [('pack_ntc','charger NTC','charger-ntc-shielded-'),('PROG','charger POR program','program-reroute-'),('c_boot1-1','SW1 bootstrap return','shortened-bootstrap-return')]:
  old=[r for r in data['removed_baseline_segments'] if r['net']==net];new=[r for r in data['routes'] if r['label'].startswith(prefix)]
  oldlen=sum(math.dist(*r['uvs']) for r in old);newlen=sum(math.dist(a,c) for r in new for a,c in zip(r['uvs'],r['uvs'][1:]));mins={};shielded=[]
  for r in new:
   layer=L[r['layer']]
   for a,c in zip(r['uvs'],r['uvs'][1:]):
    t=track(r,a,c);sh=t.GetEffectiveShape(layer)
    for q in b.GetTracks():
     if q.GetNetname() not in hot or q.GetNetname()==net:continue
     isvia=isinstance(q,pcbnew.PCB_VIA)
     if not isvia and q.GetLayer() not in (layer,pcbnew.B_Cu):continue
     qsh=q.GetEffectiveShape(layer if isvia else q.GetLayer());d=gap(sh,qsh)
     same=isvia or q.GetLayer()==layer
     key=hot[q.GetNetname()]+(' same-layer/via' if same else ' projected B.Cu')
     if key not in mins or d<mins[key]['edge_gap_mm']:mins[key]={'edge_gap_mm':d,'new_segment':r['label'],'neighbor_uuid':q.m_Uuid.AsString()}
     if not same and d==0 and layer==pcbnew.F_Cu:
      overlap=poly(t,layer);overlap.BooleanIntersection(poly(q,q.GetLayer()));overlap.BooleanSubtract(plane)
      assert overlap.Area()<1,('Projected power crossing lacks ground-plane shielding',r['label'],q.m_Uuid.AsString(),overlap.Area())
      shielded.append({'segment':r['label'],'neighbor_uuid':q.m_Uuid.AsString(),'unshielded_projected_area_mm2':overlap.Area()/1e12})
     elif not same and d==0:raise AssertionError(('Unshielded projected hot-copper crossing',r['label'],q.GetNetname()))
    for f in b.GetFootprints():
     for pad in f.Pads():
      if pad.GetNetname() not in hot or pad.GetNetname()==net or not pad.IsOnLayer(layer):continue
      d=gap(sh,pad.GetEffectiveShape(layer));key=hot[pad.GetNetname()]+' same-layer pad'
      if key not in mins or d<mins[key]['edge_gap_mm']:mins[key]={'edge_gap_mm':d,'new_segment':r['label'],'neighbor_part':f.GetFieldText('atopile_address'),'pad':pad.GetNumber()}
  report['signals'][label]={'replaced_length_mm':oldlen,'replacement_length_mm':newlen,'layers':sorted({r['layer'] for r in new}),'nearest_hot_copper':mins,'ground_shielded_projected_crossings':shielded}
 report['signal_scope_notes']=['PROG is sampled at charger POR per TI BQ25798 section 7.3.2; a longer low-current branch was chosen to avoid direct SW1/SW2 overlap. Power-up sampling still needs hardware validation.','The NTC replacement crosses the B.Cu PACK feed on F.Cu, with the actual filled In1 ground polygon between the crossing areas. No new In2 NTC segment remains.','SW1 bootstrap branch uses existing endpoint vias and is shorter; all original wide SW1 power copper remains unchanged.','Same-layer solder lands, route traces and vias are included in the numeric neighbor audit. Cross-layer projected solder-land coupling is not a field-solver result; native DRC and visual layer review remain separate checks.']
 return report
