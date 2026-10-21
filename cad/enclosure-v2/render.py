"""Source-bound review images; sequential, no native KiCad, no generated artwork."""
from pathlib import Path
import argparse,hashlib,json,os,shutil,subprocess,time
H=Path(__file__).resolve().parent
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
def snapshot():
 return {str(p.relative_to(H)):sha(p)for folder in ['source','parameters','assets','data']for p in sorted((H/folder).rglob('*'))if p.is_file()}|{'render.py':sha(Path(__file__))}
def main():
 parser=argparse.ArgumentParser();parser.add_argument('--openscad',default=os.environ.get('OPENSCAD')or shutil.which('openscad')or'/opt/homebrew/bin/openscad');args=parser.parse_args();inputs=snapshot();rows=[]
 target=H/'renders';target.mkdir(exist_ok=True)
 views=[('closed','closed','59,85,36,22,0,26,630',False),('assembly','assembly','59,85,36,22,0,26,630',False),('service','service','59,90,70,45,0,25,790',False),('buttons','buttons','108,32,74,12,0,12,120',False),('buttons-optional-plugs','buttons','108,32,74,12,0,12,120',True)]
 for name,part,cam,plugs in views:
  out=target/(name+'.png');cmd=[args.openscad,'--preview','--imgsize=1400,1100','--projection=o','--colorscheme=Tomorrow','--camera='+cam,'-o',str(out),'-D','part='+json.dumps(part),'-D','optional_plugs='+str(plugs).lower(),str(H/'source/assembly_v2.scad')];start=time.monotonic();r=subprocess.run(cmd,capture_output=True,text=True);log=r.stdout+r.stderr;(target/(name+'.log')).write_text(log);assert r.returncode==0 and 'WARNING:'not in log and 'ERROR:'not in log,log;assert snapshot()==inputs,'Inputs changed during render';rows.append({'file':str(out.relative_to(H)),'sha256':sha(out),'seconds':time.monotonic()-start,'command':cmd});print(name,'rendered',flush=True)
 (H/'evidence/render-report.json').write_text(json.dumps({'inputs':inputs,'outputs':rows,'limits':['Source-rendered nominal enclosure study, not physical fit or photorealistic finish.','Prominent PCB parts shown as reviewed drawing allocations, not a complete native populated PCB.','White material uses neutral scene shading. Screws and chain are actual modeled objects.','Optional caps are removable cosmetic prototypes, with unqualified retention and no IP rating.']},indent=2)+'\n')
if __name__=='__main__':main()
