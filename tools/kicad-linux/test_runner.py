"""Host-only fault tests for wrapper bookkeeping; no Docker/native launch."""
import contextlib,importlib.machinery,importlib.util,io,json,subprocess,tempfile,unittest
from pathlib import Path
from unittest.mock import patch,Mock
ROOT=Path(__file__).resolve().parents[2]
loader=importlib.machinery.SourceFileLoader('kicad_runner',str(ROOT/'tools/kicad-run'))
spec=importlib.util.spec_from_loader(loader.name,loader);runner=importlib.util.module_from_spec(spec);loader.exec_module(runner)
IMAGE='sha256:'+'a'*64
class RunnerRecords(unittest.TestCase):
 def fixture(self,tmp):
  root=Path(tmp);folder=root/'tools/kicad-linux';folder.mkdir(parents=True)
  (folder/'image.lock.json').write_text(json.dumps({'image_id':IMAGE,'architecture':'arm64','kicad_package_version':'10.0.7'}))
  return root
 def execute(self,root,proc,stop_effect=None,popen_effect=None):
  info=[{'Id':IMAGE,'Os':'linux','Architecture':'arm64','Config':{'Labels':{'org.opencontainers.image.title':'Smart Blinds isolated KiCad runner'}}}]
  with patch.object(runner,'PROJECT',root),patch.object(runner.shutil,'which',return_value='/fake/docker'),patch.object(runner.sys,'argv',['kicad-run','--timeout','1','--','python3','-c','pass']),patch.object(runner.subprocess,'check_output',return_value=json.dumps(info)),patch.object(runner.subprocess,'Popen',side_effect=popen_effect,return_value=proc),patch.object(runner.subprocess,'run',side_effect=stop_effect,return_value=subprocess.CompletedProcess([],0))as stop,contextlib.redirect_stdout(io.StringIO()):
   result=runner.main()
  records=list((root/'work/kicad-runs').glob('*/run.json'));self.assertEqual(len(records),1)
  return result,json.loads(records[0].read_text()),stop
 def test_stop_timeout_still_records_failure(self):
  with tempfile.TemporaryDirectory(prefix='runner-record-',dir=ROOT/'work')as tmp:
   root=self.fixture(tmp);proc=Mock();proc.wait.side_effect=[subprocess.TimeoutExpired('child',1),0]
   result,record,stop=self.execute(root,proc,subprocess.TimeoutExpired('docker stop',15))
   self.assertEqual(result,124);self.assertTrue(record['timed_out']);self.assertEqual(record['status'],'complete')
   self.assertIn('error',record['cleanup'][0]);self.assertEqual(record['attempts'],1)
   self.assertEqual(stop.call_args.args[0][-1],record['container'])
 def test_stop_os_error_still_records_failure(self):
  with tempfile.TemporaryDirectory(prefix='runner-record-',dir=ROOT/'work')as tmp:
   root=self.fixture(tmp);proc=Mock();proc.wait.side_effect=[subprocess.TimeoutExpired('child',1),0]
   result,record,_=self.execute(root,proc,OSError('test stop unavailable'))
   self.assertEqual(result,124);self.assertIn('test stop unavailable',record['cleanup'][0]['error'])
 def test_launch_failure_still_records(self):
  with tempfile.TemporaryDirectory(prefix='runner-record-',dir=ROOT/'work')as tmp:
   result,record,_=self.execute(self.fixture(tmp),Mock(),popen_effect=OSError('test launch unavailable'))
   self.assertEqual(result,125);self.assertEqual(record['cleanup'][0]['action'],'launch')
 def test_termination_signal_cleans_only_own_container(self):
  with tempfile.TemporaryDirectory(prefix='runner-record-',dir=ROOT/'work')as tmp:
   root=self.fixture(tmp);proc=Mock();proc.wait.side_effect=[runner.RunnerInterrupted(15),0]
   result,record,stop=self.execute(root,proc)
   self.assertEqual(result,143);self.assertFalse(record['timed_out'])
   self.assertEqual(stop.call_args.args[0][-1],record['container'])
 def test_image_inspect_timeout_is_recorded_before_container(self):
  with tempfile.TemporaryDirectory(prefix='runner-record-',dir=ROOT/'work')as tmp:
   root=self.fixture(tmp)
   with patch.object(runner,'PROJECT',root),patch.object(runner.shutil,'which',return_value='/fake/docker'),patch.object(runner.sys,'argv',['kicad-run','--','python3','-c','pass']),patch.object(runner.subprocess,'check_output',side_effect=subprocess.TimeoutExpired('image inspect',15)),patch.object(runner.subprocess,'Popen')as launch,contextlib.redirect_stderr(io.StringIO()):
    with self.assertRaises(SystemExit)as error:runner.main()
   self.assertEqual(error.exception.code,2);launch.assert_not_called()
   record=json.loads(next((root/'work/kicad-runs').glob('*/run.json')).read_text())
   self.assertEqual(record['status'],'preflight_failed');self.assertFalse(record['container_started'])
 def test_writable_non_scratch_subdirectory_rejected(self):
  with tempfile.TemporaryDirectory(prefix='runner-record-',dir=ROOT/'work')as tmp:
   root=self.fixture(tmp)
   with patch.object(runner,'PROJECT',root),patch.object(runner.sys,'argv',['kicad-run','--repo',str(root/'tools'),'--write-repo','--','python3','-c','pass']),patch.object(runner.subprocess,'check_output')as inspect,contextlib.redirect_stderr(io.StringIO()):
    with self.assertRaises(SystemExit)as error:runner.main()
   self.assertEqual(error.exception.code,2);inspect.assert_not_called()
if __name__=='__main__':unittest.main()
