"""Emit owned finite routing onto a hash-bound, genuinely unrouted 206-part capture.
No completed-board baseline or experimental-stage imports. Native fill is separate.
"""
from pathlib import Path
import json,copy,hashlib,uuid,shutil,sys,argparse,collections
import geometry as G,contracts as C,library
D=Path(__file__).parent
NAMESPACE=uuid.UUID('a0bd1caa-2c24-5aa5-85ba-d4450c801bd3')
def read(name):return json.loads((D/name).read_text())
def hash_text(s):return hashlib.sha256(s.encode()).hexdigest()
def inputs(source_root=None,*,snapshot=False):
 assert (source_root is not None)!=snapshot,'choose explicit live source_root or snapshot replay'
 root=Path(source_root)if source_root is not None else D/'source'
 b=read('source-binding.json')
 for p,h in b['files'].items():assert G.sha(root/p)==h,('stale bound source',p)
 return b,root

def validate_records(r,parts,nets):
 assert r['schema']==1 and len(r['copper'])==636 and len(r['zones'])==6,'record inventory'
 ids=set()
 for q in r['copper']+r['zones']:
  assert q['kind']in ['segment','via','zone']and q['block']in ['socket','usb_data','mcu_supply','regulator','pd','usb_protection']and q['name'],'unowned route record'
  assert q['uuid']not in ids,'duplicate record UUID';ids.add(q['uuid'])
  node=G.parse(q['sexpr']);assert node[0]==q['kind']and G.one(node,'uuid')[1]==q['uuid'],'record identity mismatch'
  assert G.one(node,'net')[-1]==q['net']and q['net']in nets,'record net missing from source'
  if q['kind']!='zone':
   assert hash_text(q['sexpr'])==q['record_sha256'],'stale record geometry'
   for a,p in q['own_pads']:
    pp=[x for x in G.children(parts[a],'pad')if str(x[1])==p]
    assert pp and all(G.one(x,'net')[-1]==q['net']for x in pp),'record owner pin net'
  else:assert not G.children(node,'filled_polygon')and not G.children(node,'keepout'),'owned zones must be unfilled netted definitions'
 return ids

def build(source_root=None,*,snapshot=False):
 b,root=inputs(source_root,snapshot=snapshot);t=G.parse((root/b['source']).read_text());semantic=G.canonical_nets(t);F=G.parts(t);SF=G.parts(semantic);review=read('reviewed-parts.json')['parts'];r=read('routing-records.json');bc=read('reviewed-board-contract.json')
 assert C.graph(t)==b['graph'],'source circuit mismatch'
 assert not G.children(t,'segment')and not G.children(t,'via'),'source not unrouted'
 assert len(G.children(t,'zone'))==8 and all(G.children(x,'keepout')and not G.children(x,'filled_polygon')for x in G.children(t,'zone')),'source rules/fills'
 nets={str(q[2]):str(q[1])for q in G.children(t,'net')};assert nets,'expected source numeric-net map'
 validate_records(r,SF,nets)
 pose_changes={};silk_changes=[];models_changed=[];uuid_map={};seen=set();attribute_overlays={}
 for a,f in F.items():
  q=review[a];before=G.pose(f)
  if a in ['charger.inductor','regen.thermostat']:
   attrs=G.one(f,'attr');assert attrs[1:]==['through_hole'],('unexpected SMD overlay preimage',a,attrs)
   assert all(p[2]=='smd'for p in G.children(f,'pad')),('SMD overlay has non-SMD pad',a)
   attribute_overlays[a]=dict(before=list(attrs[1:]),after=['smd']);attrs[1:]=[G.Atom('smd')]
  assert before==b['parts'][a]['pose'],'stale source pose'
  assert C.equivalent(C.pad_contract(SF[a]),b['parts'][a]['pads']),'stale source lands'
  if before!=q['pose_uv']:pose_changes[a]=dict(before=before,after=q['pose_uv']);C.place(f,q['pose_uv'])
  if G.graphics(f,'F.SilkS')!=q['silk']:
   silk_changes.append(a)
   for x in list(C.layer_graphics(f,'F.SilkS')):f.remove(x)
   f.extend(G.parse(x)for x in q['silk_sexpr'])
  old=[G.dumps(x)for x in G.children(f,'model')]
  for x in list(G.children(f,'model')):f.remove(x)
  for m in q['models']:
   p=D/'models'/(m['sha256']+m['extension']);assert G.sha(p)==m['sha256'],'model content binding'
   x=G.parse(m['transform_sexpr']);x[1]='${KIPRJMOD}/models/'+p.name;f.append(x)
  if old!=[G.dumps(x)for x in G.children(f,'model')]:models_changed.append(a)
  # Native diagnostics need globally unique child IDs. Owning FP UUID/path and
  # all physical pin/net identities remain source-owned; mapping is reported.
  fmap={}
  for i,x in enumerate(G.walk(f,'uuid')):
   if x is G.one(f,'uuid'):continue
   oldid=str(x[1]);new=str(uuid.uuid5(NAMESPACE,a+'/'+str(i)+'/'+oldid));x[1]=new;fmap[oldid]=new
   assert new not in seen,'child UUID collision';seen.add(new)
  for x in G.walk(f,'members'):
   x[1:]=[fmap.get(str(v),v)for v in x[1:]]
  uuid_map[a]=fmap
 assert pose_changes==b['pose_delta'],'unexpected placement delta'
 for q in r['copper']+r['zones']:
  x=G.parse(q['sexpr']);G.one(x,'net')[1:]=[G.Atom(nets[q['net']])]
  if q['kind']=='zone':
   if G.children(x,'net_name'):G.one(x,'net_name')[1]=q['net']
   else:x.insert(2,G.node('net_name',q['net']))
  t.append(x)
 assert C.graph(t)==b['graph'],'emission changed electrical graph'
 libs,aliases=library.variants(F)
 inputs(source_root,snapshot=snapshot) # Detect concurrent mutation across source reads.
 return t,dict(library_variants={n:G.dumps(v)for n,v in libs.items()},library_alias_mapping=aliases,attribute_overlays=attribute_overlays,source_root=str(root.resolve()),replay_mode='snapshot'if snapshot else'live source',source_sha256=b['files'][b['source']],source_parts=206,pin_identities=b['physical_pin_identities'],pose_changes=pose_changes,silk_overlay_count=len(silk_changes),silk_overlays=silk_changes,model_binding_addresses=models_changed,child_uuid_map=uuid_map,segments=sum(x['kind']=='segment'for x in r['copper']),vias=sum(x['kind']=='via'for x in r['copper']),rule_areas=8,unfilled_zones=6,status='Unfilled source-driven partial route; native fill/DRC required; 352 historical opens are not a fresh result')

def write(out,source_root=None,*,snapshot=False):
 assert not out.exists()or not any(out.iterdir()),'output must be absent or empty; preserve earlier evidence'
 t,report=build(source_root,snapshot=snapshot);out.mkdir(parents=True,exist_ok=True);p=out/'candidate.kicad_pcb';p.write_text(G.dumps(t)+'\n');report['emitted_sha256']=G.sha(p)
 b,root=inputs(source_root,snapshot=snapshot);shutil.copyfile(root/b['project'],out/'candidate.kicad_pro')
 shutil.copytree(D/'models',out/'models',dirs_exist_ok=True)
 # Only explicitly generated reviewed variants are used for native comparison.
 lib=out/'clean-main.pretty';lib.mkdir(exist_ok=True)
 for n,v in report['library_variants'].items():(lib/(n+'.kicad_mod')).write_text(v+'\n')
 table=G.node('fp_lib_table',G.node('version',7),G.node('lib',G.node('name','clean-main'),G.node('type','KiCad'),G.node('uri','${KIPRJMOD}/clean-main.pretty'),G.node('options',''),G.node('descr','Source-owned lands with reviewed model/silk/attribute variants')))
 (out/'fp-lib-table').write_text(G.dumps(table)+'\n');report['library_variant_count']=len(report['library_variants']);del report['library_variants'];(out/'emission.json').write_text(json.dumps(report,indent=2)+'\n');inputs(source_root,snapshot=snapshot);return report
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);g=p.add_mutually_exclusive_group(required=True);g.add_argument('--source-root',type=Path);g.add_argument('--snapshot',action='store_true');a=p.parse_args();r=write(a.output,a.source_root,snapshot=a.snapshot);print(json.dumps({k:v for k,v in r.items()if k not in ['child_uuid_map','silk_overlays','model_binding_addresses','library_alias_mapping']},indent=2))
