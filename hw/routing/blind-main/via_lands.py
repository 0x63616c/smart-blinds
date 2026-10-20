"""Move ordinary via drills clear of solder lands; replay finite reviewed paths."""
from pathlib import Path
import json,shutil,sys
import pcbnew,wx
app=wx.App(False);quiet=wx.LogNull();here=Path(__file__).resolve().parent
folder=Path('work/main-route-build');source=folder/'charger-controls.kicad_pcb'
sys.path.insert(0,'tools')
from generate_schematics import board_graph
b=pcbnew.LoadBoard(str(source))
def pt(xy):return pcbnew.VECTOR2I(round((100+xy[0])*1e6),round((175-xy[1])*1e6))
def close(a,c):return abs(a.x-c.x)<=2 and abs(a.y-c.y)<=2
layers={pcbnew.LayerName(l):l for l in (pcbnew.F_Cu,pcbnew.In1_Cu,pcbnew.In2_Cu,pcbnew.B_Cu)}
rows=json.loads((here/'via-land-clearance.json').read_text());assert len(rows)==12
for row in rows:
 old,new=pt(row['old']),pt(row['new'])
 vias=[t for t in b.GetTracks() if isinstance(t,pcbnew.PCB_VIA) and close(t.GetPosition(),old) and t.GetNetname()==row['net']]
 assert len(vias)==1,'Missing or ambiguous original via';v=vias[0]
 for change in row['changed_tracks']:
  a,c=map(pt,change['from']);matches=[t for t in b.GetTracks() if not isinstance(t,pcbnew.PCB_VIA) and t.GetNetCode()==v.GetNetCode() and t.GetLayer()==layers[change['layer']] and close(t.GetStart(),a) and close(t.GetEnd(),c) and t.GetWidth()==round(change['width']*1e6)]
  assert len(matches)==1,'Missing or ambiguous incident trace';t=matches[0]
  t.SetStart(pt(change['to'][0]));t.SetEnd(pt(change['to'][1]))
 v.SetPosition(new)
 for change in row['added_tracks']:
  t=pcbnew.PCB_TRACK(b);t.SetStart(pt(change['path'][0]));t.SetEnd(pt(change['path'][1]));t.SetLayer(layers[change['layer']]);t.SetWidth(round(change['width']*1e6));t.SetNetCode(v.GetNetCode());b.Add(t)
b.BuildConnectivity();pcbnew.ZONE_FILLER(b).Fill(b.Zones())
out=folder/'via-land-clearance.kicad_pcb';pcbnew.SaveBoard(str(out),b)
shutil.copyfile(source.with_suffix('.kicad_pro'),out.with_suffix('.kicad_pro'))
assert board_graph(source)==board_graph(out)
print('Moved twelve ordinary vias clear of solder lands; circuit graph preserved')
