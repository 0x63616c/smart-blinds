"""Small integrity controls; no CAD export or geometry replay."""
from pathlib import Path
import sys,tempfile,json,hashlib
R=Path(__file__).resolve().parent.parent;sys.path.insert(0,str(R));import verify
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest();results=[]
with tempfile.TemporaryDirectory()as d:
 h=Path(d);(h/'evidence').mkdir();(h/'exports').mkdir();source=h/'source.txt';source.write_text('fixed source');out=h/'exports/part.stl';out.write_text('new exact output')
 def manifest(name,value):
  (h/'evidence'/name).write_text(json.dumps({'inputs':{'source.txt':sha(source)},'outputs':[{'part':'part','file':'exports/part.stl','sha256':hashlib.sha256(value.encode()).hexdigest()}]}))
 manifest('export-20260101T000000.json','old output');manifest('export-20260101T000001.json','new exact output');ex,sup=verify.select_current_exports(h);assert len(ex)==1 and len(sup)==1;results.append('latest_valid_selected_over_superseded_row')
 out.write_text('old output')
 try:verify.select_current_exports(h)
 except AssertionError:results.append('old_output_cannot_hide_latest_mismatch')
 else:raise AssertionError('stale rollback accepted')
 out.unlink()
 try:verify.select_current_exports(h)
 except AssertionError:results.append('missing_latest_output_rejected')
 else:raise AssertionError('missing output accepted')
 source.write_text('changed source');ex,sup=verify.select_current_exports(h);assert not ex;results.append('changed_source_has_no_current_export')
actual,sup=verify.select_current_exports(R);assert len(actual)==30;results.append('all30_current_real_export_roles_bound')
out={'inputs':{'verify.py':sha(R/'verify.py'),'review/manifest_selection_test.py':sha(Path(__file__))},'passed':True,'controls':results,'current_roles':len(actual),'superseded_same_source_rows':sup};(R/'review/manifest-selection-controls.json').write_text(json.dumps(out,indent=2)+'\n');print(results)
