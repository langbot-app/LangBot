from __future__ import annotations

import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tools.evaluation.locomo import digest, prepare
from tools.evaluation.pipeline import run, safe_snapshot, validate_profile


def inputs() -> tuple[dict, dict]:
    questions = [
        {
            'id': 'conv-1/q1',
            'sample_id': 'conv-1',
            'question': 'What?',
            'reference_answer': 'yes',
            'gold_evidence': ['D1:1'],
        }
    ]
    plan = {
        'questions': questions,
        'question_set_sha256': digest(questions),
        'dataset_sha256': 'a' * 64,
        'planned_question_ids': ['conv-1/q1'],
    }
    profile = {
        'protocol': {
            'protocol_id': 'pilot-v1',
            'embedding_model': 'MiniLM384',
            'answer_model': 'flash',
            'answer_policy': 'source-only-v1',
            'answer_temperature': 0,
            'answer_max_tokens': 256,
            'judge_model': 'flash',
            'judge_policy': 'strict-v1',
            'context_budget_bytes': 12000,
            'execution_layer': 'langbot.pipeline',
        },
        'provenance': {
            'core_sha': 'abc',
            'sdk_version': '0.7.25',
            'plugins': {'LocalAgent': '0.1'},
        },
        'arms': {'baseline': {'pipelines': {'conv-1': 'pipeline-1'}}},
    }
    return plan, profile


class PublicEvaluationPipelineTests(unittest.TestCase):
    def test_snapshot_preserves_generation_limits(self) -> None:
        snapshot = safe_snapshot({'max_tokens': 256, 'api_key': 'private', 'access_token': 'private'})
        self.assertEqual(snapshot['max_tokens'], 256)
        self.assertEqual(snapshot['api_key'], '[redacted]')
        self.assertEqual(snapshot['access_token'], '[redacted]')

    def test_resume_rejects_tampered_question(self) -> None:
        plan, profile = inputs()
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            with patch(
                'tools.evaluation.pipeline.operation',
                side_effect=[{'config': 'one'}, {'status': 'completed', 'reply': 'yes'}],
            ):
                run(plan, profile, directory, 'http://127.0.0.1:5300', 'key')
            path = directory / 'baseline.json'
            result = json.loads(path.read_text())
            result['results'][0]['question'] = 'changed'
            path.write_text(json.dumps(result))
            with patch('tools.evaluation.pipeline.operation', return_value={'config': 'one'}):
                with self.assertRaises(ValueError):
                    run(plan, profile, directory, 'http://127.0.0.1:5300', 'key')

    def test_plan_integrity_and_missing_pipeline_fail_before_execution(self) -> None:
        plan, profile = inputs()
        bad = copy.deepcopy(plan)
        bad['questions'][0]['question'] = 'Changed'
        with self.assertRaises(ValueError):
            validate_profile(bad, profile)
        profile['arms']['baseline']['pipelines'] = {}
        with self.assertRaises(ValueError):
            validate_profile(plan, profile)

    def test_run_submits_only_question_and_resumes_completed_checkpoint(self) -> None:
        plan, profile = inputs()
        calls = []

        def operation(base_url, key, name, payload, **kwargs):
            calls.append((name, payload))
            if name == 'pipeline.get':
                return {'uuid': 'pipeline-1', 'config': {'api_key': 'private'}}
            return {'status': 'completed', 'reply': 'yes', 'query_id': 'query-1'}

        with (
            tempfile.TemporaryDirectory() as tmp,
            patch('tools.evaluation.pipeline.operation', operation),
        ):
            directory = Path(tmp)
            run(plan, profile, directory, 'http://127.0.0.1:5300', 'private')
            run(plan, profile, directory, 'http://127.0.0.1:5300', 'private')
            submissions = [payload for name, payload in calls if name == 'pipeline.run']
            self.assertEqual(len(submissions), 1)
            self.assertEqual(submissions[0]['text'], 'What?')
            self.assertNotIn('private', (directory / 'pipelines.json').read_text())
            result = json.loads((directory / 'baseline.json').read_text())
            self.assertTrue(result['complete'])
            self.assertEqual(result['results'][0]['reference_answer'], 'yes')

    def test_unknown_submission_is_saved_and_never_retried_on_resume(self) -> None:
        plan, profile = inputs()
        submissions = []

        def operation(base_url, key, name, payload, **kwargs):
            if name == 'pipeline.get':
                return {'uuid': 'pipeline-1'}
            submissions.append(payload)
            raise TimeoutError()

        with (
            tempfile.TemporaryDirectory() as tmp,
            patch('tools.evaluation.pipeline.operation', operation),
        ):
            directory = Path(tmp)
            with self.assertRaises(RuntimeError):
                run(plan, profile, directory, 'http://127.0.0.1:5300', 'private')
            with self.assertRaises(ValueError):
                run(plan, profile, directory, 'http://127.0.0.1:5300', 'private')
            self.assertEqual(len(submissions), 1)
            self.assertEqual(
                json.loads((directory / 'baseline.json').read_text())['results'][0]['status'],
                'unknown',
            )
            self.assertFalse((directory / '.lock').exists())

    def test_pipeline_configuration_drift_requires_new_run(self) -> None:
        plan, profile = inputs()
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            with patch(
                'tools.evaluation.pipeline.operation',
                side_effect=[
                    {'config': 'one'},
                    {'status': 'completed', 'reply': 'yes'},
                ],
            ):
                run(plan, profile, directory, 'http://127.0.0.1:5300', 'key')
            with patch('tools.evaluation.pipeline.operation', return_value={'config': 'two'}):
                with self.assertRaises(ValueError):
                    run(plan, profile, directory, 'http://127.0.0.1:5300', 'key')

    def test_dataset_checksum_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'dataset.json'
            path.write_text('[]')
            with self.assertRaises(ValueError):
                prepare(path)


if __name__ == '__main__':
    unittest.main()
