"""Challenge isolation oracles with serialized, duplicated, and crossed evidence."""

import copy
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest

from regression_ci import suite_profile
from regression_isolation_cases import CASE_NAMES, check_reply, overlapping, verify_wire
from regression_local_cases import DEFAULT_GROUPS
from regression_scenarios import expanded_profile
from regression_suite import validate


class IsolationTests(unittest.TestCase):
    def test_sync_stream_snapshots_cannot_hide_foreign_or_incomplete_output(self):
        expected = 'LANGBOT_SLOW_OK GROUP_ACK=aaaa'

        def parts(texts):
            return [{'type': 'Plain', 'text': text} for text in texts]

        check_reply(parts(['LANGBOT_', expected, expected]), expected)
        for texts in ([], ['LANGBOT_'], [expected, 'LANGBOT_'], [expected, expected + ' GROUP_ACK=bbbb']):
            with self.subTest(texts=texts), self.assertRaises(ValueError):
                check_reply(parts(texts), expected)

    def test_dedicated_finite_profile_does_not_expand_daily(self):
        profile, _ = suite_profile('isolation', 'test')
        validate(profile)
        self.assertEqual([case['scenario'] for case in profile['cases']], list(CASE_NAMES))
        self.assertNotIn('execution', profile)
        self.assertNotIn('isolation', DEFAULT_GROUPS)
        self.assertFalse(set(CASE_NAMES) & {case.get('scenario') for case in expanded_profile(DEFAULT_GROUPS)['cases']})
        with self.assertRaisesRegex(ValueError, 'dedicated suite'):
            expanded_profile(['isolation'])

    def test_serial_execution_or_incomplete_timing_cannot_pass_overlap(self):
        first = {'started_at': '2026-10-29 01:00:00', 'finished_at': '2026-10-29 01:00:02'}
        second = {'started_at': '2026-10-29 01:00:01', 'finished_at': '2026-10-29 01:00:03'}
        self.assertEqual(overlapping([first, second]), [first, second])
        for invalid in ({**second, 'started_at': first['finished_at']}, {**second, 'finished_at': None}):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                overlapping([first, invalid])

    def test_wire_rejects_crossed_history_duplicates_wrong_model_and_wrong_reply(self):
        receipt = {'group': 'test-a', 'token': 'bbbb', 'model': 'mock-slow', 'expected': 'LANGBOT_SLOW_OK'}
        record = {
            'status': 200,
            'response_complete': True,
            'request': {
                'model': 'mock-slow',
                'messages': [
                    {'role': 'user', 'content': 'LB_GROUP=test-a LB_TURN=1 LB_TOKEN=aaaa LB_PREVIOUS=none'},
                    {'role': 'assistant', 'content': 'LANGBOT_SLOW_OK GROUP_ACK=aaaa'},
                    {'role': 'user', 'content': 'LB_GROUP=test-a LB_TURN=2 LB_TOKEN=bbbb LB_PREVIOUS=aaaa'},
                ],
            },
            'response': {'content': 'LANGBOT_SLOW_OK GROUP_ACK=bbbb'},
        }
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'wire.jsonl'
            suite = SimpleNamespace(profile={'smoke': {'mock_records': str(path)}}, path=lambda value: value)

            def check(rows):
                path.write_text(''.join(json.dumps(row) + '\n' for row in rows))
                return verify_wire(suite, {}, [receipt])

            self.assertEqual(check([record])['requests'], 1)
            crossed = copy.deepcopy(record)
            crossed['request']['messages'][0]['content'] = crossed['request']['messages'][0]['content'].replace(
                'test-a', 'test-b'
            )
            wrong_model = copy.deepcopy(record)
            wrong_model['request']['model'] = 'mock-chat'
            wrong_reply = copy.deepcopy(record)
            wrong_reply['response']['content'] = 'LANGBOT_SLOW_OK GROUP_ACK=aaaa'
            incomplete = {**record, 'response_complete': False}
            for rows in ([], [record, record], [crossed], [wrong_model], [wrong_reply], [incomplete]):
                with self.subTest(rows=rows), self.assertRaises(ValueError):
                    check(rows)


if __name__ == '__main__':
    unittest.main()
