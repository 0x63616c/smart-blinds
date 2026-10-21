#!/usr/bin/env python3
"""Explicit, single-attempt build with a package-download budget; never runs host KiCad."""
from pathlib import Path
import datetime,hashlib,json,re,shutil,subprocess,sys
ROOT=Path(__file__).resolve().parents[2];HERE=Path(__file__).resolve().parent
OUT=ROOT/'work/kicad-linux-runner';OUT.mkdir(parents=True,exist_ok=True)
VERSION='10.0.7~ubuntu24.04.1';TAG='smart-blinds-kicad:10.0.7-arm64';META='smart-blinds-kicad:metadata'
DOCKER=shutil.which('docker')
if not DOCKER:raise SystemExit('Docker is required. Native KiCad fallback is disabled.')
def run(args,log):
 path=OUT/log
 with path.open('wb')as f:r=subprocess.run([DOCKER,*args],cwd=ROOT,stdout=f,stderr=subprocess.STDOUT,timeout=900)
 print(f'{path}: exit {r.returncode}',flush=True)
 if r.returncode:raise SystemExit(r.returncode)
 return path.read_text()
if shutil.disk_usage(ROOT).free<3*1024**3:raise SystemExit('At least 3 GiB free is required before this bounded build.')
run(['build','--platform','linux/arm64','--target','metadata','--progress','plain','-t',META,str(HERE)],'metadata-build.log')
plan=run(['run','--rm','--network','none',META,'apt-get','--print-uris','--yes','--no-install-recommends','install','kicad='+VERSION,'xvfb','xauth','python3-wxgtk4.0','python3-shapely','python3-yaml'],'install-plan.txt')
bytes_=sum(int(x)for x in re.findall(r"^'[^']+'\s+\S+\s+(\d+)\s",plan,re.M))
if not bytes_:raise SystemExit('No download size found; inspect the plan manually before building.')
size={'kicad_version':VERSION,'download_bytes':bytes_,'install_summary':[s for s in plan.splitlines()if 'disk space'in s or 'archives'in s],'download_budget_bytes':2000000000}
(OUT/'size-plan.json').write_text(json.dumps(size,indent=2)+'\n');print(json.dumps(size,indent=2),flush=True)
if bytes_>2000000000:raise SystemExit('Download exceeds 2 GB: stop and review disk/download requirements; no install attempted.')
run(['build','--platform','linux/arm64','--target','runtime','--build-arg','KICAD_VERSION='+VERSION,'--progress','plain','-t',TAG,str(HERE)],'runtime-build.log')
info=json.loads(subprocess.check_output([DOCKER,'image','inspect',TAG],timeout=30))[0]
assert info['Os']=='linux'and info['Architecture']=='arm64'
lock={'schema':1,'image_id':info['Id'],'tag_for_humans':TAG,'architecture':'arm64','kicad_package_version':VERSION,'ubuntu_manifest':'sha256:18b33ff3829707f31ada654a963b9ee35f2e6f0241b964bd17a22a9b330cb63d','ppa':'https://ppa.launchpadcontent.net/kicad/kicad-10.0-releases/ubuntu','ppa_key_fingerprint':'FDA854F61C4D0D9572BB95E5245D5502FAD7A805','image_size_bytes':info['Size'],'built_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'recipe_sha256':{f.name:hashlib.sha256(f.read_bytes()).hexdigest()for f in [HERE/'Dockerfile',HERE/'entrypoint.sh',HERE/'kicad-ppa.asc']}}
(HERE/'image.lock.json').write_text(json.dumps(lock,indent=2)+'\n');print(json.dumps(lock,indent=2))
