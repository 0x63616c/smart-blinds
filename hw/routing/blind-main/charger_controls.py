"""Explicit partial charger control/sense routes; no fabrication acceptance."""
from pathlib import Path
import json,shutil,sys
import pcbnew,wx
app=wx.App(False);quiet=wx.LogNull();here=Path(__file__).resolve().parent
folder=Path("work/main-route-build")
sys.path.insert(0,"tools")
from generate_schematics import board_graph
source=folder/"charger-distribution.kicad_pcb"
b=pcbnew.LoadBoard(str(source));parts={f.GetFieldText('atopile_address'):f for f in b.GetFootprints()}
def pt(uv):return pcbnew.VECTOR2I(round((100+uv[0])*1e6),round((175-uv[1])*1e6))
def pad(a,n):return next(p for p in parts[a].Pads() if p.GetNumber()==str(n))
def close(a,c):return abs(a.x-c.x)<=2 and abs(a.y-c.y)<=2
old=pt((35.2,23.9));new=pt((35.2,24.15));changed=[]
for t in b.GetTracks():
 if isinstance(t,pcbnew.PCB_VIA) and close(t.GetPosition(),old):t.SetPosition(new);changed.append(t.m_Uuid.AsString())
 elif not isinstance(t,pcbnew.PCB_VIA):
  touched=False
  if close(t.GetStart(),old):t.SetStart(new);touched=True
  if close(t.GetEnd(),old):t.SetEnd(new);touched=True
  if touched:changed.append(t.m_Uuid.AsString())
assert len(changed)==3
# VAC1 and VAC2 are low-current input sensing; use In2 for the short
# connection to the established USB/charger input trunk.
net=pad('charger.ic',8).GetNetCode()
for points,layer in [([pad('charger.ic',8).GetPosition(),pad('charger.ic',9).GetPosition()],pcbnew.F_Cu),
 ([pad('charger.ic',9).GetPosition(),pt((26.5,22.2)),pt((25.3,22.2)),pt((24.7,21.6)),pt((24.7,21.4))],pcbnew.F_Cu),
 ([pt((24.7,21.4)),pt((23.25,21.4)),pt((23.1,21.55))],pcbnew.In2_Cu)]:
 for a,c in zip(points,points[1:]):
  t=pcbnew.PCB_TRACK(b);t.SetStart(a);t.SetEnd(c);t.SetWidth(150000);t.SetLayer(layer);t.SetNetCode(net);b.Add(t)
v=pcbnew.PCB_VIA(b);v.SetPosition(pt((24.7,21.4)));v.SetWidth(500000);v.SetDrill(250000);v.SetViaType(pcbnew.VIATYPE_THROUGH);v.SetLayerPair(pcbnew.F_Cu,pcbnew.B_Cu);v.SetNetCode(net);b.Add(v)
paths=json.loads((here/'charger-control-routes.json').read_text())
for r in paths:
 for p in r['path']:p[:2]=[round(x,6) for x in p[:2]]
 source_pad=pad(*r['start']);net=source_pad.GetNetCode();assert source_pad.GetNetname()==r['net']
 dest=None if r['end'][0] in ('escape','plane') else pad(*r['end'])
 if dest:assert dest.GetNetCode()==net
 for a,c in zip(r['path'],r['path'][1:]):
  ap,cp=pt(a[:2]),pt(c[:2])
  if close(ap,source_pad.GetPosition()):ap=source_pad.GetPosition()
  if dest and close(cp,dest.GetPosition()):cp=dest.GetPosition()
  if a[2]!=c[2]:
   assert a[:2]==c[:2]
   if any(isinstance(t,pcbnew.PCB_VIA) and close(t.GetPosition(),ap) and t.GetNetCode()==net for t in b.GetTracks()):continue
   t=pcbnew.PCB_VIA(b);t.SetPosition(ap);t.SetWidth(500000);t.SetDrill(250000);t.SetViaType(pcbnew.VIATYPE_THROUGH);t.SetLayerPair(pcbnew.F_Cu,pcbnew.B_Cu)
  else:
   t=pcbnew.PCB_TRACK(b);t.SetStart(ap);t.SetEnd(cp);t.SetWidth(round(r.get('width',.15)*1e6));t.SetLayer(pcbnew.F_Cu if a[2]=='F' else pcbnew.B_Cu)
  t.SetNetCode(net);b.Add(t)
b.BuildConnectivity();pcbnew.ZONE_FILLER(b).Fill(b.Zones())
out=folder/'charger-controls.kicad_pcb';pcbnew.SaveBoard(str(out),b)
shutil.copyfile(source.with_suffix('.kicad_pro'),out.with_suffix('.kicad_pro'))
assert board_graph(source)==board_graph(out)
print('Added charger sensing, control networks and local returns; graph preserved')
