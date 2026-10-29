"""Challenge lifecycle retrieval oracles and keep the optional suite isolated."""

import copy
import unittest

from regression_ci import SUITE_BUDGETS, suite_profile
from regression_state import document_absent, document_visible
from regression_suite import validate


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

    def test_state_profile_does_not_change_smoke_or_daily_cases(self):
        smoke, _ = suite_profile('smoke', 'before')
        daily, _ = suite_profile('daily', 'before')
        expected = copy.deepcopy((smoke, daily))
        state, _ = suite_profile('state', 'state')
        validate(state)
        self.assertEqual((smoke, daily), expected)
        self.assertEqual(state['coverage_suite'], 'state')
        self.assertNotIn('execution', state)
        self.assertNotIn('scenario_groups', state)
        self.assertEqual(SUITE_BUDGETS['state'], 300)
        self.assertTrue(all(not resource.get('documents') for resource in state['resources']))
        self.assertTrue(all('state' not in case['name'] for case in smoke['cases'] + daily['cases']))


if __name__ == '__main__':
    unittest.main()
