from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tools.evaluation.judge import grade


class PublicEvaluationJudgeTests(unittest.TestCase):
    def test_judge_resumes_only_under_same_instruction_and_source(self) -> None:
        payload = {
            'complete': True,
            'protocol': {'judge_model': 'flash', 'judge_policy': 'strict-v1'},
            'planned_question_ids': ['c/q1'],
            'results': [{'id': 'c/q1', 'status': 'completed', 'question': 'Q', 'reference_answer': 'A', 'answer': 'A'}],
        }
        raw = {'choices': [{'message': {'content': '{"correct":true,"reason":"same"}'}}], 'usage': {'total_tokens': 20}}
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / 'judged.json'
            with patch('tools.evaluation.judge.urllib.request.build_opener') as opener:
                response = opener.return_value.open.return_value.__enter__.return_value
                response.read.return_value = json.dumps(raw).encode()
                grade(payload, output, 'https://example.org/v1', 'key')
                grade(payload, output, 'https://example.org/v1', 'key')
                self.assertEqual(opener.call_count, 1)
            with self.assertRaises(ValueError):
                grade(payload, output, 'https://different.org/v1', 'key')
            saved = json.loads(output.read_text())
            saved['results'][0]['answer'] = 'tampered'
            output.write_text(json.dumps(saved))
            with self.assertRaises(ValueError):
                grade(payload, output, 'https://example.org/v1', 'key')

    def test_incomplete_run_is_rejected_without_model_call(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, self.assertRaises(ValueError):
            grade({'complete': False}, Path(tmp) / 'out.json', 'https://example.org/v1', 'key')


if __name__ == '__main__':
    unittest.main()
