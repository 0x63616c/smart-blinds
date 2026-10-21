"""Pure KiCad geometry; no study imports, native APIs or import-time board reads.
Extracted from reviewed usb54-actual-audit and pd54-return-refinement helpers.
"""
import collections,copy,hashlib,json,math,sys
from pathlib import Path
from shapely.geometry import Point,Polygon,LineString,box
from shapely.affinity import rotate,translate,scale
from shapely.ops import unary_union
from shapely.validation import make_valid
from sexpr import parse,children,one,walk,Atom,node,dumps
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def norm(x):
 if isinstance(x,list):return [norm(v)for v in x]
 if isinstance(x,Atom):
  try:return round(float(x),9)
  except ValueError:return str(x)
 return x
def props(f):return {x[1]:x[2]for x in children(f,'property')}
def parts(t):
 out={}
 for f in children(t,'footprint'):
  a=props(f)['atopile_address'];assert a not in out,'duplicate address';out[a]=f
 return out
def pose(f):
 x,y,*a=map(float,one(f,'at')[1:]);return [round(x-100,9),round(175-y,9),a[0]if a else 0]
def cu_layers(p):
 ls=set(one(p,'layers')[1:]);return {'F.Cu','In1.Cu','In2.Cu','B.Cu'} if '*.Cu'in ls else ls&{'F.Cu','In1.Cu','In2.Cu','B.Cu'}
def shape(p):
 w,h=map(float,one(p,'size')[1:]);s=p[3]
 if s=='rect':return box(-w/2,-h/2,w/2,h/2)
 if s=='roundrect':
  z=float(one(p,'roundrect_rratio')[1])*min(w,h);return box(-w/2+z,-h/2+z,w/2-z,h/2-z).buffer(z,quad_segs=64)
 if s=='circle':return Point(0,0).buffer(w/2,quad_segs=64)
 if s=='oval':return (LineString([(-(w-h)/2,0),((w-h)/2,0)]).buffer(h/2,quad_segs=64)if w>=h else LineString([(0,-(h-w)/2),(0,(h-w)/2)]).buffer(w/2,quad_segs=64))
 if s=='custom':
  anchor=one(one(p,'options'),'anchor')[1];gs=[Point(0,0).buffer(w/2,quad_segs=64)if anchor=='circle'else box(-w/2,-h/2,w/2,h/2)]
  for q in one(p,'primitives')[1:]:
   assert q[0]=='gr_poly';g=Polygon([list(map(float,x[1:]))for x in children(one(q,'pts'),'xy')]);ww=float(one(q,'width')[1])if children(q,'width')else float(one(one(q,'stroke'),'width')[1])if children(q,'stroke')else 0;gs.append(g.buffer(ww/2,quad_segs=64)if ww else g)
  return unary_union(gs)
 raise ValueError(s)
def geometry(f,p):
 u,v,r=pose(f);px,py,*ar=map(float,one(p,'at')[1:]);centre=rotate(Point(px,-py),r,origin=(0,0));centre=[u+centre.x,v+centre.y]
 # Saved KiCad pad orientation is absolute; pad centre remains footprint-local.
 angle=ar[0]if ar else 0
 return centre,translate(rotate(scale(shape(p),yfact=-1,origin=(0,0)),angle,origin=(0,0)),*centre)
def copper(t):
 tracks=[];vias=[]
 for s in children(t,'segment'):
  a=[float(one(s,'start')[1])-100,175-float(one(s,'start')[2])];z=[float(one(s,'end')[1])-100,175-float(one(s,'end')[2])];w=float(one(s,'width')[1]);n=one(s,'net')[-1]
  tracks.append(dict(a=a,b=z,width=w,net=n,layer=one(s,'layer')[1],uuid=one(s,'uuid')[1],geom=LineString([a,z]).buffer(w/2,quad_segs=64)))
 for s in children(t,'via'):
  x,y=map(float,one(s,'at')[1:]);a=[x-100,175-y];d=float(one(s,'size')[1]);dr=float(one(s,'drill')[1]);ls=one(s,'layers')[1:]
  assert ls==['F.Cu','B.Cu'],'unexpected non-through via'
  vias.append(dict(at=a,diameter=d,drill=dr,net=one(s,'net')[-1],uuid=one(s,'uuid')[1],layers={'F.Cu','In1.Cu','In2.Cu','B.Cu'},geom=Point(a).buffer(d/2,quad_segs=64)))
 return tracks,vias
PAD_FIELDS={'at','size','drill','layers','roundrect_rratio','chamfer_ratio','chamfer','primitives','options','offset','solder_mask_margin','solder_paste_margin','solder_paste_margin_ratio','remove_unused_layers','keep_end_layers'}
def padphysical(p):return norm(p[:4]+sorted([x for x in p[4:]if isinstance(x,list)and x[0]in PAD_FIELDS],key=lambda x:str(x[0])))
def by_uuid(f):
 ps={one(p,'uuid')[1]:p for p in children(f,'pad')};assert len(ps)==len(children(f,'pad'));return ps
def graphics(f,layer):
 out=[]
 for x in f:
  if not(isinstance(x,list)and x[0].startswith('fp_')and children(x,'layer')and one(x,'layer')[1]==layer):continue
  q=copy.deepcopy(x);q[:]=[v for v in q if not(isinstance(v,list)and v[0]=='uuid')]
  for v in children(q,'fill'):
   if v[1]=='none':v[1]=Atom('no')
   if v[1]=='solid':v[1]=Atom('yes')
  out.append(norm(q))
 return sorted(out,key=str)
def filled_regions(z):
 """Decode native fracture bridges without treating zero-width seams as copper.

 KiCad may serialize a holed fill as one ring with doubled, zero-area bridge
 edges. Keep only valid area polygons, require signed-ring area preservation,
 and expose every disconnected polygon independently to continuity checks.
 """
 result=[]
 for fp in children(z,'filled_polygon'):
  raw=Polygon([[float(p[1])-100,175-float(p[2])]for p in children(one(fp,'pts'),'xy')])
  valid=make_valid(raw)
  def areas(g):
   if g.geom_type=='Polygon':return [g]
   return [p for x in getattr(g,'geoms',[])for p in areas(x)]
  ps=areas(valid);assert ps and abs(sum(p.area for p in ps)-raw.area)<1e-6,'invalid or area-changing native fill'
  for p in ps:
   assert p.is_valid and p.area>0
   result.append((one(fp,'layer')[1],p))
 return result

def copper_nodes(t,net,pads,ts,vs,skip_pad=None):
 ss=[dict(id=('pad',p['a'],p['p']),geom=p['geom'],layers=p['layers'])for p in pads if p['net']==net and(p['a'],p['p'])!=skip_pad]
 ss.extend(dict(id=('copper',x['uuid']),geom=x['geom'],layers={x['layer']}if'layer'in x else set(x['layers']))for x in ts+vs if x['net']==net)
 for z in children(t,'zone'):
  if children(z,'keepout')or one(z,'net')[-1]!=net:continue
  for i,(layer,shape)in enumerate(filled_regions(z)):
   ss.append(dict(id=('fill',one(z,'uuid')[1],i),geom=shape,layers={layer}))
 return ss

def components(ss):
 roots=list(range(len(ss)))
 def root(i):
  while roots[i]!=i:i=roots[i]
  return i
 for i,x in enumerate(ss):
  for j,y in enumerate(ss[:i]):
   if x['layers']&y['layers']and x['geom'].distance(y['geom'])<1e-8:roots[root(i)]=root(j)
 return {tuple(x['id']):root(i)for i,x in enumerate(ss)}


def canonical_nets(tree):
 """Pure semantic view for legacy numeric and native10 name-only net records."""
 t=copy.deepcopy(tree);defs={str(q[1]):str(q[2])for q in children(t,'net')if len(q)==3}
 for q in walk(t,'net'):
  if len(q)==3:q[1:]=[str(q[2])]
  elif len(q)==2 and str(q[1])in defs:q[1:]=[defs[str(q[1])]]
 for q in list(children(t,'net')):t.remove(q)
 return t

def gather(t,contracts):
 F=parts(t);ts,vs=copper(t);pads=[]
 for a,f in F.items():
  for idx,p in enumerate(children(f,'pad')):
   at,g=geometry(f,p);pads.append(dict(a=a,p=str(p[1]),index=idx,at=at,geom=g,net=one(p,'net')[-1]if children(p,'net')else None,layers=cu_layers(p),kind=p[2]))
 return F,ts,vs,pads,{a:Polygon(x)for a,x in contracts['bodies'].items()},{a:Polygon(x)for a,x in contracts['courts'].items()}

def physical_nodes(t,net,pads,ts,vs,skip_pad=None):
 ss=[dict(id=('pad',p['a'],p['p'],p['index']),geom=p['geom'],layers=p['layers'])for p in pads if p['net']==net and(p['a'],p['p'])!=skip_pad]
 ss.extend(dict(id=('copper',x['uuid']),geom=x['geom'],layers={x['layer']}if'layer'in x else set(x['layers']))for x in ts+vs if x['net']==net)
 for z in children(t,'zone'):
  if children(z,'keepout')or one(z,'net')[-1]!=net:continue
  for i,(layer,g)in enumerate(filled_regions(z)):ss.append(dict(id=('fill',one(z,'uuid')[1],i),geom=g,layers={layer}))
 return ss

def endpoint_ids(pads,a,p):
 ids=[('pad',q['a'],q['p'],q['index'])for q in pads if(q['a'],q['p'])==(a,p)]
 assert ids,('missing physical pin',a,p)
 return ids
