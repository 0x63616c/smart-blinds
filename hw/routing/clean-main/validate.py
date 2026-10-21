"""Reusable route/body/fill topology audit. No experimental-module imports."""
from pathlib import Path
import json,math,copy,sys,collections
import geometry as G
import contracts as C,topology
from shapely.geometry import Point,Polygon,LineString,box
from shapely.ops import unary_union
D=Path(__file__).parent

def records():
 r=json.loads((D/'routing-records.json').read_text());c=json.loads((D/'physical-contracts.json').read_text());return r,c

def audit(t,filled=False,inventory=True,geometry=True):
 t=G.canonical_nets(t);r,c=records();F,ts,vs,pads,bodies,courts=G.gather(t,c)
 rr=r['copper'];ids=[q['uuid']for q in rr];assert len(ids)==len(set(ids)),'duplicate route record'
 assert all(q.get('block')and q.get('name')and q.get('source')for q in rr),'unowned route record'
 rec={q['uuid']:q for q in rr};actual={q['uuid']:q for q in ts+vs};assert len(actual)==len(ts)+len(vs),'duplicate copper identity'
 if inventory:assert set(actual)==set(rec),'unowned or missing copper'
 assert set(F)==set(c['bodies']),'part address contract'
 review=json.loads((D/'reviewed-parts.json').read_text())['parts']
 for a,f in F.items():
  assert G.pose(f)==review[a]['pose_uv'],('reviewed pose mismatch',a)
  wanted=[dict(pin=p['pin'],net=p['net'],physical=C.semantic_pad(G.parse(G.dumps(p['physical']))))for p in review[a]['pads']]
  actual_pads=C.pad_contract(f);assert len(actual_pads)==len(wanted),('pad count',a)
  for p,q in zip(actual_pads,wanted):assert p['pin']==q['pin']and p['net']==q['net']and C.equivalent(p['physical'],q['physical']),('reviewed land/net mismatch',a,p['pin'])
  assert G.graphics(f,'F.CrtYd')==review[a]['courtyard']and G.graphics(f,'F.Paste')==review[a]['paste'],('courtyard/paste changed',a)
 for a,f in F.items():
  p=G.pose(f);assert all(math.isfinite(x)and abs(x/.25-round(x/.25))<1e-8 for x in p[:2])and p[2]%90==0,('placement grid',a)
 padmap=collections.defaultdict(list)
 for p in pads:padmap[(p['a'],p['p'])].append(p)
 def land(a,p):return unary_union([q['geom']for q in padmap[(a,p)]])
 mini={'foreign':99,'drill_land':99,'drill_drill':99};terminal=[];allcu=ts+vs
 if geometry:
  for x in ts:
   q=rec.get(x['uuid']);assert q,'unowned track';dx=x['a'][0]-x['b'][0];dy=x['a'][1]-x['b'][1]
   assert abs(dx)<2e-8 or abs(dy)<2e-8 or abs(abs(dx)-abs(dy))<2e-8,('routing angle',q['name'])
   for pt in [x['a'],x['b']]:
    if all(math.isfinite(v)and abs(v/.05-round(v/.05))<2e-8 for v in pt):continue
    assert any(land(a,p).covers(Point(pt))for a,p in q['own_pads']),('offgrid outside exact land',q['name'],pt)
   if x['layer']=='F.Cu':
    for a,g in bodies.items():
     hit=x['geom'].intersection(g)
     if hit.area<1e-9:continue
     for own in q['own_pads']:
      if own[0]==a:
       assert all(p['net']==x['net']for p in padmap[tuple(own)]),'own-pad wrong rail'
       hit=hit.difference(land(*own).buffer(2e-6))
     spec=c['finite_terminal_corridors'].get(q['name'])
     if spec and spec['owner']==a:
      assert x['net']==spec['net']and x['width']<=spec['max_width']+1e-9,'finite terminal identity'
      exact=LineString(spec['points']).buffer(spec['max_width']/2).intersection(g).difference(unary_union([land(a,p)for p in spec['pins']]))
      assert hit.difference(exact.buffer(2e-6)).area<1e-9,('finite own entry exceeded',q['name']);hit=hit.difference(exact.buffer(2e-6));terminal.append(q['name'])
     assert hit.area<1e-9,('top body transit',q['name'],a,hit.area)
  for v in vs:
   assert all(math.isfinite(x)and abs(x/.05-round(x/.05))<2e-8 for x in v['at']),'via grid'
   for a,g in bodies.items():assert v['geom'].intersection(g).area<1e-9,('via under body',rec.get(v['uuid'],{}).get('name'),a)
   for p in pads:
    if p['kind']=='smd':
     d=Point(v['at']).distance(p['geom'])-v['drill']/2;mini['drill_land']=min(mini['drill_land'],d);assert d>=.2-2e-6,('SMD drill intrusion',v['uuid'],p['a'],p['p'],d)
   for w in vs:
    if w['uuid']==v['uuid']:continue
    d=math.dist(v['at'],w['at'])-(v['drill']+w['drill'])/2;mini['drill_drill']=min(mini['drill_drill'],d);assert d>=.25-2e-6,('drill spacing',d)
  for i,x in enumerate(allcu):
   ls={x['layer']}if'layer'in x else x['layers']
   for p in pads:
    if p['kind']=='np_thru_hole':assert x['geom'].distance(p['geom'])>=.2-2e-6,('NPTH clearance',x['uuid'],p['a'])
    elif p['net']!=x['net']and ls&p['layers']:
     d=x['geom'].distance(p['geom']);mini['foreign']=min(mini['foreign'],d);assert d>=.15-2e-6,('foreign pad',x['uuid'],p['a'],p['p'],d)
   for y in allcu[:i]:
    ly={y['layer']}if'layer'in y else y['layers']
    if x['net']!=y['net']and ls&ly:
     d=x['geom'].distance(y['geom']);mini['foreign']=min(mini['foreign'],d);assert d>=.15-2e-6,('foreign copper',x['uuid'],y['uuid'],d)
   assert not x['geom'].intersects(box(*c['antenna']['antenna_only_copper_ban_uv'])),'antenna-only copper'
  for z in G.children(t,'zone'):
   if not G.children(z,'keepout'):continue
   poly=Polygon([[float(p[1])-100,175-float(p[2])]for p in G.children(G.one(G.one(z,'polygon'),'pts'),'xy')])
   for x in allcu:
    if 'layer'not in x or x['layer']=='F.Cu':assert x['geom'].intersection(poly).area<1e-9,'mechanical rule-area copper'
 # Exact reviewed courtyard envelopes plus current retainers/RF exclusions.
 for i,(a,g)in enumerate(courts.items()):
  for b,h in list(courts.items())[:i]:assert g.intersection(h).area<1e-9,('courtyard overlap',a,b)
 retainers=[box(0,3,3,11),box(52.5,72,54,80)]
 for a,g in courts.items():
  assert all(g.intersection(x).area<1e-9 for x in retainers),('retainer courtyard intrusion',a)
  if a not in ['controller.mcu','controller.c_bulk','controller.c_bypass']:
   assert g.intersection(box(-9.5,65,38.5,101.5)).area<1e-9,('external metal RF reservation',a)
 for x in ts+vs:
  if 'layer'not in x or x['layer']in ['F.Cu','B.Cu']:
   assert all(x['geom'].intersection(z).area<1e-9 for z in retainers),('retainer surface copper',x['uuid'])
 # Multiple physical copies of one pin are each tested, without dict-key masking.
 roots={};groups=[]
 for group in c['groups']:
  net=group['net']
  if net not in roots:roots[net]=G.components(G.physical_nodes(t,net,pads,ts,vs))
  root=roots[net];targets=[k for a,p in group['endpoints']for k in G.endpoint_ids(pads,a,p)]
  if not filled and net=='lv':continue
  assert len({root[k]for k in targets})==1,('physical endpoint group cut',group['block'],net)
  groups.append(group)
 if filled:
  goals=collections.defaultdict(set)
  for g in c['groups']:
   goals[g['net']].update(roots[g['net']][k]for a,p in g['endpoints']for k in G.endpoint_ids(pads,a,p))
  for x in ts+vs:
   assert roots[x['net']].get(('copper',x['uuid']))in goals[x['net']],('required conductor detached',rec[x['uuid']]['name'])
 for net,pin,con,pd in [('connector-1','1','A5','1'),('CC2','2','B5','4')]:
  root=G.components(G.physical_nodes(t,net,pads,ts,vs,('usb.tvs_cc',pin)))
  assert root[G.endpoint_ids(pads,'usb.connector',con)[0]]!=root[G.endpoint_ids(pads,'usb.pd',pd)[0]],'CC clamp land bypassed'
 zone_results=[]
 for z in G.children(t,'zone'):
  if G.children(z,'keepout'):continue
  name=G.one(z,'name')[1];net=G.one(z,'net')[-1];layer=G.one(z,'layer')[1];key=G.one(z,'uuid')[1];regs=G.filled_regions(z)
  if not filled:assert not regs,'unfilled emitter must not credit saved copper';continue
  assert regs,('missing fill',name)
  outline=Polygon([[float(p[1])-100,175-float(p[2])]for p in G.children(G.one(G.one(z,'polygon'),'pts'),'xy')])
  if net not in roots:roots[net]=G.components(G.physical_nodes(t,net,pads,ts,vs))
  root=roots[net]
  owner=('usb.cutoff','17')if name.startswith('USB_CUTOFF_RTN')else('usb.pd','10')if name=='PD_LOCAL_GND_RETURN'else('usb.cutoff','9')if name=='USB_INPUT_GND_RETURN'else('logic_supply.ic','4')if net=='lv'else('logic_supply.ic','6')
  goal=root[G.endpoint_ids(pads,*owner)[0]]
  for i,(l,g)in enumerate(regs):
   assert l==layer and g.difference(outline.buffer(2e-6)).area<1e-6,'fill envelope'
   assert root[('fill',key,i)]==goal,('floating same-net filled island',name)
   for x in allcu:
    ls={x['layer']}if'layer'in x else x['layers']
    if x['net']!=net and l in ls:assert g.distance(x['geom'])>=.15-2e-6,('foreign fill clearance',name,x['uuid'])
   for p in pads:
    if p['kind']=='np_thru_hole':assert g.distance(p['geom'])>=.2-2e-6,'fill hole clearance'
    elif p['net']!=net and l in p['layers']:assert g.distance(p['geom'])>=.15-2e-6,'fill land clearance'
  zone_results.append(dict(name=name,net=net,layer=layer,area=sum(g.area for l,g in regs),fragments=len(regs)))
 top=topology.audit(t,r,c,pads,ts,vs,filled,roots)
 return dict(topology=top,status='PASS physical filled'if filled else'PASS unfilled preflight',parts=len(F),tracks=len(ts),vias=len(vs),groups=len(groups),minimum=mini,finite_terminal_entries=sorted(set(terminal)),zones=zone_results)
if __name__=='__main__':
 p=Path(sys.argv[1]);out=audit(G.parse(p.read_text()),filled='--filled'in sys.argv);print(json.dumps(out,indent=2))
