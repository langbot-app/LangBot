"""Challenge plugin lifecycle task verdicts and worker cleanup evidence."""

from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from regression_ci import suite_profile
from regression_local_cases import DEFAULT_GROUPS
from regression_plugin_lifecycle import failed_generation_safe, wait_task, workers_stopped
from regression_suite import validate


class PluginLifecycleTests(unittest.TestCase):
    def test_failed_generation_cannot_pass_by_http_status_alone(self):
        path = '/api/v1/plugins/regression-qa/probe'

        def plugin(version, status):
            return (
                200,
                {
                    'code': 0,
                    'data': {
                        'plugin': {
                            'status': status,
                            'manifest': {
                                'manifest': {
                                    'metadata': {'author': 'regression-qa', 'name': 'probe', 'version': version},
                                }
                            },
                        }
                    },
                },
            )

        for responses in (
            [(404, {'code': 0})],
            [plugin('0.0.2', 'initialized')],
            [plugin('0.0.9', 'mounted')],
            [plugin('0.0.2', 'mounted'), (200, {'code': 0, 'data': {}})],
            [plugin('0.0.2', 'mounted'), (500, {'code': 0})],
        ):
            row = {}
            with self.subTest(responses=responses), patch('regression_plugin_lifecycle.api', side_effect=responses):
                with self.assertRaises(ValueError):
                    failed_generation_safe(None, row, path, Mock())
                self.assertEqual(row['assertions']['failed_generation_safe'], 'failed')

        for responses in (
            [(404, {'code': -1})],
            [plugin('0.0.2', 'mounted'), (400, {'code': -1})],
        ):
            row, verify_good = {}, Mock()
            with self.subTest(responses=responses), patch('regression_plugin_lifecycle.api', side_effect=responses):
                failed_generation_safe(None, row, path, verify_good)
                self.assertEqual(row['assertions']['failed_generation_safe'], 'passed')
                verify_good.assert_not_called()

        for state_error in (None, ValueError('Restored plugin lost configuration or stored data')):
            row, verify_good = {}, Mock(side_effect=state_error)
            with (
                self.subTest(state_error=state_error),
                patch('regression_plugin_lifecycle.api', return_value=plugin('0.0.1', 'initialized')),
            ):
                if state_error:
                    with self.assertRaisesRegex(ValueError, 'lost configuration'):
                        failed_generation_safe(None, row, path, verify_good)
                    self.assertEqual(row['assertions']['failed_generation_safe'], 'failed')
                else:
                    failed_generation_safe(None, row, path, verify_good)
                    self.assertEqual(row['assertions']['failed_generation_safe'], 'passed')
                verify_good.assert_called_once_with()

    def test_job_is_opt_in_and_does_not_expand_daily(self):
        profile, _ = suite_profile('plugin-lifecycle', 'run')
        validate(profile)
        self.assertEqual(len(profile['cases']), 3)
        self.assertEqual(profile['resources'], [])
        self.assertNotIn('plugin-lifecycle', DEFAULT_GROUPS)
        for name in ('smoke', 'daily'):
            existing, _ = suite_profile(name, 'run')
            self.assertFalse(any(c.get('scenario', '').startswith('plugin_') for c in existing['cases']))

    def test_expected_failure_requires_a_failed_task_not_http_success(self):
        suite = SimpleNamespace(timeout=lambda seconds: seconds)
        for task in (
            {'id': 7, 'status': 'succeeded'},
            {'id': 7, 'status': 'cancelled'},
            {'id': 7, 'status': 'failed', 'error': None},
            {'id': 8, 'status': 'failed', 'error': {'type': 'task_failed'}},
        ):
            with self.subTest(task=task), patch('regression_plugin_lifecycle.request', return_value=task):
                with self.assertRaises(ValueError):
                    wait_task(suite, {}, 7, 'failed', 'broken_upgrade')
        row = {}
        task = {'id': 7, 'status': 'failed', 'error': {'type': 'task_failed'}}
        with patch('regression_plugin_lifecycle.request', return_value=task):
            wait_task(suite, row, 7, 'failed', 'broken_upgrade')
        self.assertEqual(row['assertions']['broken_upgrade_task'], 'passed')
        self.assertEqual(row['plugin_tasks'][0]['status'], 'failed')

    def test_live_worker_is_a_cleanup_failure_but_reused_pid_is_not(self):
        suite = SimpleNamespace(timeout=lambda seconds: 0)
        with patch('regression_plugin_lifecycle.process_identity', return_value='same-start'):
            with self.assertRaisesRegex(ValueError, 'worker remains'):
                workers_stopped(suite, {'100': 'same-start'})
        for identity in (None, 'new-start'):
            with patch('regression_plugin_lifecycle.process_identity', return_value=identity):
                workers_stopped(suite, {'100': 'same-start'})

    def test_unfinished_task_cannot_be_accepted(self):
        suite = SimpleNamespace(timeout=lambda seconds: 0)
        with patch('regression_plugin_lifecycle.request', Mock(return_value={'id': 7, 'status': 'running'})):
            with self.assertRaisesRegex(TimeoutError, 'did not finish'):
                wait_task(suite, {}, 7, 'succeeded', 'install')


if __name__ == '__main__':
    unittest.main()
