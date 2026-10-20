"""Replay explicit reviewed candidates; no route search during reproduction."""
from pathlib import Path
import json,importlib.util,shutil
import pcbnew
HERE=Path(__file__).resolve().parent
FOLDER=Path('work/main-route-build')
source=FOLDER/'usb-power-route.kicad_pcb';dest=FOLDER/'usb-control-route.kicad_pcb'
import wx
app=wx.App(False);quiet=wx.LogNull()
b=pcbnew.LoadBoard(str(source))
class Geometry:
 F=pcbnew.F_Cu;B=pcbnew.B_Cu
 @staticmethod
 def P(at):return pcbnew.VECTOR2I(pcbnew.FromMM(100+at[0]),pcbnew.FromMM(175-at[1]))
 @staticmethod
 def local(p):return (pcbnew.ToMM(p.x)-100,175-pcbnew.ToMM(p.y))
 @staticmethod
 def pad(a,n):return next(p for f in b.GetFootprints() if f.GetFieldText('atopile_address')==a for p in f.Pads() if p.GetNumber()==str(n))
m=Geometry
records=json.loads((HERE/'usb-control-routes.json').read_text())
def via(net,at):
 pos=m.P(at)
 if any(isinstance(t,pcbnew.PCB_VIA) and t.GetPosition()==pos and t.GetNetCode()==net for t in b.GetTracks()):return
 v=pcbnew.PCB_VIA(b);v.SetPosition(pos);v.SetWidth(pcbnew.FromMM(.6));v.SetDrill(pcbnew.FromMM(.3));v.SetViaType(pcbnew.VIATYPE_THROUGH);v.SetLayerPair(m.F,m.B);v.SetNetCode(net);b.Add(v)
def track(net,a,c,layer):
 if a==c:return
 t=pcbnew.PCB_TRACK(b);t.SetStart(m.P(a));t.SetEnd(m.P(c));t.SetLayer(m.F if layer=='F' else m.B);t.SetWidth(pcbnew.FromMM(.2));t.SetNetCode(net);b.Add(t)
for r in records['paths']:
 p,q=m.pad(*r['start']),m.pad(*r['end']);assert p.GetNetname()==q.GetNetname()==r['net'];net=p.GetNetCode()
 assert m.P(r['path'][0][:2])==p.GetPosition() and m.P(r['path'][-1][:2])==q.GetPosition()
 for a,c in zip(r['path'],r['path'][1:]):
  if a[2]!=c[2]:
   assert a[:2]==c[:2];via(net,a[:2])
  else:track(net,a[:2],c[:2],a[2])
for r in records['grounds']:
 p=m.pad(*r['pad']);assert p.GetNetname()=='lv'
 track(p.GetNetCode(),list(m.local(p.GetPosition())),r['via'],'F');via(p.GetNetCode(),r['via'])
b.BuildConnectivity();pcbnew.ZONE_FILLER(b).Fill(b.Zones());pcbnew.SaveBoard(str(dest),b)
print('Segments:',sum(not isinstance(t,pcbnew.PCB_VIA) for t in b.GetTracks()),'Vias:',sum(isinstance(t,pcbnew.PCB_VIA) for t in b.GetTracks()))

dest.with_suffix('.kicad_pro').write_bytes(source.with_suffix('.kicad_pro').read_bytes())
