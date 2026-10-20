"""Partial front-side regulator and motor bypass/return placement experiment."""
from pathlib import Path
import sys,json
import wx,pcbnew
sys.path.insert(0,'tools');from generate_schematics import board_graph
app=wx.App(False);quiet=wx.LogNull();folder=Path('work/main-route-build');src=folder/'charger-route.kicad_pcb';out=folder/'local-power-route.kicad_pcb';b=pcbnew.LoadBoard(str(src))
parts={f.GetFieldText('atopile_address'):f for f in b.GetFootprints()}
def pad(a,n):return next(p for p in parts[a].Pads() if p.GetNumber()==str(n))
def point(uv):return pcbnew.VECTOR2I(pcbnew.FromMM(100+uv[0]),pcbnew.FromMM(175-uv[1]))
def uv(p):return [pcbnew.ToMM(p.GetPosition().x)-100,175-pcbnew.ToMM(p.GetPosition().y)]
def trace(net,points,width=.25,layer=pcbnew.F_Cu):
 for a,c in zip(points,points[1:]):
  t=pcbnew.PCB_TRACK(b);t.SetStart(point(a));t.SetEnd(point(c));t.SetWidth(pcbnew.FromMM(width));t.SetLayer(layer);t.SetNetCode(net);b.Add(t)
def via(net,p,diam=.6,drill=.3):
 v=pcbnew.PCB_VIA(b);v.SetPosition(point(p));v.SetWidth(pcbnew.FromMM(diam));v.SetDrill(pcbnew.FromMM(drill));v.SetViaType(pcbnew.VIATYPE_THROUGH);v.SetLayerPair(pcbnew.F_Cu,pcbnew.B_Cu);v.SetNetCode(net);b.Add(v)
def link(a,n,c,m,path=(),width=.25,layer=pcbnew.F_Cu):
 p,q=pad(a,n),pad(c,m);assert p.GetNetCode()==q.GetNetCode(),(a,n,c,m)
 trace(p.GetNetCode(),[uv(p),*path,uv(q)],width,layer)
gn=pad('motor.ic',9).GetNetCode()
def ground(a,n,at,width=.3):
 p=pad(a,n);assert p.GetNetCode()==gn
 trace(gn,[uv(p),at],width);via(gn,at)
# DRV8874: flying capacitor and VM-to-VCP bypass beside their corresponding pins.
link('motor.ic',13,'motor.c_fly',1)
link('motor.ic',14,'motor.c_fly',2)
link('motor.ic',12,'motor.c_pump',1,[[39.1,28.325],[38.5,29.025]])
link('motor.ic',11,'motor.c_pump',2,[[39.25,28.975],[39.25,29.87]],.25)
link('motor.c_pump',2,'motor.c_vm',1,[[38.5,30.83]],.4)
ground('motor.c_vm',2,[38.0,31.97])
# Existing 13-pad thermal footprint has plated ground vias. Join both ground
# leads to the exposed central pad without adding a new open hole in SMD lands.
link('motor.ic',9,'motor.ic',17,[[42.0,30.275],[42.8,29.475]],.35)
link('motor.ic',15,'motor.ic',17,[[42.0,26.375]],.35)
link('motor.ic',16,'motor.r_mode',2,[[40.6,25.725]],.25)
link('motor.ic',1,'motor.r_in1',1,[[47.9,25.725],[47.9,25.3],[48.57,24.63]])
link('motor.ic',2,'motor.r_in2',1,[[47.9,26.375],[48.57,25.705]])
link('motor.ic',3,'motor.r_sleep',1)
link('motor.ic',6,'motor.r_current',1)
# Reference and current-sense paths are low-current analogue routes; spare pin7
# remains floating as specified in the circuit source.
rp=pad('motor.ic',5);rn=rp.GetNetCode()
trace(rn,[uv(rp),[47.95,28.325]],.2);via(rn,[47.95,28.325])
for a,n,at in [('motor.c_ref',1,[48.58,31.05]),('motor.r_ref_lo',1,[50.77,31.4]),('motor.r_ref_hi',2,[52.45,29.1])]:
 p=pad(a,n);assert p.GetNetCode()==rn
 trace(rn,[uv(p),at],.2);via(rn,at)
trace(rn,[[47.95,28.325],[48.58,28.955],[48.58,31.05],[50.77,31.4],[50.77,29.9],[51.57,29.1],[52.45,29.1]],.2,pcbnew.B_Cu)
for a,n,p in [('motor.r_in1',2,[49.43,23.45]),('motor.r_in2',2,[49.43,26.35]),('motor.r_sleep',2,[50.13,27.05]),('motor.r_current',2,[49.43,28.1]),('motor.c_ref',2,[49.42,29.6]),('motor.r_ref_lo',2,[52.4,30.6])]:ground(a,n,p)
# TPS62902: short SW to inductor, local VIN/GND ceramic, local softstart/mode.
link('logic_supply.ic',6,'logic_supply.c_input_fast',1,[[13.8,43.16]],.18)
link('logic_supply.ic',4,'logic_supply.c_input_fast',2,[[13.8,42.16]],.18)
ground('logic_supply.ic',4,[12.45,41.5],.25)
ground('logic_supply.c_input_fast',2,[14.8,42.28])
link('logic_supply.c_input_fast',1,'logic_supply.c_input',1,[[14.9,44.02],[14.9,44.59]],.6)
link('logic_supply.c_input',1,'logic_supply.c_input2',1,[],.8)
for a in ('logic_supply.c_input','logic_supply.c_input2'):ground(a,2,[uv(pad(a,2))[0],40.5],.6)
link('logic_supply.ic',2,'logic_supply.inductor',1,[[10.8,42.66],[10.46,43]],.25)
# Thicken only after the fine-pitch lead escape.
trace(pad('logic_supply.ic',2).GetNetCode(),[[10.2,43],[8.85,43]],.65)
link('logic_supply.ic',3,'logic_supply.c_output_fast',1,[[11.37,41.55]],.2)
link('logic_supply.ic',8,'logic_supply.c_softstart',1,[],.2)
link('logic_supply.ic',7,'logic_supply.r_mode',1,[[13.1,43.84],[14,44.74]],.2)
ground('logic_supply.c_softstart',2,[11.3,45.92],.3)
ground('logic_supply.r_mode',2,[14.8,45.93],.3)
# Output reservoir trunk is separate from the narrow VOS sense branch.
link('logic_supply.inductor',2,'logic_supply.c_output1',1,[[5.15,39.35]],.8)
rail=pad('logic_supply.c_output1',1).GetNetCode()
for a,points in [('logic_supply.c_output1',[(5.1,40.2),(5.9,40.2)]),('logic_supply.c_output2',[(9.2,40.2),(10.0,40.2)])]:
 p=pad(a,1)
 for at in points:
  trace(rail,[uv(p),at],.6);via(rail,at)
trace(rail,[[5.1,40.2],[10.0,40.2]],.9,pcbnew.B_Cu)
ground('logic_supply.c_output1',2,[7.5,38.0],.5)
ground('logic_supply.c_output2',2,[12.0,38.0],.5)
ground('logic_supply.c_output_fast',2,[10.58,41.6],.25)
link('logic_supply.c_output_fast',1,'logic_supply.c_output2',1,[[11.42,40.2],[11.0,39.78],[11.0,39.4],[10.6,39.0]],.2)
# Enable escapes the 0.5 mm pin corridor through a 0.5/0.25 mm via. This remains
# subject to final fabrication capability review; do not assume filled via-in-pad.
en=pad('logic_supply.ic',5).GetNetCode()
trace(en,[uv(pad('logic_supply.ic',5)),[13.25,42.66]],.2);via(en,[13.25,42.66],.5,.25)
trace(en,[uv(pad('logic_supply.r_enable',2)),[18.15,46.3]],.2);via(en,[18.15,46.3])
trace(en,[[13.25,42.66],[15.6,45.01],[15.6,46.3],[18.15,46.3]],.2,pcbnew.B_Cu)
link('logic_supply.r_enable',1,'logic_supply.c_input',1,[[16.57,44.86]],.25)
link('logic_supply.ic',1,'logic_supply.r_pg',2,[[10.9,43.16],[10.9,44.8]],.2)
# Two motor output trunks; fine lead necks and short via bank are explicit.
ma=pad('motor.ic',8).GetNetCode();mb=pad('motor.ic',10).GetNetCode()
assert ma==pad('motor_output.landing1',1).GetNetCode()
assert mb==pad('motor_output.landing2',1).GetNetCode()
trace(ma,[uv(pad('motor.ic',8)),[46.9,31.2]],.35)
trace(ma,[[46.9,31.2],[46.9,31.6],[44.2,34.3],uv(pad('motor_output.landing1',1))],1.2)
trace(mb,[uv(pad('motor.ic',10)),[39.95,29.625],[39.95,31.625]],.35)
for v in (29.625,30.625,31.625):via(mb,[39.95,v],.5,.25)
trace(mb,[[39.95,29.625],[39.95,31.6]],.8,pcbnew.B_Cu)
trace(mb,[[39.95,31.6],[46.8,31.6],[48,32.8],uv(pad('motor_output.landing2',1))],1.2,pcbnew.B_Cu)
# Protected-pack VM local reservoir, not a connection through charger SYS.
hv=pad('motor.ic',11).GetNetCode();assert hv==pad('motor.c_bulk',1).GetNetCode()
for at in ([37.7,29.87],[38.9,30.2]):
 via(hv,at);trace(hv,[uv(pad('motor.c_pump',2)),at],.3)
for x in (40.5,41.3,42.1):
 at=[x,20.8];trace(hv,[uv(pad('motor.c_bulk',1)),at],.8);via(hv,at)
trace(hv,[[38.9,30.2],[38.5,30.2],[38.5,29.87],[37.7,29.87]],.6,pcbnew.B_Cu)
trace(hv,[[38.5,30.2],[38.5,22.05],[39.75,20.8],[42.1,20.8]],1.2,pcbnew.B_Cu)
for x in (45.9,46.7,47.5):ground('motor.c_bulk',2,[x,20.8],.8)
b.BuildConnectivity();pcbnew.ZONE_FILLER(b).Fill(b.Zones());pcbnew.SaveBoard(str(out),b)
assert board_graph(out)==board_graph(src)
out.with_suffix('.kicad_pro').write_bytes(src.with_suffix('.kicad_pro').read_bytes())
print('Segments',sum(type(t).__name__=='PCB_TRACK' for t in b.GetTracks()),'vias',sum(type(t).__name__=='PCB_VIA' for t in b.GetTracks()))
