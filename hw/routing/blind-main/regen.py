"""Replay reviewed clamp geometry on the current preceding pipeline stage.

No completed baseline is embedded. Only twelve exact low-current segments and
one obsolete NTC via are removed; every other incoming copper item is retained.
"""
from pathlib import Path
import json,shutil,sys
import pcbnew,wx
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[2]
sys.path.insert(0,str(ROOT/'tools'))
from kicad_sexpr import parse,dumps,children,one
from generate_schematics import board_graph


def point(uv):return pcbnew.VECTOR2I(pcbnew.FromMM(100+uv[0]),pcbnew.FromMM(175-uv[1]))
def close(a,c):return max(abs(x-y) for x,y in zip(a,c))<.000002

def main():
 app=wx.App(False);quiet=wx.LogNull();work=ROOT/'work/main-route-build'
 source=work/'via-land-clearance.kicad_pcb';out=work/'regen.kicad_pcb'
 data=json.loads((HERE/'regen-routes.json').read_text());tree=parse(source.read_text())
 before_source=source.read_bytes();original_graph=board_graph(source)
 def uv(node,key):return [float(one(node,key)[1])-100,175-float(one(node,key)[2])]
 removed=[]
 for row in data['removed_baseline_segments']:
  found=[n for n in children(tree,'segment') if one(n,'net')[1]==row['net'] and one(n,'layer')[1]==row['layer'] and abs(float(one(n,'width')[1])-row['width_mm'])<1e-7 and close(uv(n,'start'),row['uvs'][0]) and close(uv(n,'end'),row['uvs'][1])]
  assert len(found)==1,('Exact preceding signal branch not found',row)
  removed.append(found[0]);tree.remove(found[0])
 assert len(removed)==12 and all(one(n,'net')[1] in ('PROG','pack_ntc','c_boot1-1') and one(n,'layer')[1]=='B.Cu' and float(one(n,'width')[1])<=.2 for n in removed)
 for row in data['removed_baseline_vias']:
  found=[n for n in children(tree,'via') if one(n,'net')[1]==row['net'] and close(uv(n,'at'),row['uv']) and float(one(n,'size')[1])==row['diameter_mm'] and float(one(n,'drill')[1])==row['drill_mm']]
  assert len(found)==1,('Exact redundant NTC via not found',row)
  tree.remove(found[0])
 assert len(data['removed_baseline_vias'])==1 and data['removed_baseline_vias'][0]['net']=='pack_ntc'
 prep=work/'regen-prepared.kicad_pcb';prep.write_text(dumps(tree)+'\n')
 shutil.copyfile(source.with_suffix('.kicad_pro'),prep.with_suffix('.kicad_pro'))
 b=pcbnew.LoadBoard(str(prep));parts={f.GetFieldText('atopile_address'):f for f in b.GetFootprints()}
 for address,(target,angle) in data['moves'].items():
  f=parts[address]
  assert f.GetPosition()==point(target) and abs(f.GetOrientationDegrees()%360-angle%360)<1e-7,('Final placement plan disagrees with clamp data',address)
 layers={pcbnew.LayerName(l):l for l in (pcbnew.F_Cu,pcbnew.B_Cu,pcbnew.In2_Cu)}
 nets=b.GetNetsByName();incoming={t.m_Uuid.AsString():signature(t) for t in b.GetTracks()};new=[]
 for row in data['routes']:
  assert row['net'] in nets
  for a,c in zip(row['uvs'],row['uvs'][1:]):
   assert a!=c
   t=pcbnew.PCB_TRACK(b);t.SetStart(point(a));t.SetEnd(point(c));t.SetWidth(pcbnew.FromMM(row['width_mm']));t.SetLayer(layers[row['layer']]);t.SetNet(nets[row['net']]);b.Add(t);new.append(t)
 positions={(t.GetPosition().x,t.GetPosition().y) for t in b.GetTracks() if isinstance(t,pcbnew.PCB_VIA)}
 for row in data['vias']:
  p=point(row['uv']);assert (p.x,p.y) not in positions,'Duplicate via position';positions.add((p.x,p.y))
  v=pcbnew.PCB_VIA(b);v.SetPosition(p);v.SetWidth(pcbnew.FromMM(row['diameter_mm']));v.SetDrill(pcbnew.FromMM(row['drill_mm']));v.SetLayerPair(pcbnew.F_Cu,pcbnew.B_Cu);v.SetNet(nets[row['net']]);b.Add(v);new.append(v)
 assert len(new)==249
 for item in new:
  if isinstance(item,pcbnew.PCB_VIA) or item.GetLayer()==pcbnew.F_Cu:
   assert item.GetEffectiveShape(pcbnew.F_Cu).BBox().GetX()>=pcbnew.FromMM(101.25),'Reserved west USB channel infringed'
 actual={t.m_Uuid.AsString():signature(t) for t in b.GetTracks()}
 assert all(actual[k]==value for k,value in incoming.items()),'Unrelated incoming copper changed'
 b.BuildConnectivity();pcbnew.ZONE_FILLER(b).Fill(b.Zones());pcbnew.SaveBoard(str(out),b)
 shutil.copyfile(source.with_suffix('.kicad_pro'),out.with_suffix('.kicad_pro'))
 assert source.read_bytes()==before_source and original_graph==board_graph(out)
 print('Replayed local clamp: 12 reviewed low-current segment replacements, 1 obsolete NTC via removed, 249 new items; all other incoming copper unchanged.')

def signature(t):
 if isinstance(t,pcbnew.PCB_VIA):return ('via',t.GetPosition().x,t.GetPosition().y,t.GetNetname(),t.GetDrillValue(),t.GetWidth(pcbnew.F_Cu),tuple(t.GetLayerSet().Seq()))
 return ('segment',t.GetStart().x,t.GetStart().y,t.GetEnd().x,t.GetEnd().y,t.GetNetname(),t.GetLayer(),t.GetWidth())
if __name__=='__main__':main()
