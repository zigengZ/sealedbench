import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from sealedbench.infer import completion_cmd, n_predict_for, run_item
from sealedbench.v2.replay_run import replay_v2


class InferTests(unittest.TestCase):
    def setUp(self):
        self.manifest = json.loads(Path('results/batches/b2/manifest.json').read_text())
        self.model = self.manifest['models'][0]

    def test_frozen_command(self):
        with patch('sealedbench.infer.resolve_binary', return_value=Path('/llama')):
            for family, cap in [('arith_word',768),('code_output',512),('graph_path',768),('gsm8k',768)]:
                cmd = completion_cmd(self.manifest, self.model, 'question', family)
                for flag, value in [('-t','6'),('-tb','6'),('-n',str(cap)),('-b','2048'),('-ub','512'),('--temp','0'),('--top-k','1'),('--top-p','1'),('--min-p','0'),('--seed','42'),('--reasoning','off')]:
                    self.assertEqual(cmd[cmd.index(flag)+1], value)
                self.assertIn('--jinja', cmd)
                self.assertNotIn('--prompt-cache', cmd)
        self.manifest['runtime']['n_predict']['gsm8k'] = 555
        self.assertEqual(n_predict_for(self.manifest, 'gsm8k'), 555)

    def test_restart_reuses_intact_success_and_terminal_failure(self):
        with tempfile.TemporaryDirectory() as tmp:
            dest = Path(tmp)
            (dest/'item.txt').write_bytes(b'ok')
            for rc, attempt in [(0,1),(124,2)]:
                meta = {'returncode':rc,'attempt':attempt,'stdout_sha256':hashlib.sha256(b'ok').hexdigest()}
                (dest/'item.json').write_text(json.dumps(meta))
                with patch('sealedbench.infer._run_once') as run:
                    self.assertEqual(run_item(self.manifest,self.model,'item','arith_word','q',dest),meta)
                    run.assert_not_called()

    def test_corrupt_cached_output_is_rerun(self):
        with tempfile.TemporaryDirectory() as tmp:
            dest = Path(tmp)
            (dest/'item.txt').write_bytes(b'broken')
            (dest/'item.json').write_text(json.dumps({'returncode':0,'stdout_sha256':'bad'}))
            with patch('sealedbench.infer.completion_cmd',return_value=['llama']), patch('sealedbench.infer._run_once',return_value=(0,b'fresh',b'',1,None)) as run:
                got = run_item(self.manifest,self.model,'item','arith_word','q',dest)
                self.assertEqual(got['stdout_sha256'], hashlib.sha256(b'fresh').hexdigest())
                run.assert_called_once()

    def test_replay_is_fresh_and_accepts_a_small_batch(self):
        with tempfile.TemporaryDirectory() as tmp:
            dest = Path(tmp)
            (dest/'manifest.json').write_text(json.dumps(self.manifest))
            (dest/'items.jsonl').write_text(json.dumps({'item_id':'a','family':'arith_word','prompt':'q'})+'\n')
            published=dest/'runs'/self.model['id']; published.mkdir(parents=True)
            (published/'a.txt').write_bytes(b'answer')
            lock=(dest/'lock').open('w')
            dirs=[]
            def fresh(*args):
                path=dest/f'fresh{len(dirs)}';path.mkdir();dirs.append(path);return path
            def run(*args):
                (args[-1]/'a.txt').write_bytes(b'answer');return {'returncode':0}
            with patch('sealedbench.v2.replay_run.batch_dir',return_value=dest), patch('sealedbench.v2.replay_run.fresh_replay_dir',side_effect=fresh), patch('sealedbench.v2.replay_run.run_item',side_effect=run) as runner, patch('sealedbench.v2.replay_run._lock',side_effect=lambda: (dest/'lock').open('a')):
                self.assertEqual(replay_v2(self.model['id'],10,'b2r'),0)
                self.assertEqual(replay_v2(self.model['id'],10,'b2r'),0)
                self.assertEqual(runner.call_count,2)
                self.assertNotEqual(dirs[0],dirs[1])
            lock.close()

if __name__=='__main__':
    unittest.main()
