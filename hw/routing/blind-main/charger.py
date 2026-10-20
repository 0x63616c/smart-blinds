"""Limited BQ25798 fast-loop/inductor experiment; never a complete routed board."""
from pathlib import Path
import json,sys,uuid
import wx,pcbnew
sys.path.insert(0,'tools');from generate_schematics import board_graph
app=wx.App(False);quiet=wx.LogNull();folder=Path('work/main-route-build');src=folder/'main-controller.kicad_pcb';out=folder/'charger-route.kicad_pcb';b=pcbnew.LoadBoard(str(src));assert not list(b.GetTracks())
parts={f.GetFieldText('atopile_address'):f for f in b.GetFootprints()}
def pad(a,n):return next(p for p in parts[a].Pads() if p.GetNumber()==str(n))
def point(xy):return pcbnew.VECTOR2I(pcbnew.FromMM(xy[0]),pcbnew.FromMM(xy[1]))
def xy(p):return [pcbnew.ToMM(p.GetPosition().x),pcbnew.ToMM(p.GetPosition().y)]
def trace(net,points,width,layer=pcbnew.F_Cu):
 for a,c in zip(points,points[1:]):
  t=pcbnew.PCB_TRACK(b);t.SetStart(point(a));t.SetEnd(point(c));t.SetWidth(pcbnew.FromMM(width));t.SetLayer(layer);t.SetNetCode(net);b.Add(t)
def via(net,p):
 v=pcbnew.PCB_VIA(b);v.SetPosition(point(p));v.SetWidth(pcbnew.FromMM(.6));v.SetDrill(pcbnew.FromMM(.3));v.SetViaType(pcbnew.VIATYPE_THROUGH);v.SetLayerPair(pcbnew.F_Cu,pcbnew.B_Cu);v.SetNetCode(net);b.Add(v)
# Direct, symmetric front-face loops to small capacitors, following TI8.4.
for a,pin,path in [('charger.c_pmid_fast',29,[[129.1,148.25],[128.58,147.73]]),('charger.c_sys_fast',25,[[130.9,148.25],[131.42,147.73]])]:
 srcpad=pad('charger.ic',pin);dest=pad(a,1);assert srcpad.GetNetCode()==dest.GetNetCode();trace(srcpad.GetNetCode(),[xy(srcpad),*path,xy(dest)],.25)
gnd=pad('charger.ic',27);gn=gnd.GetNetCode()
trace(gn,[xy(gnd),[130,147.65]],.3)
for a,x in [('charger.c_pmid_fast',129.75),('charger.c_sys_fast',130.25)]:
 p=pad(a,2);assert p.GetNetCode()==gn;trace(gn,[xy(p),[x,147.4],[130,147.65]],.3)
trace(gn,[xy(gnd),[130,151.7]],.3)
for y in (150.1,150.9,151.7):via(gn,[130,y])
for pin,x,indpin,terminal in [(28,129.1,1,127.15),(26,130.9,2,132.85)]:
 p=pad('charger.ic',pin);ip=pad('charger.inductor',indpin);net=p.GetNetCode();assert net==ip.GetNetCode()
 trace(net,[xy(p),[xy(p)[0],149.65],[x,150.1],[x,151.7]],.25)
 for y in (150.1,150.9,151.7):via(net,[x,y])
 trace(net,[[x,151.7],[x,150.1],[terminal,148.15],[terminal,143.8]],.8,pcbnew.B_Cu)
 trace(net,[[terminal-.7,143.8],[terminal+.7,143.8]],.8,pcbnew.B_Cu)
 for vx in (terminal-.7,terminal,terminal+.7):
  via(net,[vx,143.8]);trace(net,[[vx,143.8],[vx,143.2],[terminal,142.5],xy(ip)],.6)
def link(a,n,c,m,path=(),width=.25,layer=pcbnew.F_Cu):
 p,q=pad(a,n),pad(c,m);assert p.GetNetCode()==q.GetNetCode(),(a,n,c,m)
 trace(p.GetNetCode(),[xy(p),*path,xy(q)],width,layer)
def ground(a,n,at):
 p=pad(a,n);assert p.GetNetCode()==gn
 trace(gn,[xy(p),at],.3);via(gn,at)
# Same-face parallel bulk reservoirs for the two immediate switching loops.
link('charger.c_pmid_fast',1,'charger.c_pmid1',1,[[128.58,146.9],[127.18,145.5]],.6)
link('charger.c_sys_fast',1,'charger.c_sys1',1,[[131.42,146.9],[132.82,145.5]],.6)
ground('charger.c_pmid1',2,[123.71,146.95])
ground('charger.c_sys1',2,[136.29,146.95])
link('charger.ic',2,'charger.c_input_fast',1,[[127.65,149.5],[126.97,148.82]])
link('charger.ic',3,'charger.ic',2,[[127.65,149.9],[127.65,149.5]])
ground('charger.c_input_fast',2,[125.4,147.4])
ground('charger.c_input_fast',2,[126.3,147.1])  # TI 8.4.1: at least two ground vias
link('charger.ic',5,'charger.c_regn',1,[[127.35,150.7],[127.35,151.4],[126.35,152.4]])
ground('charger.c_regn',2,[123.9,149.0])
ground('charger.c_regn',2,[123.05,149.2])  # TI 8.4.1: at least two ground vias
link('charger.ic',4,'charger.c_boot1',1)
sw1=pad('charger.c_boot1',2).GetNetCode()
trace(sw1,[xy(pad('charger.c_boot1',2)),[125.3,150.02],[125.3,149.3]],.2)
via(sw1,[125.3,149.3])
trace(sw1,[[125.3,149.3],[125.3,152.8],[127.2,152.8],[129.1,150.9]],.2,pcbnew.B_Cu)
link('charger.ic',19,'charger.c_boot2',1)
sw2=pad('charger.c_boot2',2).GetNetCode()
trace(sw2,[xy(pad('charger.c_boot2',2)),[135.2,151.1]],.2);via(sw2,[135.2,151.1])
trace(sw2,[[135.2,151.1],[134.1,152.2],[131.4,152.2],[130.9,151.7]],.2,pcbnew.B_Cu)
link('charger.ic',23,'charger.c_bat1',1,[[132.5,149.5],[133.2,148.8]])
link('charger.ic',22,'charger.ic',23,[[132.5,149.9],[132.5,149.5]])
bn=pad('charger.c_bat1',1).GetNetCode();assert bn==pad('charger.c_bat2',1).GetNetCode()
trace(bn,[xy(pad('charger.c_bat1',1)),[134.21,147.3]],.6);via(bn,[134.21,147.3])
trace(bn,[xy(pad('charger.c_bat2',1)),[132.6,153]],.6);via(bn,[132.6,153])
trace(bn,[[134.21,147.3],[134.21,151.39],[132.6,153]],.8,pcbnew.In2_Cu)
ground('charger.c_bat1',2,[137.39,147.35])
ground('charger.c_bat2',2,[137.39,154.45])
# Experimental dedicated internal return plane. Existing all-layer RF,
# connector-foot and clamp keepouts are retained and applied by the zone filler.
# No signal or power routing acceptance is inferred from this partial fill.
z=pcbnew.ZONE(b);z.SetZoneName('TRIAL_IN1_GND_RETURN')
z.SetLayer(pcbnew.In1_Cu);z.SetNetCode(gn)
z.SetLocalClearance(pcbnew.FromMM(.2));z.SetMinThickness(pcbnew.FromMM(.2))
z.SetThermalReliefGap(pcbnew.FromMM(.25));z.SetThermalReliefSpokeWidth(pcbnew.FromMM(.3))
z.SetPadConnection(pcbnew.ZONE_CONNECTION_FULL)
poly=z.Outline();poly.NewOutline()
for p in ((99,105),(155,105),(155,178),(99,178)):poly.Append(point(p))
b.Add(z);b.BuildConnectivity();pcbnew.ZONE_FILLER(b).Fill(b.Zones())
pcbnew.SaveBoard(str(out),b);assert board_graph(out)==board_graph(src)
out.with_suffix('.kicad_pro').write_bytes(src.with_suffix('.kicad_pro').read_bytes())
print('Experimental segments',sum(type(t).__name__=='PCB_TRACK' for t in b.GetTracks()),'vias',sum(type(t).__name__=='PCB_VIA' for t in b.GetTracks()))
