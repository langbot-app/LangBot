"""Keep CLI presentation flexible while rejecting wrong identity and false success."""

from pathlib import Path
from types import SimpleNamespace
import tempfile
import json
import unittest
from unittest.mock import Mock, patch

from tools.regression.regression_cli_cases import identity, invalid_credential, pipeline_roundtrip
from tools.entrypoints.regression_ci import suite_profile
from tools.entrypoints.regression_suite import Suite, validate


class CLICompatibilityTests(unittest.TestCase):
    def test_wrong_workspace_fails_even_when_cli_exits_successfully(self):
        suite = SimpleNamespace(
            call=Mock(side_effect=[{'version': 'future', 'new_field': True}, {'workspace_uuid': 'wrong'}]),
            variables={'workspace_uuid': 'expected'},
        )
        row = {}
        with self.assertRaisesRegex(ValueError, 'different Workspace'):
            identity(suite, row)
        self.assertEqual(row['assertions']['workspace_identity'], 'failed')

    def test_invalid_credential_must_have_nonzero_exit(self):
        suite = SimpleNamespace(
            connection={'credential_source': 'env:QA_KEY'},
            cli=['lbctl', '-o', 'json'],
            env={'QA_KEY': 'secret'},
            timeout=lambda value: value,
        )
        with patch(
            'tools.regression.regression_cli_cases.subprocess.run',
            return_value=SimpleNamespace(returncode=0, stdout='{}', stderr=''),
        ):
            with self.assertRaisesRegex(ValueError, 'success with an invalid credential'):
                invalid_credential(suite, {})

    def test_successful_cli_create_without_backend_state_fails(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            suite = Suite(
                {'cli': {'config': 'unused'}, 'cases': [], 'vars': {'workspace_uuid': 'test'}}, path / 'p.json', path
            )
            suite.call = Mock(return_value={'uuid': 'reported-but-not-created'})
            row = {}
            with (
                patch('tools.regression.regression_cli_cases.request', return_value={'pipelines': []}),
                patch(
                    'tools.regression.regression_api_checks.api',
                    return_value=(200, {'code': 0, 'data': {'pipelines': []}}),
                ),
            ):
                with self.assertRaisesRegex(ValueError, 'exactly one owned Pipeline'):
                    pipeline_roundtrip(suite, row)
            self.assertEqual(row['owned_resources'][0]['state'], 'absent')

    def test_zero_exit_does_not_hide_an_explicit_failure_envelope(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            suite = Suite({'cli': {'config': 'unused'}, 'cases': []}, path / 'p.json', path, env={})
            for response in (
                {'ok': False, 'data': {'requested_uuid': 'owned'}},
                {'error': {'type': 'failed'}, 'data': {'uuid': 'owned'}},
            ):
                process = SimpleNamespace(returncode=0, stdout=json.dumps(response), stderr='')
                with (
                    self.subTest(response=response),
                    patch('tools.entrypoints.regression_suite.subprocess.run', return_value=process),
                ):
                    with self.assertRaisesRegex(RuntimeError, 'failure response'):
                        suite.call(['pipeline', 'get', 'owned'])
            process = SimpleNamespace(
                returncode=0,
                stdout=json.dumps(
                    {'ok': True, 'new_field': 'allowed', 'data': {'pipeline': {'uuid': 'owned', 'extra': 1}}}
                ),
                stderr='',
            )
            with patch('tools.entrypoints.regression_suite.subprocess.run', return_value=process):
                self.assertEqual(suite.call(['pipeline', 'get', 'owned'])['pipeline']['uuid'], 'owned')

    def test_profile_is_finite_and_uses_no_shared_resources(self):
        profile, _ = suite_profile('cli', 'unit-test')
        validate(profile)
        self.assertEqual(profile['resources'], [])
        self.assertEqual(len(profile['cases']), 3)
        self.assertNotIn('execution', profile)
        smoke, _ = suite_profile('smoke', 'unit-test')
        self.assertFalse(any(case.get('scenario', '').startswith('cli.') for case in smoke['cases']))


if __name__ == '__main__':
    unittest.main()
