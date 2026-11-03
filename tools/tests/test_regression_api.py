"""Challenge API job oracles and replay/cleanup boundaries without a running Core."""

from collections import Counter
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from tools.regression.regression_api_cases import run_case
from tools.regression.regression_api_checks import owned_resource, request
from tools.regression.regression_api_resources import _expect_rejection
from tools.entrypoints.regression_ci import suite_profile
from tools.regression.regression_local_cases import DEFAULT_GROUPS
from tools.regression.regression_scenarios import expanded_profile
from tools.entrypoints.regression_suite import Suite, validate


class ApiContractTests(unittest.TestCase):
    def test_replay_and_job_isolation(self):
        first, _ = suite_profile('api', 'run-a', api_seed=20261028)
        replay, _ = suite_profile('api', 'run-b', api_seed=20261028)
        other, _ = suite_profile('api', 'run-c', api_seed=2)
        validate(first)
        self.assertEqual(first['cases'], replay['cases'])
        self.assertNotEqual(first['cases'], other['cases'])
        half = len(first['cases']) // 2
        fixed, shuffled = first['cases'][:half], first['cases'][half:]
        self.assertEqual(Counter(c['scenario'] for c in fixed), Counter(c['scenario'] for c in shuffled))
        self.assertEqual(set(Counter(c['scenario'] for c in fixed).values()), {1})
        self.assertEqual(first['resources'], [])
        self.assertNotIn('api', DEFAULT_GROUPS)
        daily = expanded_profile(DEFAULT_GROUPS)
        self.assertFalse(any(c.get('scenario', '').startswith('api_') for c in daily['cases']))
        with self.assertRaisesRegex(ValueError, 'dedicated suite'):
            expanded_profile(['api'])

    def test_http_success_cannot_hide_business_failure_or_wrong_status(self):
        for actual in ((200, {'code': -1}), (201, {'code': 0}), (400, {'code': 0}), (400, {})):
            row = {}
            with self.subTest(actual=actual), patch('tools.regression.regression_api_checks.api', return_value=actual):
                with self.assertRaises(ValueError):
                    request(None, row, 'GET', '/api/test', expected=400 if actual[0] == 400 else 200)
                self.assertEqual(row['assertions']['http_1'], 'failed')
                self.assertEqual(row['http_steps'][0]['status'], actual[0])

    def test_late_failure_cannot_mark_the_api_chain_passed(self):
        from types import SimpleNamespace

        suite = SimpleNamespace(profile={'vars': {'api_seed': 1}})
        row = {}
        with patch(
            'tools.regression.regression_api_cases.credentials_case', side_effect=ValueError('Revoked key still works')
        ):
            with self.assertRaisesRegex(ValueError, 'Revoked key'):
                run_case(suite, {'scenario': 'api_credentials', 'expect': 'OK'}, row)
        self.assertEqual(row['assertions']['api_chain'], 'failed')

    def test_rejection_keeps_http_failure_when_state_check_also_fails(self):
        row = {}

        def verify():
            row['state_checked'] = True
            raise ValueError('Stored state changed')

        with patch(
            'tools.regression.regression_api_resources.request', side_effect=ValueError('Expected 400, got 200')
        ):
            with self.assertRaisesRegex(ValueError, 'Expected 400, got 200'):
                _expect_rejection(None, row, 'PUT', '/api/test', {}, expected=400, headers={}, verify=verify)
        self.assertTrue(row['state_checked'])

    def test_lost_create_response_cleans_only_exact_owned_resource(self):
        for changed in (False, True):
            with self.subTest(changed=changed), tempfile.TemporaryDirectory() as directory:
                suite = Suite(
                    {'version': 1, 'cli': {'config': 'unused'}, 'cases': [], 'vars': {'workspace_uuid': 'test'}},
                    Path(directory) / 'profile.json',
                    Path(directory),
                )
                row, calls = {}, []

                def api(suite, method, path, body=None, headers=None):
                    calls.append((method, path))
                    if method == 'POST':
                        raise TimeoutError('Lost response after create')
                    if path == '/collection':
                        return 200, {
                            'code': 0,
                            'data': {
                                'items': [{'name': 'qa-owned', 'uuid': 'owned'}, {'name': 'unrelated', 'uuid': 'other'}]
                            },
                        }
                    if calls[-2][0] == 'DELETE':
                        return 404, {'code': -1}
                    if method == 'GET':
                        return 200, {
                            'code': 0,
                            'data': {'item': {'name': 'unrelated' if changed else 'qa-owned', 'uuid': 'owned'}},
                        }
                    return 200, {'code': 0}

                with patch('tools.regression.regression_api_checks.api', side_effect=api):
                    with self.assertRaisesRegex(TimeoutError, 'Lost response'):
                        with owned_resource(
                            suite, row, '/collection', {'name': 'qa-owned'}, item_key='item', list_key='items'
                        ):
                            self.fail('Create timeout must not enter the contract body')
                deleted = [path for method, path in calls if method == 'DELETE']
                self.assertEqual(deleted, [] if changed else ['/collection/owned'])
                if changed:
                    self.assertTrue(row['cleanup_errors'])
                else:
                    self.assertEqual(row['owned_resources'][0]['state'], 'deleted')

    def test_invalid_key_side_effects_fail_and_revoke_only_the_owned_key(self):
        for status, invalid_field in ((200, 'scopes'), (400, 'scopes'), (200, 'expires_at'), (400, 'expires_at')):
            with self.subTest(status=status, field=invalid_field), tempfile.TemporaryDirectory() as directory:
                suite = Suite(
                    {
                        'version': 1,
                        'cli': {'config': 'unused'},
                        'cases': [],
                        'vars': {'workspace_uuid': 'test', 'api_seed': 1},
                    },
                    Path(directory) / 'profile.json',
                    Path(directory),
                    env={'LANGBOT_QA_USER_TOKEN': 'manager-secret'},
                )
                other = {'id': 1, 'name': 'qa-api-other-key', 'status': 'active', 'secret_available': False}
                keys, row, deleted = {1: dict(other)}, {}, []

                def api(suite, method, path, body=None, headers=None):
                    if path == '/api/v1/pipelines':
                        return 401, {'code': -1}
                    if path == '/api/v1/apikeys':
                        if method == 'GET':
                            return 200, {'code': 0, 'data': {'keys': [dict(key) for key in keys.values()]}}
                        self.assertEqual(method, 'POST')
                        if invalid_field not in body:
                            return 400, {'code': -1}
                        keys[7] = {'id': 7, 'name': body['name'], 'status': 'active', 'secret_available': False}
                        return status, {'code': 0 if status == 200 else -1, 'data': {'key': dict(keys[7])}}
                    self.assertEqual(path, '/api/v1/apikeys/7')
                    if method == 'DELETE':
                        deleted.append(path)
                        keys[7]['status'] = 'revoked'
                        return 200, {'code': 0}
                    self.assertEqual(method, 'GET')
                    return 200, {'code': 0, 'data': {'key': dict(keys[7])}}

                error = 'expected HTTP 400' if status == 200 else 'Invalid key request changed key list'
                with (
                    patch('tools.regression.regression_api_checks.api', side_effect=api),
                    patch('tools.regression.regression_api_cases.unique_name', return_value='qa-api-owned-key'),
                    self.assertRaisesRegex(ValueError, error),
                ):
                    run_case(suite, {'scenario': 'api_credentials', 'expect': 'OK'}, row)
                self.assertEqual(row['assertions']['api_chain'], 'failed')
                self.assertEqual(row['assertions']['key_cleanup'], 'passed')
                self.assertFalse(row.get('cleanup_errors'))
                self.assertEqual(deleted, ['/api/v1/apikeys/7'])
                self.assertEqual(keys[7]['status'], 'revoked')
                self.assertEqual(keys[1], other)
                self.assertEqual(set(keys), {1, 7})
                self.assertEqual(row['owned_resources'][0]['state'], 'revoked')

    def test_readonly_pipeline_side_effects_fail_and_cleanup_preserves_other_resources(self):
        for status in (200, 403):
            with self.subTest(status=status), tempfile.TemporaryDirectory() as directory:
                suite = Suite(
                    {
                        'version': 1,
                        'cli': {'config': 'unused'},
                        'cases': [],
                        'vars': {'workspace_uuid': 'test', 'api_seed': 1},
                    },
                    Path(directory) / 'profile.json',
                    Path(directory),
                    env={'LANGBOT_QA_USER_TOKEN': 'manager-secret'},
                )
                other_key = {'id': 1, 'name': 'qa-api-other-key', 'status': 'active', 'secret_available': False}
                other_pipeline = {'uuid': 'other-pipeline', 'name': 'qa-api-other-pipeline'}
                keys, pipelines = {1: dict(other_key)}, {'other-pipeline': dict(other_pipeline)}
                row, deleted = {}, []

                def api(suite, method, path, body=None, headers=None):
                    if path == '/api/v1/apikeys':
                        if method == 'GET':
                            return 200, {'code': 0, 'data': {'keys': [dict(key) for key in keys.values()]}}
                        self.assertEqual(method, 'POST')
                        if body.get('scopes') == ['qa.invalid'] or 'expires_at' in body:
                            return 400, {'code': -1}
                        keys[7] = {'id': 7, 'name': body['name'], 'status': 'active', 'secret_available': False}
                        return 200, {'code': 0, 'data': {'key': {**keys[7], 'key': 'child-secret'}}}
                    if path == '/api/v1/apikeys/7':
                        if method == 'PUT':
                            keys[7]['name'] = body['name']
                            return 200, {'code': 0}
                        if method == 'DELETE':
                            deleted.append(path)
                            keys[7]['status'] = 'revoked'
                            return 200, {'code': 0}
                        self.assertEqual(method, 'GET')
                        return 200, {'code': 0, 'data': {'key': dict(keys[7])}}
                    if path == '/api/v1/pipelines':
                        if headers in ({}, {'Authorization': 'Bearer qa-invalid'}):
                            return 401, {'code': -1}
                        if method == 'GET':
                            return 200, {'code': 0, 'data': {'pipelines': [dict(item) for item in pipelines.values()]}}
                        self.assertEqual(method, 'POST')
                        self.assertEqual(headers, {'X-API-Key': 'child-secret'})
                        pipelines['owned-pipeline'] = {'uuid': 'owned-pipeline', 'name': body['name']}
                        return status, {'code': 0 if status == 200 else -1, 'data': {'uuid': 'owned-pipeline'}}
                    self.assertEqual(path, '/api/v1/pipelines/owned-pipeline')
                    if method == 'DELETE':
                        deleted.append(path)
                        del pipelines['owned-pipeline']
                        return 200, {'code': 0}
                    self.assertEqual(method, 'GET')
                    if 'owned-pipeline' not in pipelines:
                        return 404, {'code': -1}
                    return 200, {'code': 0, 'data': {'pipeline': dict(pipelines['owned-pipeline'])}}

                error = 'expected HTTP 403' if status == 200 else 'Read-only key changed resources'
                with (
                    patch('tools.regression.regression_api_checks.api', side_effect=api),
                    patch('tools.regression.regression_api_cases.unique_name', return_value='qa-api-owned-key'),
                    self.assertRaisesRegex(ValueError, error),
                ):
                    run_case(suite, {'scenario': 'api_credentials', 'expect': 'OK'}, row)
                self.assertEqual(row['assertions']['api_chain'], 'failed')
                self.assertEqual(row['assertions']['key_cleanup'], 'passed')
                self.assertEqual(row['assertions']['cleanup_pipeline_qa-api-owned-key'], 'passed')
                self.assertFalse(row.get('cleanup_errors'))
                self.assertEqual(deleted, ['/api/v1/pipelines/owned-pipeline', '/api/v1/apikeys/7'])
                self.assertEqual(keys[7]['status'], 'revoked')
                self.assertEqual(keys[1], other_key)
                self.assertEqual(set(keys), {1, 7})
                self.assertEqual(pipelines, {'other-pipeline': other_pipeline})
                self.assertEqual(
                    {item['kind']: item['state'] for item in row['owned_resources']},
                    {'api-key': 'revoked', 'pipeline': 'deleted'},
                )


if __name__ == '__main__':
    unittest.main()
