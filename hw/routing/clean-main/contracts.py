"""Narrow semantic contracts for compiled source and native serialization."""
import geometry as G,copy,math,collections

def semantic_pad(p):
 q=copy.deepcopy(p)
 # Order of a layer set, omitted zero orientation and explicit disabled option
 # are inert. No nonzero geometry or fabrication option is removed.
 for x in G.children(q,'layers'):x[1:]=sorted(x[1:])
 for x in G.children(q,'at'):
  if len(x)==3:x.append(G.Atom('0'))
  x[3]=G.Atom(str(float(x[3])%360))
 q[:]=[x for x in q if not(isinstance(x,list)and x[0]=='remove_unused_layers'and len(x)==2 and x[1]=='no')]
 for x in G.walk(q,'gr_poly'):
  pts=G.one(x,'pts');vs=pts[1:]
  if G.norm(vs[0])==G.norm(vs[-1]):vs=vs[:-1]
  candidates=[]
  for seq in [vs,list(reversed(vs))]:
   i=min(range(len(seq)),key=lambda i:G.norm(seq[i]));candidates.append(seq[i:]+seq[:i])
  pts[1:]=min(candidates,key=lambda v:G.norm(v))
  if not G.children(x,'width')and not G.children(x,'stroke'):x.append(G.node('width',0))
  x[1:]=sorted(x[1:],key=lambda n:str(n[0]))
 return G.padphysical(q)

def equivalent(a,b,path=''):
 if isinstance(a,list)and isinstance(b,list):
  return len(a)==len(b)and all(equivalent(x,y,path+'/'+str(a[0]))for x,y in zip(a,b))
 if isinstance(a,(int,float))and isinstance(b,(int,float)):
  # The source compiler serializes these dimensionless ratios to 7 decimals.
  eps=5.1e-8 if path.endswith('/roundrect_rratio')else 1e-9
  return abs(a-b)<=eps
 return a==b

def pad_contract(f):
 return [dict(pin=str(p[1]),net=G.one(p,'net')[-1]if G.children(p,'net')else None,physical=semantic_pad(p))for p in G.children(f,'pad')]

def graph(t):
 out={}
 for a,f in G.parts(G.canonical_nets(t)).items():
  p=G.props(f);out[a]=dict(reference=p['Reference'],alias=f[1],identity={k:p[k]for k in ['Value','Partnumber','LCSC','lcsc_id','LCSC Part']if k in p},pins=sorted([str(x[1]),G.one(x,'net')[-1]]for x in G.children(f,'pad')if G.children(x,'net')))
 return out

def strip_uuid(x):
 if not isinstance(x,list):return x
 return [strip_uuid(v)for v in x if not(isinstance(v,list)and v[0]=='uuid')]

def layer_graphics(f,layer):
 return [x for x in f if isinstance(x,list)and x[0].startswith('fp_')and G.children(x,'layer')and G.one(x,'layer')[1]==layer]


def place(f,new):
 old=G.pose(f);delta=new[2]-old[2];G.one(f,'at')[1:]=[G.Atom(str(100+new[0])),G.Atom(str(175-new[1])),G.Atom(str(new[2]))]
 for p in G.children(f,'pad'):
  a=G.one(p,'at');angle=float(a[3])if len(a)>3 else 0;a[1:]=[a[1],a[2],G.Atom(str((angle+delta)%360))]
 # Keep text upright relative to the same footprint rotation convention.
 for p in G.children(f,'property'):
  if G.children(p,'at'):
   a=G.one(p,'at');angle=float(a[3])if len(a)>3 else 0;a[1:]=[a[1],a[2],G.Atom(str((angle+delta)%360))]
