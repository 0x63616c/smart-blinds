"""Board-specific physical library variants, deduplicated independently of ref/UUID."""
import copy,hashlib,uuid,json
import geometry as G
NS=uuid.UUID('767bd555-2437-53ef-9c12-7e212ba38cc0')
def definition(f):
 q=copy.deepcopy(f);r=G.pose(q)[2]
 q[1]='VARIANT'
 # Standalone libraries require a modern version for three-point fp_arc.
 # Embedded board footprints inherit this from their enclosing board.
 q.insert(2,G.node('version',20241229))
 q[:]=[x for x in q if not(isinstance(x,list)and x[0]in ['at','uuid','path','sheetname','sheetfile','property','embedded_fonts'])]
 for p in G.children(q,'pad'):
  p[:]=[x for x in p if not(isinstance(x,list)and x[0]in ['net','pinfunction','pintype'])]
  at=G.one(p,'at');a=float(at[3])if len(at)>3 else 0;at[1:]=[at[1],at[2],G.Atom(str((a-r)%360))]
 for p in G.children(q,'fp_text'):
  at=G.one(p,'at');a=float(at[3])if len(at)>3 else 0;at[1:]=[at[1],at[2],G.Atom(str((a-r)%360))]
 def strip(x):
  if not isinstance(x,list):return x
  return [strip(v)for v in x if not(isinstance(v,list)and v[0]=='uuid')]
 q=strip(q)
 # Format-only normalization is intentionally narrow; pad shape stays exact.
 for p in G.walk(q,'layers'):p[1:]=sorted(p[1:])
 for p in G.walk(q,'at'):
  if len(p)==3:p.append(G.Atom('0'))
  p[3]=G.Atom(str(float(p[3])%360))
 return q

def variants(F):
 libraries={};mapping={}
 for a,f in F.items():
  q=definition(f);h=hashlib.sha256(json.dumps(G.norm(q),sort_keys=True,separators=(',',':')).encode()).hexdigest();name='V_'+h[:20]
  q[1]=name
  # Stable library child IDs are diagnostic only. Native library comparison
  # must still compare actual shapes, not IDs or a blanket waiver.
  for i,x in enumerate([x for x in q if isinstance(x,list)and x[0]in ['pad','fp_line','fp_arc','fp_poly','fp_rect','fp_circle','fp_text']]):x.append(G.node('uuid',str(uuid.uuid5(NS,h+'/'+str(i)))))
  if name in libraries:assert G.dumps(libraries[name])==G.dumps(q),'variant hash collision'
  else:libraries[name]=q
  mapping[a]=dict(source_alias=f[1],emitted_alias='clean-main:'+name,variant_sha256=h)
  f[1]='clean-main:'+name
 return libraries,mapping
