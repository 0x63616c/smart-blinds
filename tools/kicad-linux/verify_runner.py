"""Host-standard-library failure/mount probes; never imports native KiCad."""
from pathlib import Path
import errno,hashlib,json,subprocess
ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'work/kicad-linux-runner/probes';OUT.mkdir(parents=True,exist_ok=True)
REPO=OUT/'repo';REPO.mkdir(exist_ok=True)
(REPO/'sentinel.txt').write_text('read-only fixture\n')
(REPO/'work').mkdir(exist_ok=True)
runner=ROOT/'tools/kicad-run'
rows=[]
def run(name,args,expected,record=True):
    before=set((REPO/'work/kicad-runs').glob('*/run.json'))
    r=subprocess.run([str(runner),*args],cwd=ROOT,capture_output=True,text=True,timeout=45)
    (OUT/(name+'.log')).write_text(r.stdout+r.stderr)
    assert r.returncode==expected,(name,r.returncode,r.stdout,r.stderr)
    row={'name':name,'expected_exit':expected,'actual_exit':r.returncode}
    if record:
        added=set((REPO/'work/kicad-runs').glob('*/run.json'))-before
        assert len(added)==1
        path=added.pop();data=json.loads(path.read_text())
        assert data['exit_code']==expected and data['attempts']==1
        row['run_record']=str(path.relative_to(ROOT))
        row['container']=data['container']
    rows.append(row)
base=['--repo',str(REPO)]
run('child-exit-seven',base+['--','python3','-c','raise SystemExit(7)'],7)
code="""from pathlib import Path
import errno
p=Path('/work/sentinel.txt')
try:
    with p.open('r+b'): pass
except OSError as e:
    assert e.errno==errno.EROFS,e
else:
    raise AssertionError('repository was writable')
Path('/work/work/scratch-ok.txt').write_text('scratch writable\\n')
print('read-only repository; writable work verified')
"""
run('readonly-and-work',base+['--','python3','-c',code],0)
assert (REPO/'sentinel.txt').read_text()=='read-only fixture\n'
run('bounded-timeout',base+['--timeout','1','--','python3','-c','import time; time.sleep(20)'],124)
name=rows[-1]['container']
r=subprocess.run(['docker','container','inspect',name],capture_output=True,text=True,timeout=10)
assert r.returncode!=0,'timed-out own container remains'
run('reject-canonical-write',['--write-repo','--','python3','-c','pass'],2,False)
run('reject-host-native-path',['--','python3','/Applications/KiCad/KiCad.app/unsafe.py'],2,False)
run('reject-outside-mount',['--repo','/tmp','--','python3','-c','pass'],2,False)
(OUT/'results.json').write_text(json.dumps({'status':'PASS','tests':rows},indent=2)+'\n')
print(json.dumps(rows,indent=2))
