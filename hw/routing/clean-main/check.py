"""Current54x80 source/route check; does not dispatch historical196-part checks."""
from pathlib import Path
import argparse,json,math,copy,collections
import geometry as G,contracts as C,emit,validate
D=Path(__file__).parent

def geometry_key(x):
 return {k:(sorted(v)if isinstance(v,set)else [round(y,9)for y in v]if isinstance(v,list)else round(v,9)if isinstance(v,float)else v)for k,v in x.items()if k!='geom'}
def model_key(m):
 return G.norm([x for x in m[2:]])
def verify(t,board_path,filled=False,inventory=True,geometry=True,source_root=None,snapshot=False):
 expected,emission=emit.build(source_root,snapshot=snapshot);e=G.canonical_nets(expected);t=G.canonical_nets(t);F=G.parts(t);EF=G.parts(e);review=emit.read('reviewed-parts.json')['parts']
 assert C.graph(t)==C.graph(e),'compiled source graph changed'
 assert set(F)==set(EF),'duplicate/missing source address'
 for a,f in F.items():
  assert G.pose(f)==G.pose(EF[a]),('source pose delta',a)
  assert G.norm(G.children(f,'attr'))==G.norm(G.children(EF[a],'attr')),('reviewed assembly attributes',a)
  for layer in ['F.SilkS','F.CrtYd','F.Paste','F.Mask']:
   assert G.graphics(f,layer)==G.graphics(EF[a],layer),('reviewed graphics changed',a,layer)
  ms=G.children(f,'model');es=G.children(EF[a],'model');assert len(ms)==len(es),('model count',a)
  for m,ex,ref in zip(ms,es,review[a]['models']):
   assert model_key(m)==model_key(ex),('reviewed model transform',a)
   p=board_path.parent/str(m[1]).replace('${KIPRJMOD}/','');assert p.is_file()and G.sha(p)==ref['sha256'],('reviewed model content',a)
  # Source owns library alias/instance UUID/path. Child diagnostic UUIDs are
  # deterministic, namespaced and recorded; net/pin identities remain intact.
  assert G.one(f,'uuid')==G.one(EF[a],'uuid'),('source footprint UUID',a)
  for key in ['path','sheetname','sheetfile']:
   assert G.norm(G.children(f,key))==G.norm(G.children(EF[a],key)),('source association',a,key)
 ids=[str(x[1])for x in G.walk(t,'uuid')];assert len(ids)==len(set(ids)),'duplicate board item UUID'
 for typ in ['gr_line','gr_arc','gr_poly','gr_rect','gr_circle']:
  assert G.norm(G.children(t,typ))==G.norm(G.children(e,typ)),('outline/board graphic changed',typ)
 assert G.norm(G.children(t,'layers'))==G.norm(G.children(e,'layers')),'layer stack names/order'
 assert G.norm(G.children(G.one(t,'setup'),'stackup'))==G.norm(G.children(G.one(e,'setup'),'stackup')),'reviewed physical stackup changed'
 assert G.norm(G.children(t,'general'))==G.norm(G.children(e,'general')),'board thickness/general changed'
 binding=emit.read('source-binding.json');assert G.sha(board_path.with_suffix('.kicad_pro'))==binding['files'][binding['project']],'native project rules changed'
 def zkey(z):
  # Native may add inert keepout fill defaults and replace numeric nets with
  # names; finite geometry and all forbid/allow settings remain explicit.
  return {k:G.norm(G.children(z,k))for k in ['uuid','name','layer','layers','keepout','polygon','priority','connect_pads','min_thickness','fill','thermal_gap','thermal_bridge_width']if G.children(z,k)}
 z={G.one(x,'uuid')[1]:x for x in G.children(t,'zone')};ez={G.one(x,'uuid')[1]:x for x in G.children(e,'zone')};assert set(z)==set(ez),'missing/extra zone or rule area'
 for k,v in z.items():
  if G.children(v,'keepout'):
   for field in ['name','layer','layers','keepout','polygon']:
    assert G.norm(G.children(v,field))==G.norm(G.children(ez[k],field)),('mechanical rule changed',k,field)
  else:
   assert G.one(v,'net')[-1]==G.one(ez[k],'net')[-1],'zone rail changed'
   assert zkey(v)==zkey(ez[k]),('finite zone policy changed',k)
 if inventory:
  old={x['uuid']:geometry_key(x)for x in sum(G.copper(e),[])};new={x['uuid']:geometry_key(x)for x in sum(G.copper(t),[])};assert new==old,'owned copper inventory/geometry changed'
 result=validate.audit(t,filled,inventory=inventory,geometry=geometry);result.update(source_driven=True,board_sha256=G.sha(board_path),source_sha256=emission['source_sha256'],model_contents_verified=True,library_variant_count=len(emission['library_variants']),attribute_overlays=emission['attribute_overlays'],source_graph_verified=True,remaining_opens='352 historical checkpoint; native DRC required for this output')
 return result
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('board',type=Path);p.add_argument('--filled',action='store_true');p.add_argument('--output',type=Path);g=p.add_mutually_exclusive_group(required=True);g.add_argument('--source-root',type=Path);g.add_argument('--snapshot',action='store_true');a=p.parse_args();r=verify(G.parse(a.board.read_text()),a.board,a.filled,source_root=a.source_root,snapshot=a.snapshot);s=json.dumps(r,indent=2)+'\n';a.output.write_text(s)if a.output else print(s)
