"""Fresh sequential checks on this package's current exports and actual03a6 board."""
from pathlib import Path
import argparse,hashlib,json,os,subprocess,sys,time,platform,importlib.metadata
H=Path(__file__).resolve().parent
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
JOBS=['broadphase_controls','pad_contact','solid_checks','clamp_sweep','assembly_motion','current_tail_clearance','current_board_screen','access_screen','extraction','complete_extraction','drive_clearance','fastener_headroom','service_screen','parking_screen','button_integration','cosmetic_plug','cassette_reliefs']
REPORTS=['broadphase-controls.json','pad-contact.json','solid-report.json','clamp-sweep-report.json','assembly-motion-report.json','current-tail-report.json','current-board-report.json','access-report.json','extraction-report.json','complete-extraction-report.json','drive-clearance-report.json','fastener-headroom-report.json','service-check.json','parking-report.json','integration-report.json','cosmetic-report.json','cassette-reliefs-report.json']
def snapshot():
 folders=['source','parameters','assets','data','geometry']
 result={str(p.relative_to(H)):sha(p)for folder in folders for p in sorted((H/folder).rglob('*'))if p.is_file()and '__pycache__'not in str(p)}
 for p in list((H/'verification').glob('*.py'))+[H/'build.py',H/'build_auxiliary.py',H/'prepare.py',Path(__file__)]:result[str(p.relative_to(H))]=sha(p)
 return result

def select_current_exports(root):
 exports={};superseded=[]
 for p in sorted((root/'evidence').glob('export-*.json')):
  d=json.loads(p.read_text())
  if all((root/k).is_file()and sha(root/k)==v for k,v in d['inputs'].items()):
   for row in d['outputs']:
    key=row['part']
    if key in exports:superseded.append({'part':key,'manifest':exports[key]['manifest'],'sha256':exports[key]['sha256']})
    exports[key]=dict(row,manifest=str(p.relative_to(root)))
 for key,row in exports.items():
  assert (root/row['file']).is_file()and sha(root/row['file'])==row['sha256'],('Latest export changed or missing',key,row['manifest'])
 return exports,superseded

def main():
 a=argparse.ArgumentParser();a.add_argument('--checks',nargs='+',choices=JOBS,default=JOBS);args=a.parse_args()
 subprocess.run([sys.executable,str(H/'prepare.py'),'--check'],check=True)
 import manifold3d
 runtime={'python':sys.version,'platform':platform.platform(),'numpy':importlib.metadata.version('numpy'),'manifold3d':importlib.metadata.version('manifold3d'),'manifold_binary_sha256':sha(Path(manifold3d.__file__))};assert runtime['manifold3d']=='3.3.2'
 inputs=snapshot();exports,superseded=select_current_exports(H)
 needed={'cover','backplate','motor_frame','front','rear','spacer','guard_clamp','backing','tail_keeper','inline_body','housing_tie','contents','pack_fasteners','drive','guide_bar','button','nest','cosmetic_plug','ring','service_hardware'}
 assert needed<=exports.keys(),('Missing fresh source-bound exports',sorted(needed-exports.keys()))
 current={'inputs':inputs,'outputs':list(exports.values()),'superseded_same_source_rows':superseded};(H/'evidence/current-exports.json').write_text(json.dumps(current,indent=2)+'\n')
 result={'status':'Running fresh package checks; no physical qualification','inputs':inputs,'runtime':runtime,'jobs':[]}
 for name in args.checks:
  start=time.monotonic();log=H/'verification'/(name+'.log')
  with log.open('w')as f:r=subprocess.run([sys.executable,str(H/'verification'/(name+'.py'))],stdout=f,stderr=subprocess.STDOUT)
  assert snapshot()==inputs,'Source changed during verification'
  row={'name':name,'exit_code':r.returncode,'seconds':time.monotonic()-start,'log_sha256':sha(log)}
  report=H/'verification'/REPORTS[JOBS.index(name)]
  if r.returncode==0:
   d=json.loads(report.read_text());row.update(report=str(report.relative_to(H)),report_sha256=sha(report),passed=bool(d.get('passed',False)))
  else:row['passed']=False
  result['jobs'].append(row);result['passed']=all(x['passed']for x in result['jobs']);(H/'evidence/verification-run.json').write_text(json.dumps(result,indent=2)+'\n');print(name,row['passed'],round(row['seconds'],2),flush=True)
  if not row['passed']:raise SystemExit(1)
 result['status']='Fresh package checks completed; nominal geometry only';result['complete']=args.checks==JOBS;(H/'evidence/verification-run.json').write_text(json.dumps(result,indent=2)+'\n')
if __name__=='__main__':main()
