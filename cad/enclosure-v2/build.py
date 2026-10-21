"""Standalone sequential CAD exporter; no native KiCad and no work-chain imports."""
from pathlib import Path
import argparse,hashlib,json,os,shutil,subprocess,time,sys
H=Path(__file__).resolve().parent
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
def snapshot():
 return {str(p.relative_to(H)):sha(p)for folder in ['source','parameters','assets','data']for p in sorted((H/folder).rglob('*'))if p.is_file()}|{'build.py':sha(Path(__file__)),'prepare.py':sha(H/'prepare.py')}
def main():
 a=argparse.ArgumentParser();a.add_argument('--parts',nargs='+',choices=['cover', 'backplate', 'guide_bar', 'button', 'nest', 'motor_frame', 'backing', 'guard_clamp', 'tail_keeper', 'inline_body', 'housing_tie', 'front', 'rear', 'spacer', 'upper_clip', 'lower_clip', 'rear_lower', 'rear_upper', 'front_lower', 'front_upper', 'bearing_block', 'retainer', 'wheel', 'guard', 'cosmetic_plug', 'ring', 'drive', 'contents', 'pack_fasteners'],default=['cover', 'backplate', 'guide_bar', 'button', 'nest', 'motor_frame', 'backing', 'guard_clamp', 'tail_keeper', 'inline_body', 'housing_tie', 'front', 'rear', 'spacer', 'upper_clip', 'lower_clip', 'rear_lower', 'rear_upper', 'front_lower', 'front_upper', 'bearing_block', 'retainer', 'wheel', 'guard', 'cosmetic_plug', 'ring', 'drive', 'contents', 'pack_fasteners']);a.add_argument('--openscad',default=os.environ.get('OPENSCAD')or shutil.which('openscad')or'/opt/homebrew/bin/openscad');args=a.parse_args()
 subprocess.run([sys.executable,str(H/'prepare.py'),'--check'],check=True)
 inputs=snapshot();outdir=H/'exports';outdir.mkdir(exist_ok=True);rows=[]
 for n in args.parts:
  out=outdir/(n+'.stl');cmd=[args.openscad,'--export-format=binstl','-o',str(out),'-D','part='+json.dumps(n),str(H/'source/prints_v2.scad')];start=time.monotonic();r=subprocess.run(cmd,capture_output=True,text=True);log=r.stdout+r.stderr;(outdir/(n+'.log')).write_text(log)
  assert r.returncode==0 and 'WARNING:'not in log and'ERROR:'not in log,(n,log)
  assert snapshot()==inputs,'Inputs changed during export'
  rows.append({'part':n,'file':str(out.relative_to(H)),'sha256':sha(out),'bytes':out.stat().st_size,'seconds':time.monotonic()-start,'command':cmd});print(n,round(rows[-1]['seconds'],2),flush=True)
 stamp=time.strftime('%Y%m%dT%H%M%S');report={'status':'Fresh exports only; geometry/check qualification separate','inputs':inputs,'outputs':rows}
 (H/'evidence'/('export-'+stamp+'.json')).write_text(json.dumps(report,indent=2)+'\n')
if __name__=='__main__':main()
