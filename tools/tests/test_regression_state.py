"""Challenge lifecycle retrieval oracles and keep the optional suite isolated."""

import copy
import unittest
from unittest.mock import patch

from tools.entrypoints.regression_ci import SUITE_BUDGETS, suite_profile
from tools.regression.regression_state import document_absent, document_visible, monitor_run
from tools.entrypoints.regression_suite import validate


class StateLifecycleTest(unittest.TestCase):
    def test_document_identity_and_content_are_both_required(self):
        document = {'engine_document_id': 'original-file'}
        original = {'metadata': {'file_id': 'original-file'}, 'content': [{'text': 'original-marker'}]}
        self.assertTrue(document_visible([original], document, 'original-marker'))
        self.assertFalse(document_visible([], document, 'original-marker'))
        for changed in (
            {'metadata': {'file_id': 'other-file'}, 'content': original['content']},
            {'metadata': original['metadata'], 'content': [{'text': 'other-marker'}]},
        ):
            with self.subTest(changed=changed):
                self.assertFalse(document_visible([changed], document, 'original-marker'))
                self.assertFalse(document_absent([changed], document, 'original-marker'))
        self.assertFalse(document_absent([original], document, 'original-marker'))
        self.assertTrue(document_absent([], document, 'original-marker'))

    def test_monitoring_recognizes_exact_completed_run_and_conversation(self):
        current = {'run_id': 'the-run', 'status': 'completed'}
        readable = {
            'source': 'agent',
            'run': current,
            'row': {'id': 'the-run', 'status': 'completed', 'conversation_id': 'group_session', 'finished_at_ms': 1234},
        }
        auth = {'Authorization': 'Bearer test-token'}
        with (
            patch('tools.regression.regression_state.user_headers', return_value=auth),
            patch('tools.regression.regression_state.request') as request,
        ):
            row = {}
            request.return_value = readable
            monitor_run(None, row, 'original', current, 'session')
            request.assert_called_once_with(
                None, row, 'GET', '/api/v1/monitoring/executions/agent/the-run?section=overview', headers=auth
            )
            self.assertEqual(row['assertions'], {'original_monitoring_readback': 'passed'})
            self.assertEqual(row['monitoring'][0]['conversation_id'], 'group_session')
            for location, key, changed in (
                ('run', 'run_id', 'neighbor-run'),
                ('run', 'status', 'running'),
                ('row', 'id', 'neighbor-run'),
                ('row', 'status', 'cancelled'),
                ('row', 'conversation_id', 'group_neighbor'),
                ('row', 'finished_at_ms', None),
            ):
                with self.subTest(location=location, key=key):
                    response = copy.deepcopy(readable)
                    response[location][key] = changed
                    request.return_value = response
                    rejected = {}
                    with self.assertRaises(ValueError):
                        monitor_run(None, rejected, 'wrong', current, 'session')
                    self.assertEqual(rejected['assertions'], {'wrong_monitoring_readback': 'failed'})
                    self.assertNotIn('monitoring', rejected)

    def test_state_profile_does_not_change_smoke_or_daily_cases(self):
        normal_profiles = ('smoke', 'daily')
        before = {name: suite_profile(name, 'test')[0] for name in normal_profiles}
        state, _ = suite_profile('state', 'state')
        validate(state)
        after = {name: suite_profile(name, 'test')[0] for name in normal_profiles}
        self.assertEqual(after, before)
        self.assertEqual([case['name'] for case in state['cases']], ['durable_state_lifecycle'])
        self.assertEqual(state['coverage_suite'], 'state')
        self.assertNotIn('execution', state)
        self.assertNotIn('scenario_groups', state)
        self.assertEqual(SUITE_BUDGETS['state'], 300)
        self.assertTrue(all(not resource.get('documents') for resource in state['resources']))
        for profile in after.values():
            self.assertNotIn('durable_state_lifecycle', {case['name'] for case in profile['cases']})


if __name__ == '__main__':
    unittest.main()
