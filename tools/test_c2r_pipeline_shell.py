"""Exercise real shell retry/checkpoint/publish functions with local fault injection."""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

SOURCE=Path('tools/p2r_b2_pipeline_v2.sh').read_text()
RETRY=SOURCE[SOURCE.index('retry_delay='):SOURCE.index('if [[ "$BATCH" == b2 ]]; then\n  UNLOCK=')]
PUBLISH=SOURCE[SOURCE.index('publish_git() {'):SOURCE.index('retry publish_git')]


class ShellTests(unittest.TestCase):
    def run_shell(self, text):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'tools';path.mkdir()
            (path/'secret_scan.sh').write_text('#!/bin/bash\nexit 0\n')
            got=subprocess.run(['bash','-euc',text],cwd=tmp,text=True,capture_output=True,timeout=10,env={**os.environ,'SEALEDBENCH_RETRY_DELAY':'0'})
            self.assertEqual(got.returncode,0,got.stdout+got.stderr)
            return got.stdout

    def test_failure_and_failed_checkpoint_retry_then_skip(self):
        got=self.run_shell(RETRY+'''
beat() { :; }
disk_ok() { return 0; }
have_step() { test -f done; }
done_step() {
  local n=0; if test -f checkpoints; then n=$(cat checkpoints); fi
  n=$((n+1)); echo "$n" > checkpoints
  if (( n==1 )); then return 1; fi
  touch done
}
operation() {
  local n=0; if test -f attempts; then n=$(cat attempts); fi
  n=$((n+1)); echo "$n" > attempts
  if (( n==1 )); then return 1; fi
}
run_step release operation
run_step release operation
test "$(cat attempts)" == 3
test "$(cat checkpoints)" == 2
''')
        self.assertIn('STEP_RETRY',got)
        self.assertIn('STEP_SKIP release',got)

    def test_push_failure_retries_after_local_commit(self):
        got=self.run_shell(RETRY+PUBLISH+'''
BATCH=b2
beat() { :; }
disk_ok() { return 0; }
python3() { return 0; }
git() {
  if [[ "$1 $2" == 'branch --show-current' ]]; then echo p2r; return; fi
  if [[ "$1" == diff ]]; then test -f committed; return; fi
  if [[ "$1" == commit ]]; then test ! -f committed; touch committed; echo COMMITTED; return; fi
  if [[ "$1" == push ]]; then
    if test ! -f push_attempt; then touch push_attempt; echo PUSH_FAILED; return 1; fi
    echo PUSH_OK; return 0
  fi
  return 1
}
retry publish_git
echo COMPLETE
''')
        self.assertEqual(got.count('COMMITTED'),1)
        self.assertLess(got.index('PUSH_FAILED'),got.index('PUSH_OK'))
        self.assertLess(got.index('PUSH_OK'),got.index('COMPLETE'))

if __name__=='__main__':unittest.main()
