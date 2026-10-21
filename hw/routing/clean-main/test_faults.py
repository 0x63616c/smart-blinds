"""Focused real-copper fault controls and emitter trust-boundary controls.
Physical faults deliberately disable exact copper inventory, and assert their
specific physical rejection instead of accepting a missing-record failure.
"""
from pathlib import Path
import argparse,json,copy,tempfile,shutil
import geometry as G,emit,validate,topology,check as maincheck
from shapely.geometry import Point,LineString,box
from shapely.ops import unary_union
D=Path(__file__).parent

def main(board,out,source_root=None,snapshot=False):
 binding,chosen_root=emit.inputs(source_root,snapshot=snapshot)
 B=G.canonical_nets(G.parse(board.read_text()));r,c=validate.records();F=G.parts(B);results=[]
 def reject(name,mutation,check,reason,base=B):
  t=copy.deepcopy(base);before=json.dumps(t,sort_keys=True);mutation(t);assert json.dumps(t,sort_keys=True)!=before,('no-op mutant',name)
  try:check(t)
  except (AssertionError,KeyError,ValueError)as e:
   assert reason in str(e),('wrong rejection',name,reason,str(e));results.append(dict(name=name,rejected=True,reason=str(e)[:350]));return
  raise AssertionError(('fault accepted',name))
 def find(t,kind,name):
  ids={q['uuid']for q in r['copper']if q['kind']==kind and q['name']==name};return [x for x in G.children(t,kind)if G.one(x,'uuid')[1]in ids]
 def remove_path(name):return lambda t:[t.remove(x)for x in find(t,'segment',name)]
 def physical(t):return validate.audit(t,filled=True,inventory=False,geometry=False)
 for name in ['eFuse current limit','Load discharge head terminal','Cutoff RAW pin1','OVP divider tap revised','Cutoff limit series']:
  reject('physical cut '+name,remove_path(name),physical,'physical endpoint group cut')
 reject('regulator SW entire physical branch',lambda t:[t.remove(s)for s in list(G.children(t,'segment'))if G.one(s,'net')[-1]=='SW'],physical,'physical endpoint group cut')
 def widen(t):G.one(find(t,'segment','Cutoff RTN8 own EP entry')[0],'width')[1]=.35
 reject('finite EP entry widened',widen,lambda t:validate.audit(t,True,False),'finite terminal identity')
 def drill(t):
  v=find(t,'via','eFuse IN lower')[0];G.one(v,'at')[1:]=[124.5,156.8]
 def drill_check(t):
  _,ts,vs,pads,_,_=G.gather(t,c);v=next(x for x in vs if x['uuid']==G.one(find(t,'via','eFuse IN lower')[0],'uuid')[1])
  for p in pads:
   if p['kind']=='smd':assert Point(v['at']).distance(p['geom'])-v['drill']/2>=.2-2e-6,'same-net solder-land drill intrusion'
 reject('same-net via drilled into SMD',drill,drill_check,'same-net solder-land drill intrusion')
 def cc_bypass(t):t.append(G.node('segment',G.node('start',135.2,170.1),G.node('end',135.2,169.45),G.node('width',.15),G.node('layer','B.Cu'),G.node('net','connector-1'),G.node('uuid','55555555-5555-4555-8555-555555555555')))
 def cc_guard(t):
  _,ts,vs,pads,_,_=G.gather(t,c);rr=G.components(G.physical_nodes(t,'connector-1',pads,ts,vs,('usb.tvs_cc','1')))
  assert rr[G.endpoint_ids(pads,'usb.connector','A5')[0]]!=rr[G.endpoint_ids(pads,'usb.pd','1')[0]],'CC clamp physical land bypassed'
 reject('same-net CC clamp shortcut',cc_bypass,cc_guard,'CC clamp physical land bypassed')
 def zone(t,n):return next(z for z in G.children(t,'zone')if G.children(z,'name')and G.one(z,'name')[1]==n)
 def wing(t):
  v=find(t,'via','Cutoff thermal 3')[0];a=G.one(v,'at');a[1]=float(a[1])+60;a[2]=float(a[2])+4
 reject('detached required thermal wing',wing,physical,'required conductor detached')
 def floating(t):
  z=zone(t,'USB_CUTOFF_RTN_BOTTOM')
  for p in list(G.children(z,'filled_polygon')):z.remove(p)
  z.append(G.node('filled_polygon',G.node('layer','B.Cu'),G.node('pts',*[G.node('xy',100+x,175-y)for x,y in [(27,11),(30,11),(30,13),(27,13)]])))
 def reach(t):
  _,ts,vs,pads,_,_=G.gather(t,c);rr=G.components(G.physical_nodes(t,'usb-2',pads,ts,vs));z=zone(t,'USB_CUTOFF_RTN_BOTTOM');goal=rr[G.endpoint_ids(pads,'usb.cutoff','17')[0]]
  for i,_ in enumerate(G.filled_regions(z)):assert rr[('fill',G.one(z,'uuid')[1],i)]==goal,'floating same-net thermal fill'
 reject('floating same-net thermal copper',floating,reach,'floating same-net thermal fill')
 def cut_corridor(t):
  from shapely import get_parts
  from shapely.ops import triangulate
  z=zone(t,'USB_INPUT_GND_RETURN');old=unary_union([p for l,p in G.filled_regions(z)]);metal=old.difference(LineString([(23,19),(23,21.5)]).buffer(.1,cap_style=2));polys=[p for tri in triangulate(metal)for p in get_parts(tri.intersection(metal))if p.geom_type=='Polygon'and p.area>1e-12];assert all(x.is_valid and not x.interiors for x in polys)
  assert abs(sum(p.area for p in polys)-metal.area)<1e-6
  for f in list(G.children(z,'filled_polygon')):z.remove(f)
  for p in polys:z.append(G.node('filled_polygon',G.node('layer','In1.Cu'),G.node('pts',*[G.node('xy',100+x,175-y)for x,y in p.exterior.coords])))
  parsed=unary_union([p for l,p in G.filled_regions(z)]);assert parsed.is_valid and parsed.symmetric_difference(metal).area<1e-7
  _,ts,vs,pads,_,_=G.gather(t,c);rr=G.components(G.physical_nodes(t,'lv',pads,ts,vs))
  for g in c['groups']:
   if g['net']=='lv':assert len({rr[k]for a,p in g['endpoints']for k in G.endpoint_ids(pads,a,p)})==1,'mutant broke unrelated ground endpoint group'
 def corridor(t):
  z=zone(t,'USB_INPUT_GND_RETURN');g=unary_union([p for l,p in G.filled_regions(z)]);assert g.buffer(2e-6).covers(LineString(c['direct_bypass_return']['points']).buffer(.05)),'direct bypass-return corridor cut'
 reject('valid filled direct-return corridor cut',cut_corridor,corridor,'direct bypass-return corridor cut')
 # Source-owned geometry/metadata boundaries are tested independently from
 # exact route inventory, and physical exclusions have direct mutants.
 def current(t):return maincheck.verify(t,board,filled=True,inventory=False,geometry=False,source_root=source_root,snapshot=snapshot)
 def attr(t):G.one(G.parts(t)['regen.thermostat'],'attr')[1:]=[G.Atom('through_hole')]
 reject('SMD assembly attribute regression',attr,current,'reviewed assembly attributes')
 def stackup(t):
  stack=G.one(G.one(t,'setup'),'stackup');layer=next(x for x in G.children(stack,'layer')if x[1]=='In1.Cu');G.one(layer,'thickness')[1]=.07
 reject('reviewed reference stackup changed',stackup,current,'reviewed physical stackup changed')
 def model(t):G.one(G.parts(t)['controller.c_bulk'],'model')[1]='${KIPRJMOD}/models/missing-reviewed-model.wrl'
 reject('missing per-part reviewed model',model,current,'reviewed model content')
 def land_change(t):
  f=G.parts(t)['usb.efuse'];p=next(p for p in G.children(f,'pad')if p[1]=='5');q=G.one(p,'size');q[1]=float(q[1])+.01
 reject('corrected eFuse land changed',land_change,current,'reviewed land/net mismatch')
 def duplicate_address(t):
  f=G.parts(t)['regen.thermostat'];next(p for p in G.children(f,'property')if p[1]=='atopile_address')[2]='usb.efuse'
 reject('duplicate part address',duplicate_address,current,'duplicate address')
 def remove_keepout(t):t.remove(next(z for z in G.children(t,'zone')if G.children(z,'keepout')))
 reject('missing PicoBlade foot rule area',remove_keepout,current,'missing/extra zone or rule area')
 def wrong_zone(t):G.one(zone(t,'USB_CUTOFF_RTN_BOTTOM'),'net')[1]='lv'
 reject('RTN island connected to ground',wrong_zone,current,'zone rail changed')
 def top_transit(t):
  q=next(q for q in r['copper']if q['kind']=='segment'and G.one(G.parse(q['sexpr']),'layer')[1]=='F.Cu');s=next(s for s in G.children(t,'segment')if G.one(s,'uuid')[1]==q['uuid'])
  G.one(s,'start')[1:]=[143.5,115];G.one(s,'end')[1:]=[144.5,115]
 reject('foreign top route through motor body',top_transit,lambda t:validate.audit(t,True,False),'top body transit')
 def reference_intrusion(t):
  x0,y0,x1,y1=c['reference_reservations']['USB']['rect_uv_mm'];u=(x0+x1)/2;v=(y0+y1)/2
  t.append(G.node('segment',G.node('start',100+u,175-v),G.node('end',101+u,175-v),G.node('width',.15),G.node('layer','In1.Cu'),G.node('net','raw-hv'),G.node('uuid','66666666-6666-4666-8666-666666666666')))
 def reference_guard(t):
  _,ts,vs,pads,_,_=G.gather(t,c);return topology.audit(t,r,c,pads,ts,vs,False,{})
 reject('foreign copper in USB reference volume',reference_intrusion,reference_guard,'USB In1 reference intrusion')
 # Explicit metadata/record faults, with exact guarded boundaries.
 def rcheck(x):emit.validate_records(x,F,{q['net']for q in r['copper']})
 reject('duplicate owned route record',lambda x:x['copper'].append(copy.deepcopy(x['copper'][0])),rcheck,'record inventory',r)
 reject('unowned route record',lambda x:x['copper'][0].update(block='unowned'),rcheck,'unowned route record',r)
 reject('stale finite route geometry',lambda x:x['copper'][0].update(sexpr=x['copper'][0]['sexpr'].replace('(width ', '(width 0.01 ')),rcheck,'stale record geometry',r)
 def wrongnet(x):
  q=x['copper'][0];q['net']='not-a-circuit-rail';n=G.parse(q['sexpr']);G.one(n,'net')[1]=q['net'];q['sexpr']=G.dumps(n);q['record_sha256']=emit.hash_text(q['sexpr'])
 reject('owned record with unknown source net',wrongnet,rcheck,'record net missing from source',r)
 def wrongowner(x):
  q=x['copper'][0];owner=next([a,str(p[1])]for a,f in F.items()for p in G.children(f,'pad')if G.children(p,'net')and G.one(p,'net')[-1]!=q['net']);q['own_pads']=[owner]
 reject('terminal owner on wrong rail',wrongowner,rcheck,'record owner pin net',r)
 # A live root with any changed bound library/source must fail before emission.
 b=emit.read('source-binding.json')
 with tempfile.TemporaryDirectory(prefix='clean-main-source-fault-')as tmp:
  root=Path(tmp)
  for rel in b['files']:
   p=root/rel;p.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(chosen_root/rel,p)
  p=root/b['source'];p.write_text(p.read_text()+'\n;changed\n')
  try:emit.build(root)
  except AssertionError as e:assert 'stale bound source'in str(e);results.append(dict(name='live source mutation refused',rejected=True,reason=str(e)))
  else:raise AssertionError('stale live source accepted')
 try:emit.build()
 except AssertionError as e:assert 'choose explicit live source_root'in str(e);results.append(dict(name='implicit snapshot fallback refused',rejected=True,reason=str(e)))
 else:raise AssertionError('implicit source accepted')
 out.write_text(json.dumps(dict(board_sha256=G.sha(board),source_root=str(chosen_root.resolve()),source_mode='snapshot'if snapshot else'live source',physical_inventory_equality=False,tests=results,passed=len(results)),indent=2)+'\n');print('PASS',len(results),'targeted controls')
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('board',type=Path);p.add_argument('--output',type=Path,required=True);g=p.add_mutually_exclusive_group(required=True);g.add_argument('--source-root',type=Path);g.add_argument('--snapshot',action='store_true');a=p.parse_args();main(a.board,a.output,a.source_root,a.snapshot)
