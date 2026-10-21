"""One maintained, sequential package entry point; no historical work imports."""
from pathlib import Path
import argparse,subprocess,sys
H=Path(__file__).resolve().parent
STAGES={'parameters':[('prepare.py','--check')],'export':[('build.py',),('build_auxiliary.py',)],'check':[('verify.py',)],'inventory':[('inventory.py',)],'render':[('review/render_reliefs.py',)],'freeze':[('freeze.py',)]}
p=argparse.ArgumentParser();p.add_argument('--stages',nargs='+',choices=list(STAGES),default=[s for s in STAGES if s!='freeze']);a=p.parse_args()
for stage in a.stages:
 for script,*args in STAGES[stage]:subprocess.run([sys.executable,str(H/script),*args],check=True)
