"""Physical verification of the connected primary routing study."""
import collections,hashlib,json,sys,tempfile
from pathlib import Path
import wx,pcbnew
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[2]
sys.path[:0]=[str(HERE),str(ROOT/'hw/routing/blind-pack-primary')]
import route
import finish
import route_geometry as checks
checks.APPROVED={'carrier.'+k:v for k,v in route.MOVES.items()}
checks.APPROVED.update({f'carrier.fuse{i}':([x,4],270) for i,x in enumerate((15,41,67),1)})

def quiet_ground(b):
 full=checks.copper_components(b,'carrier-contact-1')
 assert any(any(k[:3]==('pad','carrier.protection.gauge','20') for k in g) and any(k[:3]==('pad','carrier.protection.shunt','1') for k in g) for g in full), 'Quiet return does not reach the RAW shunt land'
 groups=checks.copper_components(b,'carrier-contact-1',('carrier.protection.shunt','1'))
 def has(g,a,n):return any(k[:3]==('pad','carrier.'+a,str(n)) for k in g)
 group=next(g for g in groups if has(g,'protection.gauge',18))
 required=[('protection.gauge',n) for n in (18,19,20,25)]+[(a,2) for a in ('protection.c_supply','protection.c_reg2','protection.c_reg3','protection.c_cell1','protection.r_pfail','protection.r_aoldo')]+[(a,1) for a in ('ntc1_return','ntc2_return')]
 assert all(has(group,*p) for p in required), 'Quiet ground local or remote return is open'
 assert not any(has(group,*p) for p in [('holder1',2),('link_raw_ground',1),('protection.gauge',15)]),'Quiet ground joins load or CSP before shunt'
 return {'required_pad_groups':len(required),'shape_items':len(group)}

def esd_return(b):
 p=checks.parts(b)
 def pad(a,n):return next(x for x in p['carrier.'+a].Pads() if x.GetNumber()==str(n))
 def has(g,a,n):return any(k[:3]==('pad','carrier.'+a,str(n)) for k in g)
 pack=pad('harness_pack_ground',1).GetNetname()
 groups=checks.copper_components(b,pack,('carrier.protection.shunt','2'))
 g=next(g for g in groups if has(g,'harness_pack_ground',1))
 for name in ('sda','scl','alert'):
  assert pad('protection.z_'+name,2).GetNetname()==pack
  assert has(g,'protection.z_'+name,2),'Clamp return disconnected from external PACK-'
  host=pad('protection.z_'+name,1).GetNetname()
  assert host==pad('protection.r_'+name,1).GetNetname()!=pad('protection.r_'+name,2).GetNetname(),'Wrong side of series resistor'
 assert not has(g,'protection.gauge',14),'ESD return branches through CSN Kelvin'
 record=json.loads((HERE/'route-record.json').read_text())
 branch=[r for r in record['routes'] if r['label']=='ESD-pack-return']
 spine=[r for r in record['routes'] if r['label']=='ESD-ground-front-bus']
 assert len(branch)==len(spine)==1
 assert all(r['net']==pack and r['width_mm']>=.8 for r in branch+spine),'Unreviewed narrow ESD return'
 assert branch[0]['length_mm']<11 and spine[0]['length_mm']==6,'ESD return unexpectedly detoured'
 escape=[r for r in record['routes'] if r['label']=='ESD-ground-via-escape']
 assert len(escape)==1 and escape[0]['net']==pack and escape[0]['width_mm']==.6 and abs(escape[0]['length_mm']-.9)<1e-8,'Unreviewed ESD via escape'
 return {'clamps':3,'branch_length_mm':branch[0]['length_mm'],'spine_length_mm':6,'width_mm':.8,'via_escape_width_mm':.6,'via_escape_length_mm':.9,'limits':'Actual topology and geometry only; ESD waveform, via inductance and component survival remain untested.'}

def via_solder_margin(b):
 """Open/tented drill edges must clear every external SMT land, even same-net."""
 lands=[(f.GetFieldText('atopile_address'),p) for f in b.GetFootprints() for p in f.Pads() if p.GetAttribute()==pcbnew.PAD_ATTRIB_SMD]
 checked=0
 for v in b.GetTracks():
  if not isinstance(v,pcbnew.PCB_VIA):continue
  # Tenting is not filled/capped via-in-pad process approval. Probe the actual
  # drill disk independently of net names, including custom/rotated pad shapes.
  hole=pcbnew.PCB_VIA(b);hole.SetPosition(v.GetPosition());hole.SetWidth(v.GetDrillValue())
  for address,pad in lands:
   for layer in (pcbnew.F_Cu,pcbnew.B_Cu):
    if pad.IsOnLayer(layer):
     assert not hole.GetEffectiveShape(layer).Collide(pad.GetEffectiveShape(layer),200000), 'Via drill margin to SMT land: '+address+'.'+pad.GetNumber()+' at '+str(checks.local(v.GetPosition()))
  checked+=1
 return {'vias_checked':checked,'smd_lands_checked':len(lands),'minimum_drill_edge_to_land_mm':.2,'scope':'External copper lands on both faces, independent of net identity; no filled/capped via-in-pad exception.'}

def whole_board(b):
 nets={p.GetNetname() for f in b.GetFootprints() for p in f.Pads() if p.GetNetname()}
 result={}
 for name in sorted(nets):
  groups=checks.copper_components(b,name)
  assert len(groups)==1, f'Physical net {name} has {len(groups)} disconnected copper groups'
  result[name]=len(groups[0])
 return result

def via_profile(b):
 record=json.loads((HERE/'route-record.json').read_text());expected=[]
 for v in record['vias']:expected.append((v['net'],[round(x,5) for x in v['xy']],v['diameter_mm'],v['drill_mm']))
 actual=[];fine=[]
 for v in b.GetTracks():
  if not isinstance(v,pcbnew.PCB_VIA):continue
  x,y=checks.local(v.GetPosition());d=round(pcbnew.ToMM(v.GetWidth(pcbnew.F_Cu)),4);hole=round(pcbnew.ToMM(v.GetDrillValue()),4)
  assert (d,hole) in ((.9,.4),(.6,.3),(.5,.25)),'Unreviewed via geometry'
  if d==.5:
   assert 24<=x<=36 and .6<=y<=12,'Fine signal via outside bounded gauge region'
   fine.append({'net':v.GetNetname(),'xy':[x,y]})
  actual.append((v.GetNetname(),[round(x,5),round(y,5)],d,hole))
 assert collections.Counter((n,tuple(xy),d,h) for n,xy,d,h in expected)==collections.Counter((n,tuple(xy),d,h) for n,xy,d,h in actual),'Actual vias differ from declared route plan'
 return fine

def route_inventory(b):
 record=json.loads((HERE/'route-record.json').read_text())
 def key(net,layer,width,a,c):
  return (net,layer,round(width,5),tuple(sorted((tuple(round(v,5) for v in a),tuple(round(v,5) for v in c)))))
 expected=[]
 for r in record['routes']:
  if r['width_mm']<.2:
   assert r['width_mm']==.15 and r['label']=='IN-final-narrow','Unreviewed narrow-trace exception'
  for a,c in zip(r['points_local_xy'],r['points_local_xy'][1:]):
   if a!=c:expected.append(key(r['net'],r['layer'],r['width_mm'],a,c))
 actual=[key(t.GetNetname(),pcbnew.LayerName(t.GetLayer()),pcbnew.ToMM(t.GetWidth()),checks.local(t.GetStart()),checks.local(t.GetEnd()))
         for t in b.GetTracks() if not isinstance(t,pcbnew.PCB_VIA)]
 assert collections.Counter(actual)==collections.Counter(expected),'Saved copper differs from finite routing plan'
 assert len(actual)==record['segments']
 return {'segments':len(actual),'vias':len(record['vias']),'narrow_trace_label':'IN-final-narrow','narrow_width_mm':.15}

def negative_controls():
 """Exercise physical topology and geometry gates on isolated in-memory boards."""
 board_path=HERE/'primary-routed.kicad_pcb';failures=[]
 def fresh():return pcbnew.LoadBoard(str(board_path))
 def rejected(name,fn):
  try:fn()
  except AssertionError:failures.append(name)
  else:raise AssertionError('Injected fault accepted: '+name)
 def cut_label(label):
  record=json.loads((HERE/'route-record.json').read_text())
  r=next(r for r in record['routes'] if r['label']==label and len(r['points_local_xy'])>=2)
  a,c=r['points_local_xy'][:2]
  tree=checks.parse(board_path.read_text())
  def xy(node,tag):
   v=checks.one(node,tag);return [round(float(v[1])-100,5),round(204-float(v[2]),5)]
  matches=[s for s in checks.children(tree,'segment') if checks.one(s,'net')[1]==r['net'] and checks.one(s,'layer')[1]==r['layer'] and
           xy(s,'start')==[round(v,5) for v in a] and xy(s,'end')==[round(v,5) for v in c]]
  assert len(matches)==1,'Mutation must remove exactly one declared segment'
  tree.remove(matches[0])
  with tempfile.TemporaryDirectory(prefix='primary-cut-') as folder:
   path=Path(folder)/'cut.kicad_pcb';path.write_text(checks.dumps(tree)+'\n')
   result=pcbnew.LoadBoard(str(path))
  return result
 b=cut_label('CSP-refined-isolated')
 rejected('open_CSP_branch',lambda:checks.verify_current_and_kelvin(b))
 b=fresh();p=checks.parts(b)['carrier.protection.gauge']
 net=next(pad.GetNet() for pad in p.Pads() if pad.GetNumber()=='15')
 t=pcbnew.PCB_TRACK(b);t.SetNet(net);t.SetLayer(pcbnew.F_Cu);t.SetWidth(pcbnew.FromMM(.2))
 t.SetStart(checks.point([45.7,4]));t.SetEnd(checks.point([45.7,8]));b.Add(t)
 rejected('same_net_CSP_load_shortcut',lambda:checks.verify_current_and_kelvin(b))
 b=cut_label('ESD-pack-return')
 rejected('open_ESD_PACK_return',lambda:esd_return(b))
 b=fresh();p=checks.parts(b)['carrier.protection.z_scl'];land=next(p for p in p.Pads() if p.GetNumber()=='2')
 v=next(v for v in b.GetTracks() if isinstance(v,pcbnew.PCB_VIA) and checks.local(v.GetPosition())==[44.59,98.0])
 assert v.GetNetCode()==land.GetNetCode()
 v.SetPosition(land.GetPosition())
 rejected('same_net_via_in_SMD_land',lambda:via_solder_margin(b))
 b=cut_label('SDA-final-uplink')
 rejected('open_SDA_uplink',lambda:whole_board(b))
 b=cut_label('GND-shunt-bottom-land')
 rejected('open_quiet_shunt_return',lambda:quiet_ground(b))
 b=fresh();p=checks.parts(b)['carrier.protection.gauge']
 net=next(pad.GetNet() for pad in p.Pads() if pad.GetNumber()=='20')
 t=pcbnew.PCB_TRACK(b);t.SetNet(net);t.SetLayer(pcbnew.B_Cu);t.SetWidth(pcbnew.FromMM(.2))
 t.SetStart(checks.point([26,6.5]));t.SetEnd(checks.point([28.4,8]));b.Add(t)
 rejected('quiet_ground_to_CSP_shortcut',lambda:quiet_ground(b))
 b=fresh();v=next(v for v in b.GetTracks() if isinstance(v,pcbnew.PCB_VIA) and v.GetWidth(pcbnew.F_Cu)==pcbnew.FromMM(.5))
 v.SetDrill(pcbnew.FromMM(.3))
 rejected('unreviewed_signal_via_annulus',lambda:via_profile(b))
 b=fresh();v=next(v for v in b.GetTracks() if isinstance(v,pcbnew.PCB_VIA) and v.GetWidth(pcbnew.F_Cu)==pcbnew.FromMM(.5))
 v.SetPosition(checks.point([20,2]))
 rejected('fine_via_outside_escape_region',lambda:via_profile(b))
 b=fresh();t=next(t for t in b.GetTracks() if not isinstance(t,pcbnew.PCB_VIA) and t.GetWidth()==pcbnew.FromMM(5))
 t.SetWidth(pcbnew.FromMM(.15))
 rejected('load_trace_narrowed',lambda:route_inventory(b))
 with tempfile.TemporaryDirectory(prefix='primary-refinement-fault-') as tmp:
  b=fresh();f=checks.parts(b)['carrier.holder1'];f.SetPosition(f.GetPosition()+pcbnew.VECTOR2I(pcbnew.FromMM(.1),0))
  path=Path(tmp)/'moved.kicad_pcb';pcbnew.SaveBoard(str(path),b)
  rejected('holder_anchor_moved',lambda:checks.verify_geometry(path))
 return failures

def main():
 app=wx.App(False);quiet=wx.LogNull()
 paths=[HERE/n for n in ('route.py','signals.py','gates.py','checks.py','primary-routed.kicad_pcb','primary-routed.kicad_pro','primary-routed.kicad_dru','route-record.json','fp-lib-table')]+[checks.SOURCE,checks.SOURCE.parent/'fp-lib-table',checks.MECHANICAL,Path(checks.__file__)]
 finish_hashes=finish.verify_libraries(HERE,checks.SOURCE.parent/'fp-lib-table')
 paths.extend(ROOT/p for p in finish_hashes)
 paths.extend(ROOT/n for n in ('tools/generate_schematics.py','tools/kicad_sexpr.py','tools/check_footprint_clearances.py','tools/complete_courtyards.py','hw/placement/footprint-clearances.json'))
 manifest=json.loads((ROOT/'hw/placement/footprint-clearances.json').read_text())
 paths.extend(ROOT/e['source'] for e in manifest['footprints'])
 before={str(p.relative_to(ROOT)):checks.sha(p) for p in paths}
 record=json.loads((HERE/'route-record.json').read_text())
 assert checks.sha(checks.SOURCE)==record['canonical_pcb_sha256']
 assert checks.sha(checks.MECHANICAL)==record['mechanical_sha256']
 assert checks.sha(HERE/'primary-routed.kicad_pcb')==record['routed_pcb_sha256']
 assert record['route_dependency_hashes']=={n:checks.sha(HERE/n) for n in record['route_dependency_hashes']}
 assert record['finish_dependencies']==finish_hashes
 board,geom=checks.verify_geometry(HERE/'primary-routed.kicad_pcb')
 out={'geometry':geom,'current_and_kelvin':checks.verify_current_and_kelvin(board),'quiet_ground':quiet_ground(board),'esd_return':esd_return(board),'via_solder_margin':via_solder_margin(board),'fine_signal_vias':via_profile(board),'route_inventory':route_inventory(board)}
 out['all_physical_nets']=whole_board(board)
 version,drc=checks.run_drc(HERE/'primary-routed.kicad_pcb',HERE/'drc.json')
 assert not drc['unconnected_items'],'Actual KiCad DRC still reports open connections'
 holes={f.m_Uuid.AsString() for f in board.GetFootprints() if f.GetAttributes()&pcbnew.FP_BOARD_ONLY}
 missing=[]
 for v in drc['violations']:
  if v['type']=='missing_courtyard':
   assert len(v['items'])==1 and v['items'][0]['uuid'] in holes
   missing.append(v['items'][0]['uuid'])
  else:raise AssertionError(v)
 assert len(missing)==4 and set(missing)==holes
 ignored={v['key'] for v in drc.get('ignored_checks',[])}
 assert not ignored & {'clearance','shorting_items','copper_edge_clearance','hole_clearance','items_not_allowed','courtyards_overlap','missing_courtyard','malformed_courtyard','footprint_type_mismatch','unconnected_items','via_dangling','silk_edge_clearance','silk_overlap','silk_over_copper','lib_footprint_mismatch'}
 out['drc']={'kicad':version,'unconnected':len(drc['unconnected_items']),'violations':dict(collections.Counter(v['type'] for v in drc['violations'])),'ignored_checks':drc.get('ignored_checks',[])}
 out['negative_controls']=negative_controls()
 out['source_hashes']=before
 assert before=={str(p.relative_to(ROOT)):checks.sha(p) for p in paths},'Input changed during check'
 out['status']='EXPERIMENTAL CONNECTED ROUTE; retained manufacturing findings and physical qualification remain'
 (HERE/'checks.json').write_text(json.dumps(out,indent=2)+'\n')
 print(json.dumps({k:v for k,v in out.items() if k not in ('source_hashes','all_physical_nets','fine_signal_vias','geometry')},indent=2))
if __name__=='__main__':main()
