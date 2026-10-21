from pathlib import Path
import hashlib,json,os,shutil,subprocess,time
H=Path(__file__).resolve().parent;R=H.parent
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
def snap():return {str(p.relative_to(R)):sha(p)for p in [H/'relief_views.scad',Path(__file__),R/'source/definitions.scad',R/'parameters/enclosure-v2.json',*[R/'exports'/(n+'.stl')for n in ['front','rear','spacer','contents','motor_frame']]]}
inputs=snap();rows=[];openscad=os.environ.get('OPENSCAD')or shutil.which('openscad')or'/opt/homebrew/bin/openscad'
for name,cam in [('link','43,112,39,55,0,35,44'),('motor','94,68,66,55,0,35,35'),('upper_capture','92,103,34,55,0,35,45'),('lower_capture','92,10,38,55,0,35,30')]:
 out=R/'renders'/('relief-'+name+'.png');cmd=[openscad,'--preview','--imgsize=1200,1000','--projection=o','--colorscheme=Tomorrow','--camera='+cam,'-o',str(out),'-D','part='+json.dumps(name),str(H/'relief_views.scad')];start=time.monotonic();r=subprocess.run(cmd,capture_output=True,text=True);(out.with_suffix('.log')).write_text(r.stdout+r.stderr);assert r.returncode==0 and'WARNING:'not in r.stderr and'ERROR:'not in r.stderr;assert snap()==inputs;rows.append({'file':str(out.relative_to(R)),'sha256':sha(out),'seconds':time.monotonic()-start,'command':cmd});print(name,flush=True)
(H/'render-report.json').write_text(json.dumps({'inputs':inputs,'outputs':rows,'status':'OpenCSG source-export cutaway previews, not CGAL or physical-fit acceptance; colours distinguish parts. Initial CGAL failure retained.'},indent=2)+'\n')
