"""Physical current-return, clamp-land and reference guards; no historical imports."""
import geometry as G,json,collections,math
from shapely.geometry import Point,Polygon,LineString,box
from shapely.ops import unary_union

def audit(t,r,c,pads,ts,vs,filled,roots):
 rec={q['uuid']:q for q in r['copper']};padmap=collections.defaultdict(list)
 for p in pads:padmap[(p['a'],p['p'])].append(p)
 def land(a,p):return unary_union([q['geom']for q in padmap[(a,p)]])
 def cc(net):
  if net not in roots:roots[net]=G.components(G.physical_nodes(t,net,pads,ts,vs))
  return roots[net]
 def gid(net,a,p):return cc(net)[G.endpoint_ids(pads,a,p)[0]]
 # USB RAW/GND shunts must remain locally connected on the top layer, not
 # merely somewhere through a remote same-net plane.
 branches=[]
 for label,net,pins,names,escape in [
  ('RAW','raw-hv',[('usb.connector','B4A9'),('usb.tvs_vbus','1')],['Short RAW TVS socket neck','Short RAW TVS entry'],'4493ccfd-9269-5d49-84aa-66491b9314c5'),
  ('GND','lv',[('usb.connector','B1A12'),('usb.tvs_vbus','2')],['Short RAW TVS return'],'14904fd8-3f82-5f63-99a2-3db91d150143')]:
  ids={k for k,q in rec.items()if q['name']in names}|{escape};ss=[dict(id=('p',*p),geom=land(*p),layers={'F.Cu'})for p in pins]
  ss +=[dict(id=('s',x['uuid']),geom=x['geom'],layers={'F.Cu'})for x in ts if x['uuid']in ids and x['layer']=='F.Cu'and x['net']==net]
  rr=G.components(ss);assert len({rr[('p',*p)]for p in pins})==1,('short TVS branch cut',label);branches.append(label)
 q=c['quiet_star'];ids={k for k,p in rec.items()if p['name'].startswith(q['path_prefix'])and p['net']=='lv'and p['kind']=='segment'};star_ids=[k for k,p in rec.items()if p['name']==q['via_name']and p['kind']=='via'];assert len(star_ids)==1
 star=next(v for v in vs if v['uuid']==star_ids[0]);ss=[dict(id=('p',*p),geom=land(*p),layers={'F.Cu'})for p in q['pads']]
 ss +=[dict(id=('s',x['uuid']),geom=x['geom'],layers={'F.Cu'})for x in ts if x['uuid']in ids and x['layer']=='F.Cu'];ss.append(dict(id=('star',),geom=star['geom'],layers={'F.Cu'}));rr=G.components(ss)
 assert len({rr[('p',*p)]for p in q['pads']}|{rr[('star',)]})==1,'quiet same-face star broken'
 metal=unary_union([x['geom']for x in ss])
 for x in ts+vs:
  if x['uuid']in ids or x['uuid']==star['uuid']:continue
  if x['net']=='lv'and'F.Cu'in({x['layer']}if'layer'in x else x['layers']):assert metal.distance(x['geom'])>1e-8,'power ground bypasses quiet star'
 # Preserve explicitly reserved reference volumes. Through-via antipads remain
 # actual holes, never credited as ideal plane copper.
 usb=box(*c['reference_reservations']['USB']['rect_uv_mm']);mcu=box(*c['reference_reservations']['In1.Cu']['uv_rect'])
 for x in ts:
  if x['layer']=='In1.Cu'and x['net']!='lv':assert x['geom'].intersection(mcu).area<1e-9,'MCU reference intrusion'
  if x['layer']=='In1.Cu'and x['net']!='lv':assert x['geom'].intersection(usb).area<1e-9,'USB In1 reference intrusion'
  if x['layer']=='B.Cu'and x['net']!='lv':assert x['geom'].intersection(usb).area<1e-9,'USB B reference intrusion'
 for x in ts+vs:
  if x['net']=='usb-2':assert x['geom'].intersection(usb).area<1e-9,'RTN entered USB reference'
 thermal=[];corridor=None
 if filled:
  wings=[k for k,q in rec.items()if q['name'].startswith('Cutoff thermal ')and q['kind']=='via'];assert len(wings)==7
  goal=gid('usb-2','usb.cutoff','17')
  for k in wings:assert cc('usb-2').get(('copper',k))==goal,'RTN wing detached'
  ground=[]
  for z in G.children(t,'zone'):
   if G.children(z,'keepout'):continue
   name=G.one(z,'name')[1];net=G.one(z,'net')[-1];layer=G.one(z,'layer')[1];gs=G.filled_regions(z);g=unary_union([x for l,x in gs])
   if net=='lv'and layer=='In1.Cu':ground.append(g)
   if name.startswith('USB_CUTOFF_RTN'):
    assert net=='usb-2'and layer in ['B.Cu','In2.Cu'],'RTN identity'
    assert g.area>=(75 if layer=='B.Cu'else 50),'RTN spreading collapsed'
    assert g.intersection(usb).area<1e-8,'RTN fill entered USB reference';thermal.append(dict(layer=layer,area=g.area))
   if layer=='In1.Cu'and net!='lv':assert g.intersection(mcu).area<1e-9 and g.intersection(usb).area<1e-9,'foreign reference fill'
  g=unary_union(ground);p=c['direct_bypass_return'];line=LineString(p['points']);assert g.buffer(2e-6).covers(line.buffer(p['min_width']/2)),'direct bypass-return corridor cut'
  # Drill voids are removed. End annuli are terminals, so measure the interior
  # centerline after a0.35mm end trim; retain exact full corridor check above.
  voids=unary_union([Point(v['at']).buffer(v['drill']/2,quad_segs=64)for v in vs]);real=g.difference(voids);trim=LineString([line.interpolate(.35),line.interpolate(line.length-.35)])
  lo,hi=0.,2.
  for _ in range(40):
   mid=(lo+hi)/2
   if real.buffer(2e-6).covers(trim.buffer(mid/2)):lo=mid
   else:hi=mid
  corridor=dict(centerline_mm=line.length,interior_inscribed_width_mm=lo,drill_voids_removed=True,end_trim_mm=.35,thermal_or_current_rating=False)
 return dict(local_TVS_branches=branches,quiet_star=True,RTN_areas=thermal,direct_return=corridor,reference_reserved_not_impedance_qualified=True)
