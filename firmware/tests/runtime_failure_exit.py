"""A failed actual-worker assertion must exit, even with a blocked bus waiter."""
import os
import subprocess
import sys

try:
    result = subprocess.run([sys.argv[1]], env={**os.environ, 'SB_TEST_FAILED_BLOCKED_EXIT': '1'},
                            capture_output=True, text=True, timeout=3)
except subprocess.TimeoutExpired as error:
    print('FAILED: assertion hung in live-worker/global teardown', file=sys.stderr)
    if error.stderr: print(error.stderr.decode() if isinstance(error.stderr,bytes) else error.stderr,file=sys.stderr)
    raise SystemExit(1)
expected='EXPECTED FAILURE: blocked owner exits without global destructor wait'
if result.returncode!=1 or expected not in result.stderr:
    print(result.stderr,file=sys.stderr)
    raise SystemExit('Failure probe did not reach the expected assertion/exit')
print('Blocked-owner assertion produced its diagnostic and exited with status 1')
