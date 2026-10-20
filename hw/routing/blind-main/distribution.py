"""Manual charger input and bulk-reservoir distribution, with explicit fanouts."""
from pathlib import Path
import json,sys,importlib.util
import wx,pcbnew
sys.path.insert(0,'tools')
from generate_schematics import board_graph
app=wx.App(False);quiet=wx.LogNull()
HERE=Path(__file__).resolve().parent
folder=Path('work/main-route-build');src=folder/'usb-control-route.kicad_pcb';out=folder/'charger-distribution.kicad_pcb'
b=pcbnew.LoadBoard(str(src));parts={f.GetFieldText('atopile_address'):f for f in b.GetFootprints()}
def pad(a,n):return next(p for p in parts[a].Pads() if p.GetNumber()==str(n))
def uv(p):return [pcbnew.ToMM(p.GetPosition().x)-100,175-pcbnew.ToMM(p.GetPosition().y)]
def point(p):return p if isinstance(p,pcbnew.VECTOR2I) else pcbnew.VECTOR2I(pcbnew.FromMM(100+p[0]),pcbnew.FromMM(175-p[1]))
def trace(net,points,width=.3,layer=pcbnew.F_Cu):
    for a,c in zip(points,points[1:]):
        a,c=point(a),point(c)
        if a==c:continue
        t=pcbnew.PCB_TRACK(b);t.SetStart(point(a));t.SetEnd(point(c));t.SetWidth(pcbnew.FromMM(width));t.SetLayer(layer);t.SetNetCode(net);b.Add(t)
def via(net,p,diam=.6,drill=.3):
    assert not any(isinstance(t,pcbnew.PCB_VIA) and t.GetPosition()==point(p) for t in b.GetTracks()),p
    v=pcbnew.PCB_VIA(b);v.SetPosition(point(p));v.SetWidth(pcbnew.FromMM(diam));v.SetDrill(pcbnew.FromMM(drill));v.SetViaType(pcbnew.VIATYPE_THROUGH);v.SetLayerPair(pcbnew.F_Cu,pcbnew.B_Cu);v.SetNetCode(net);b.Add(v)
def bank(a,n,points,width=.6):
    p=pad(a,n);net=p.GetNetCode()
    for at in points:trace(net,[p.GetPosition(),at],width);via(net,at)
    return net
inp=bank('charger.c_input1',1,[[21.1,20.35],[21.9,20.35]])
trace(inp,[[26.05,13.8],[26.05,18.5],[23.8,20.75],[22.3,20.75],[21.9,20.35],[21.1,20.35]],.8,pcbnew.In2_Cu)
for record in json.loads((HERE/'charger-power-banks.json').read_text()):
    bank(record['address'],record['pin'],record['uv'],.3 if record['address']=='charger.c_input_fast' else .6)
def net(a,n=1):return pad(a,n).GetNetCode()
def trunk(n,path,w=.8):trace(n,path,w,pcbnew.In2_Cu)
inp=net('charger.c_input_fast')
trunk(inp,[[21.9,20.35],[23.1,21.55],[23.1,22.6],[26.7,25.48],[26.7,26.48]])
trunk(inp,[[26.7,26.48],[25.5,26.48]],.6)
pm=net('charger.c_pmid1')
trunk(pm,[[25.79,29.5],[28.09,29.5],[27.9,29.31],[27.9,21.44],[27.45,20.99],[26.15,19.89]])
trunk(pm,[[27.21,19.7],[27.45,20.99],[28.7,20.99],[29.41,20.28],[29.41,19.7]],.7)
trunk(pm,[[29.41,19.7],[29.41,18.7],[31.67,16.44],[32.2,16.44],[32.2,18.04],[32.8,18.64]])
sy=net('charger.c_sys1')
trunk(sy,[[31.91,29.5],[34.21,29.5],[35.05,30.34],[35.05,30.56],[35.45,30.96],[35.45,32.76]])
trunk(sy,[[35.05,30.56],[35.25,30.36],[35.25,25.55],[36.2,24.6],[36.2,20.19],[35.8,19.79],[34.5,18.69]])
trunk(sy,[[35.56,14.8],[37.76,14.8]])
trunk(sy,[[35.56,14.8],[35.56,16.5],[35.8,16.74],[35.8,19.79]])
trunk(sy,[[35.8,17.8],[48.91,17.8],[49.85,16.86],[49.85,19.06]])
b.BuildConnectivity();pcbnew.ZONE_FILLER(b).Fill(b.Zones());pcbnew.SaveBoard(str(out),b)
out.with_suffix('.kicad_pro').write_bytes(src.with_suffix('.kicad_pro').read_bytes())
assert board_graph(out)==board_graph(src)
print('Segments',sum(not isinstance(t,pcbnew.PCB_VIA) for t in b.GetTracks()),'Vias',sum(isinstance(t,pcbnew.PCB_VIA) for t in b.GetTracks()))
