"""One safe Linux load/iterate/save-copy/reload smoke; no native object deletion."""
from pathlib import Path
import hashlib,json,platform,re,shutil,sys
assert platform.system()=='Linux','Run through tools/kicad-run, never host pcbnew'
import wx
app=wx.App(False)
import pcbnew
ROOT=Path('/work');sys.path.insert(0,str(ROOT/'tools'))
from generate_schematics import board_graph
source=ROOT/'hw/routing/blind-main/main-routed.kicad_pcb'
out=ROOT/'work/kicad-linux-runner/smoke';out.mkdir(parents=True,exist_ok=True)
hashfile=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
source_sha=hashfile(source);before_graph=board_graph(source)
b=pcbnew.LoadBoard(str(source));assert b is not None
# Snapshot lists while the owning board remains alive. No Remove calls or unsafe deletion loops.
footprints=list(b.GetFootprints());tracks=list(b.GetTracks());zones=list(b.Zones());drawings=list(b.GetDrawings())
counts={'footprints':len(footprints),'tracks':sum(not isinstance(t,pcbnew.PCB_VIA)for t in tracks),'vias':sum(isinstance(t,pcbnew.PCB_VIA)for t in tracks),'zones':len(zones),'drawings':len(drawings),'pads':sum(len(list(f.Pads()))for f in footprints)}
for f in footprints:
 assert f.GetReference()
 for pad in list(f.Pads()):pad.GetPosition();pad.GetNetname()
for t in tracks:t.GetStart();t.GetEnd();t.GetNetname()
for z in zones:z.GetLayer();z.GetIsRuleArea();z.GetZoneName()
copy=out/'main-copy.kicad_pcb';pcbnew.SaveBoard(str(copy),b)
again=pcbnew.LoadBoard(str(copy));assert again is not None
assert len(list(again.GetFootprints()))==counts['footprints']
assert len(list(again.GetTracks()))==len(tracks)
assert board_graph(copy)==before_graph,'electrical graph/metadata changed on save-copy'
assert hashfile(source)==source_sha,'canonical source changed'
for suffix in ['.kicad_pro','.kicad_dru']:
 p=source.with_suffix(suffix)
 if p.exists():shutil.copyfile(p,copy.with_suffix(suffix))
lib=source.parent/'fp-lib-table'
if lib.exists():
 text=re.sub(r'\$\{KIPRJMOD\}/([^"\n]+)',lambda m:str((source.parent/m.group(1)).resolve()),lib.read_text())
 (out/'fp-lib-table').write_text(text)
result={'status':'PASS load/iteration/save-copy/reload; DRC separate','platform':platform.platform(),'python':sys.version,'pcbnew_version':pcbnew.GetBuildVersion(),'source':str(source.relative_to(ROOT)),'source_sha256':source_sha,'source_unchanged':hashfile(source)==source_sha,'copy_sha256':hashfile(copy),'graph_equal':True,'counts':counts,'no_object_deletion':True}
(out/'load-save.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
