from __future__ import annotations

import copy
import unittest

from tools.evaluation.traces import attach


class PublicEvaluationTraceTests(unittest.TestCase):
    def test_observed_model_and_budget_must_match_protocol(self) -> None:
        payload = {
            'protocol': {'answer_model': 'flash', 'context_budget_bytes': 12000},
            'results': [
                {
                    'id': 'conv/q1',
                    'question': 'Question',
                    'started_at': '2026-01-01T00:00:00+00:00',
                    'finished_at': '2026-01-01T00:01:00+00:00',
                }
            ],
        }
        request = {
            'event': 'request_start',
            'request_id': 'one',
            'timestamp': '2026-01-01T00:00:05+00:00',
            'request_body': {
                'model': 'other',
                'messages': [
                    {
                        'role': 'user',
                        'content': [{'type': 'text', 'text': 'Event data'}, {'type': 'text', 'text': 'Question'}],
                    }
                ],
            },
        }
        response = {'event': 'request_complete', 'request_id': 'one', 'outcome': 'ok'}
        self.assertEqual(attach(payload, [request, response])['results'][0]['model_trace_status'], 'model_mismatch')
        request['request_body']['model'] = 'flash'
        self.assertEqual(attach(payload, [request, response])['model_trace_coverage'], 1)
        payload['protocol']['context_budget_bytes'] = 1
        self.assertEqual(attach(payload, [request, response])['results'][0]['model_trace_status'], 'budget_exceeded')

    def test_trace_requires_question_time_and_completed_upstream(self) -> None:
        payload = {
            'results': [
                {
                    'id': 'conv/q1',
                    'question': 'Question',
                    'started_at': '2026-01-01T00:00:00+00:00',
                    'finished_at': '2026-01-01T00:01:00+00:00',
                }
            ]
        }
        request = {
            'event': 'request_start',
            'request_id': 'request-1',
            'timestamp': '2026-01-01T00:00:05+00:00',
            'request_body': {'messages': [{'role': 'user', 'content': [{'type': 'text', 'text': 'Question'}]}]},
        }
        response = {
            'event': 'request_complete',
            'request_id': 'request-1',
            'outcome': 'ok',
        }
        verified = attach(payload, [request, response])
        self.assertEqual(verified['model_trace_coverage'], 1)
        self.assertFalse(verified['results'][0]['retrieval_trace_available'])
        self.assertEqual(attach(payload, [request])['results'][0]['model_trace_status'], 'incomplete')
        unrelated = copy.deepcopy(request)
        unrelated['request_body']['messages'][0]['content'] = 'Other question'
        self.assertEqual(attach(payload, [unrelated, response])['model_trace_coverage'], 0)

    def test_one_request_cannot_be_attributed_twice(self) -> None:
        row = {
            'question': 'Question',
            'started_at': '2026-01-01T00:00:00+00:00',
            'finished_at': '2026-01-01T00:01:00+00:00',
        }
        request = {
            'event': 'request_start',
            'request_id': 'one',
            'timestamp': '2026-01-01T00:00:05+00:00',
            'request_body': {'messages': [{'role': 'user', 'content': 'Question'}]},
        }
        with self.assertRaises(ValueError):
            attach({'results': [row, copy.deepcopy(row)]}, [request])


if __name__ == '__main__':
    unittest.main()
