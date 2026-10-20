"""Partial USB input/protection routing; not a complete negotiated power path."""
from pathlib import Path
import sys,json,importlib.util
import wx,pcbnew
sys.path.insert(0,'tools');from generate_schematics import board_graph
app=wx.App(False);quiet=wx.LogNull();folder=Path('work/main-route-build');src=folder/'module-power-route.kicad_pcb';out=folder/'usb-power-route.kicad_pcb';b=pcbnew.LoadBoard(str(src))
parts={f.GetFieldText('atopile_address'):f for f in b.GetFootprints()}
def pad(a,n):return next(p for p in parts[a].Pads() if p.GetNumber()==str(n))
def uv(p):return [pcbnew.ToMM(p.GetPosition().x)-100,175-pcbnew.ToMM(p.GetPosition().y)]
def pos(xy):return pcbnew.VECTOR2I(pcbnew.FromMM(100+xy[0]),pcbnew.FromMM(175-xy[1]))
def trace(net,pts,w=.2,layer=pcbnew.F_Cu):
 for a,c in zip(pts,pts[1:]):
  if a==c:continue
  t=pcbnew.PCB_TRACK(b);t.SetStart(pos(a));t.SetEnd(pos(c));t.SetWidth(pcbnew.FromMM(w));t.SetLayer(layer);t.SetNetCode(net);b.Add(t)
def via(net,p,diam=.6,drill=.3):
 v=pcbnew.PCB_VIA(b);v.SetPosition(pos(p));v.SetWidth(pcbnew.FromMM(diam));v.SetDrill(pcbnew.FromMM(drill));v.SetViaType(pcbnew.VIATYPE_THROUGH);v.SetLayerPair(pcbnew.F_Cu,pcbnew.B_Cu);v.SetNetCode(net);b.Add(v)
def link(a,n,c,m,pts=(),w=.2,layer=pcbnew.F_Cu):
 p,q=pad(a,n),pad(c,m);assert p.GetNetCode()==q.GetNetCode(),(a,n,c,m)
 trace(p.GetNetCode(),[uv(p),*pts,uv(q)],w,layer)
gn=pad('usb.pd',22).GetNetCode()
def ground(a,n,at):
 p=pad(a,n);assert p.GetNetCode()==gn
 trace(gn,[uv(p),at],.25);via(gn,at)
# Three independent PD bypass branches; do not tie the two regulator outputs.
link('usb.pd',24,'usb.c_vdd',1,[(37.4,8.25),(36.75,7.6)])
link('usb.pd',23,'usb.c_2v7',1,[(37.45,8.75),(36.9,9.3)])
link('usb.pd',21,'usb.c_1v2',1,[(37.45,9.75)])
for a,v in [('usb.c_vdd',8.4),('usb.c_2v7',10.1),('usb.c_1v2',11.8)]:ground(a,2,(34.6,v))
link('usb.pd',22,'usb.pd',25,[(38.7,9.25),(39,9.5)])
link('usb.pd',25,'usb.pd',10,[(41.3,9.75)])
trace(gn,[uv(pad('usb.pd',10)),(42.65,9.75)],.2);via(gn,(42.65,9.75),.5,.25)
# Matched small series resistor placement immediately at the MCU's USB pins.
link('controller.mcu',14,'controller.r_dp',1)
link('controller.mcu',13,'controller.r_dm',1)
# eFuse timing/current setting and an explicit same-face quiet ground star.
link('usb.efuse',7,'usb.c_slew',1,[(26.4,8.1),(26.4,7.5),(26.9,7)])
link('usb.efuse',9,'usb.r_limit',1)
trace(gn,[uv(pad('usb.efuse',8)),(26.7,8.77),(28.4,8.77)],.2)
trace(gn,[uv(pad('usb.c_slew',2)),(28.4,7.6),(28.4,8.77)],.2)
trace(gn,[uv(pad('usb.r_limit',2)),(28.4,9.2),(28.4,8.77)],.2)
trace(gn,[uv(pad('usb.r_ov_bottom',2)),(21.3,14.4),(21.3,12.8),uv(pad('usb.r_uv_bottom',2))],.2)
trace(gn,[(21.3,12.8),(21.3,11.8),(24,11.8),(24,11.3),(26.8,11.3),(27.5,10.6),(27.5,9.95),(28.4,9.95),(28.4,8.77)],.2)
via(gn,(28.4,8.77),.5,.25)
# Divider sense traces cross the local return on the opposite side; the
# complete divider chains and source transient qualification remain pending.
for a,pin,start,end in [('usb.r_uv_bottom',1,(23.4,10.2),(23.03,13.5)),('usb.r_ov_bottom',2,(23.4,9.23),(23.6,14.4))]:
 p=pad('usb.efuse',pin);q=pad(a,1);assert p.GetNetCode()==q.GetNetCode();net=p.GetNetCode()
 trace(net,[uv(p),start],.15);via(net,start,.5,.25)
 trace(net,[uv(q),end],.15);via(net,end,.5,.25)
 trace(net,[start,*([(22.45,10.18),(22.45,14.4)] if pin==2 else [(start[0],end[1])]),end],.2,pcbnew.B_Cu)
# eFuse input/output power branches, retaining the centre pad escape widths.
raw=pad('usb.efuse',5).GetNetCode();power=pad('usb.efuse',6).GetNetCode()
trace(raw,[uv(pad('usb.efuse',5)),(24.77,7.3),(24.2,6.7)],.3)
trace(raw,[uv(pad('usb.c_raw',1)),(22.81,6.7),(24.2,6.7)],.6)
for at in [(23.6,6.7),(24.2,6.7)]:via(raw,at)
trace(raw,[uv(pad('usb.tvs_vbus',1)),(21.2,5.7),(21.2,6.51),uv(pad('usb.c_raw',1))],.6)
ground('usb.tvs_vbus',2,(23.4,5.3));ground('usb.c_raw',2,(21.2,10.6))
for n,at in [('A4B9',(27.1,5.3)),('B4A9',(31.9,5.3))]:
 trace(raw,[uv(pad('usb.connector',n)),at],.5);via(raw,at)
trace(raw,[(27.1,5.3),(27.8,4.6),(27.8,2.0),(31.2,2.0),(31.2,4.6),(31.9,5.3)],.8,pcbnew.B_Cu)
trace(raw,[(27.1,5.3),(26.6,5.8),(24.8,5.8),(24.2,6.4),(24.2,6.7),(23.6,6.7)],.8,pcbnew.B_Cu)
for n,shell,mid in [('A1B12','4',[(25.9,4.7),(25.175,4.7)]),('B1A12','1',[(33.1,4.7),(33.825,4.7)])]:link('usb.connector',n,'usb.connector',shell,mid,.35)
trace(power,[uv(pad('usb.efuse',6)),(25.26,7.3),(25.7,6.8)],.3)
trace(power,[uv(pad('usb.efuse',6)),(25.26,10.7)],.3)
trace(power,[(25.26,10.7),(25.9,10.7)],.6)
for at in [(25.7,6.8),(25.26,10.7),(25.9,10.7),(26.05,13.8)]:via(power,at)
trace(power,[(25.7,6.8),(26.2,7.2),(26.2,10.7),(25.26,10.7)],.8,pcbnew.B_Cu)
trace(power,[(26.2,10.7),(26.2,12.7),(26.05,13.8)],.8,pcbnew.B_Cu)
trace(power,[(26.05,13.8),uv(pad('charger.c_input2',1))],.8)
ground('charger.c_input2',2,(24.3,15.3))
# USB-fed VDD diode beside the PD bypass capacitor.
link('usb.d_vdd',1,'usb.c_vdd',1,[(37.2,5.85),(37.2,6.6)])
trace(raw,[uv(pad('usb.d_vdd',2)),(35.55,3.9)],.2);via(raw,(35.55,3.9),.5,.25)
trace(raw,[(31.2,2),(35.55,2),(35.55,3.9)],.25,pcbnew.B_Cu)
# CC sensing through the local protector, including both dead-battery pins.
link('usb.connector','A5','usb.tvs_cc',1,[(28.25,5.4),(29.54,6.69)])
link('usb.connector','B5','usb.tvs_cc',2,[(31.25,5.2),(30.5,5.95),(30.5,8.4)])
cc1=pad('usb.pd',1).GetNetCode();cc2=pad('usb.pd',4).GetNetCode()
link('usb.pd',1,'usb.pd',2,[(38.75,7),(39.25,7)],.15)
link('usb.pd',4,'usb.pd',5,[(40.25,7),(40.75,7)],.15)
for a,n,at in [('usb.tvs_cc',1,(29.54,8)),('usb.pd',2,(39.25,6.8)),('usb.tvs_cc',2,(31,8.1)),('usb.pd',5,(40.75,6.6))]:
 p=pad(a,n);trace(p.GetNetCode(),[uv(p),at],.15);via(p.GetNetCode(),at,.5,.25)
trace(cc1,[(29.54,8),(30.64,6.9),(36.8,6.9),(38.2,6.14),(39.25,6.8)],.2,pcbnew.B_Cu)
trace(cc2,[(31,8.1),(32.15,9.25),(37.8,9.25),(40.75,6.6)],.2,pcbnew.B_Cu)
ground('usb.tvs_cc',3,(30.2,11.3))
# Separate short ESD returns; data pair beyond the pads is still pending.
link('controller.usb_esd',1,'controller.usb_esd',2)
ground('controller.usb_esd',1,(31.9,7.7));ground('controller.usb_esd',4,(32.8,5.6))
b.BuildConnectivity();pcbnew.ZONE_FILLER(b).Fill(b.Zones());pcbnew.SaveBoard(str(out),b)
out.with_suffix('.kicad_pro').write_bytes(src.with_suffix('.kicad_pro').read_bytes())
assert board_graph(src)==board_graph(out)
print('USB partial routes:',sum(not isinstance(t,pcbnew.PCB_VIA) for t in b.GetTracks()),'segments,',sum(isinstance(t,pcbnew.PCB_VIA) for t in b.GetTracks()),'vias')
