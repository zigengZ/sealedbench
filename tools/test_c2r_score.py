import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from sealedbench.v2.scoring import _baseline, score_batch


class ScoreTests(unittest.TestCase):
    def test_baseline_is_observed_set_including_code(self):
        self.assertEqual(_baseline([{'oracle_answer':'1'},{'oracle_answer':'9'}])['uniform_over_observed_answers'],.5)
        self.assertEqual(_baseline([{'oracle_answer':'a\nb'},{'oracle_answer':'c'},{'oracle_answer':'c'}])['distinct_observed_answers'],2)

    def test_strict_truncation_and_failed_outputs_count_wrong(self):
        manifest=json.loads(Path('results/batches/b2/manifest.json').read_text())
        manifest['models']=manifest['models'][:1]
        manifest['generator']['families']=[{'name':'arith_word','n':4},{'name':'code_output','n':0},{'name':'graph_path','n':0}]
        manifest['reference']['n']=1
        model=manifest['models'][0]['id']
        items=[{'item_id':f'arith_word-{i:04d}','family':'arith_word','oracle_answer':'7','params':{'template_id':'test'}} for i in range(4)]
        with tempfile.TemporaryDirectory() as tmp:
            dest=Path(tmp);runs=dest/'runs'/model;runs.mkdir(parents=True)
            (dest/'items.jsonl').write_text(''.join(json.dumps(i)+'\n' for i in items))
            for i, (answer, runs_n, rc) in enumerate([('#### 7\n[end of text]',10,0),('7\n[end of text]',10,0),('#### 7\n[end of text]',767,0),('#### 7\n[end of text]',10,1)]):
                stem=runs/f'arith_word-{i:04d}'
                stem.with_suffix('.txt').write_text(answer)
                stem.with_suffix('.stderr').write_text(f'eval time = 10.0 ms / {runs_n} runs')
                stem.with_suffix('.json').write_text(json.dumps({'returncode':rc}))
            with patch('sealedbench.v2.scoring.batch_dir',return_value=dest),patch('sealedbench.v2.scoring.load_manifest',return_value=manifest),patch('sealedbench.v2.scoring._v2_reference',return_value=[{'item_id':'gsm8k-0000','oracle_answer':'7'}]):
                self.assertEqual(score_batch('b2r'),0)
            row=json.loads((dest/'scores.json').read_text())['models'][model]
            block=row['families']['arith_word']
            self.assertEqual((block['n'],block['correct'],block['invalid'],block['truncated']),(4,1,3,1))
            self.assertEqual(row['status'],'PARTIAL')
            self.assertEqual(row['gsm8k']['n'],1)
            self.assertEqual(row['gsm8k']['invalid'],1)
            self.assertEqual(block['truncated_rate'],.25)
            manifest['generator']['families'][0]['n']=5
            with patch('sealedbench.v2.scoring.batch_dir',return_value=dest),patch('sealedbench.v2.scoring.load_manifest',return_value=manifest):
                with self.assertRaisesRegex(ValueError,'item counts'):score_batch('b2r')

if __name__=='__main__':unittest.main()
