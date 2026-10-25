import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from sealedbench.v2.pipeline_state import checkpoint, have


class PipelineTests(unittest.TestCase):
    def test_hash_checkpoint_detects_corruption_and_atomic_state(self):
        with tempfile.TemporaryDirectory() as tmp:
            dest=Path(tmp);artifact=dest/'items';artifact.write_bytes(b'items')
            state=dest/'state.json'
            with patch('sealedbench.v2.pipeline_state.artifacts',return_value=[artifact]),patch('sealedbench.v2.pipeline_state.inputs',return_value=[]):
                checkpoint(state,'b2r','release')
            self.assertTrue(have(state,'release'))
            self.assertFalse(have(state,'score'))
            artifact.write_bytes(b'corrupt')
            self.assertFalse(have(state,'release'))
            self.assertFalse(state.with_suffix('.json.partial').exists())
            state.write_text('{partial')
            self.assertFalse(have(state,'release'))

    def test_failed_replay_never_checkpointed(self):
        from sealedbench.v2.pipeline_state import artifacts
        with tempfile.TemporaryDirectory() as tmp:
            dest=Path(tmp)
            (dest/'replay_qwen3-4b-instruct-2507.json').write_text(json.dumps({'matches':0,'compared':1}))
            with patch('sealedbench.v2.pipeline_state.batch_dir',return_value=dest):
                with self.assertRaises(ValueError):artifacts('b2r','replay')

    def test_changed_input_invalidates_checkpoint(self):
        with tempfile.TemporaryDirectory() as tmp:
            dest=Path(tmp);artifact=dest/'scores';artifact.write_bytes(b'scores')
            source=dest/'completion';source.write_bytes(b'answer');state=dest/'state.json'
            with patch('sealedbench.v2.pipeline_state.artifacts',return_value=[artifact]),patch('sealedbench.v2.pipeline_state.inputs',return_value=[source]):
                checkpoint(state,'b2r','score')
            self.assertTrue(have(state,'score'))
            source.write_bytes(b'new answer')
            self.assertFalse(have(state,'score'))

    def test_llama_gate_matches_process_executable_not_prompt_text(self):
        from sealedbench.v2.pipeline_state import llama_active
        self.assertFalse(llama_active('10 codex exec explain /cache/llama-completion\n11 grep llama-completion'))
        self.assertTrue(llama_active('12 /cache/llama-completion -t 6 -n 768'))

if __name__=='__main__':unittest.main()
