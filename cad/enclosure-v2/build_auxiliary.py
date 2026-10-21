"""Export explicit service hardware independently of unchanged print meshes."""
from pathlib import Path
import hashlib,json,os,shutil,subprocess,time
H=Path(__file__).resolve().parent;sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
def snapshot():
 return {str(p.relative_to(H)):sha(p)for folder in ['source','parameters','assets','data']for p in sorted((H/folder).rglob('*'))if p.is_file()}|{'build_auxiliary.py':sha(Path(__file__))}
inputs=snapshot();out=H/'exports/service_hardware.stl';cmd=[os.environ.get('OPENSCAD')or shutil.which('openscad')or'/opt/homebrew/bin/openscad','--export-format=binstl','-o',str(out),str(H/'source/service_hardware_v2.scad')];start=time.monotonic();r=subprocess.run(cmd,capture_output=True,text=True);log=r.stdout+r.stderr;(H/'exports/service_hardware.log').write_text(log);assert r.returncode==0 and 'WARNING:'not in log and 'ERROR:'not in log,log;assert snapshot()==inputs
row={'part':'service_hardware','file':str(out.relative_to(H)),'sha256':sha(out),'bytes':out.stat().st_size,'seconds':time.monotonic()-start,'command':cmd};stamp=time.strftime('%Y%m%dT%H%M%S');(H/'evidence'/('export-'+stamp+'.json')).write_text(json.dumps({'status':'Fresh auxiliary operand; geometry checks separate','inputs':inputs,'outputs':[row]},indent=2)+'\n');print('service_hardware',round(row['seconds'],2))
