"""Manual 3.3 V module-feed experiment, with no changes to RF reservations."""
from pathlib import Path
import sys
import pcbnew,wx
sys.path.insert(0,'tools');from generate_schematics import board_graph
app=wx.App(False);quiet=wx.LogNull();folder=Path('work/main-route-build')
src=folder/'local-power-route.kicad_pcb';out=folder/'module-power-route.kicad_pcb';b=pcbnew.LoadBoard(str(src))
parts={f.GetFieldText('atopile_address'):f for f in b.GetFootprints()}
def pad(a,n):return next(p for p in parts[a].Pads() if p.GetNumber()==str(n))
def point(uv):return pcbnew.VECTOR2I(pcbnew.FromMM(100+uv[0]),pcbnew.FromMM(175-uv[1]))
def uv(p):return [pcbnew.ToMM(p.GetPosition().x)-100,175-pcbnew.ToMM(p.GetPosition().y)]
def trace(net,points,width=.3,layer=pcbnew.F_Cu):
 for a,c in zip(points,points[1:]):
  t=pcbnew.PCB_TRACK(b);t.SetStart(point(a));t.SetEnd(point(c));t.SetWidth(pcbnew.FromMM(width));t.SetLayer(layer);t.SetNetCode(net);b.Add(t)
def via(net,p,diam=.6,drill=.3):
 v=pcbnew.PCB_VIA(b);v.SetPosition(point(p));v.SetWidth(pcbnew.FromMM(diam));v.SetDrill(pcbnew.FromMM(drill));v.SetViaType(pcbnew.VIATYPE_THROUGH);v.SetLayerPair(pcbnew.F_Cu,pcbnew.B_Cu);v.SetNetCode(net);b.Add(v)
rail=pad('controller.mcu',2).GetNetCode();ground=pad('controller.mcu',1).GetNetCode()
assert rail==pad('logic_supply.c_output2',1).GetNetCode()
# Two vias beyond the power pad, under the body, never in the solder land.
for at in ([6.95,66.24],[7.75,66.24]):
 trace(rail,[uv(pad('controller.mcu',2)),at],.6);via(rail,at)
for n,at in [(1,[6.95,67.51]),(28,[22.05,67.51])]:
 trace(ground,[uv(pad('controller.mcu',n)),at],.6);via(ground,at)
# Existing module ground grid is tied to the dedicated In1 return plane.
# 3.3 V trunk on In2 stays within the permitted body region, clear of RF zones.
trace(rail,[[6.95,66.24],[7.75,66.24],[8.5,65.49],[8.5,49.3],[9.2,48.6],[9.2,40.2]],1.2,pcbnew.In2_Cu)
for a,n,at in [('controller.c_bypass',1,[14.58,49.0]),('controller.c_bulk',1,[17.6,49.3])]:
 p=pad(a,n);assert p.GetNetCode()==rail
 trace(rail,[uv(p),at],.3 if 'bypass' in a else .7);via(rail,at)
trace(rail,[[8.5,49.3],[14.28,49.3],[14.58,49.0],[14.88,49.3],[17.6,49.3]],1.2,pcbnew.In2_Cu)
for a,n,at in [('controller.c_bypass',2,[15.42,47.2]),('controller.c_bulk',2,[19.6,49.3])]:
 p=pad(a,n);assert p.GetNetCode()==ground
 trace(ground,[uv(p),at],.3 if 'bypass' in a else .7);via(ground,at)
b.BuildConnectivity();pcbnew.ZONE_FILLER(b).Fill(b.Zones());pcbnew.SaveBoard(str(out),b)
assert board_graph(src)==board_graph(out)
out.with_suffix('.kicad_pro').write_bytes(src.with_suffix('.kicad_pro').read_bytes())
print('Segments',sum(type(t).__name__=='PCB_TRACK' for t in b.GetTracks()),'vias',sum(type(t).__name__=='PCB_VIA' for t in b.GetTracks()))
