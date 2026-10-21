from pathlib import Path
import runpy,json,numpy as np
s=runpy.run_path(str(Path(__file__).with_name('capture_relief_trial.py')))
from geometry.operations import swept_check
rows=[]
for n,vec in [('front',[0,0,20]),('rear',[0,0,-20])]:
 q=s['f'if n=='front'else'r'];m=q.to_mesh();tri=np.array(m.vert_properties)[:,:3][np.array(m.tri_verts)]
 for on in ['spacer','contents']:
  swept_check(q,tri,vec,s['p'][on],n+'_shell_approach_'+on,rows)
(Path(__file__).with_name('shell-motion-trial.json')).write_text(json.dumps({'inputs':s['inputs'],'checks':rows,'passed':all(a['pass']for a in rows),'status':'Trial path, full source-export checking still required'},indent=2)+'\n')
