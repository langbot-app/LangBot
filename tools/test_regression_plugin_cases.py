"""Challenge plugin business oracles and cleanup without starting target services."""

import copy
import hashlib
import hmac
import json
from pathlib import Path
import sqlite3
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import regression_plugin_cases as plugins
from regression_scenarios import expanded_profile


def success(value=None):
    return 200, {'code': 0, 'data': value}


class PluginCasesTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.profile = expanded_profile()
        plugins.add_cases(self.profile)
        self.records = self.root / 'mock.jsonl'
        self.records.write_text(
            json.dumps({'path': '/v1/chat/completions', 'request': {'model': 'earlier'}, 'status': 200}) + '\n'
        )
        self.database = self.root / 'ledger.db'
        with sqlite3.connect(self.database) as connection:
            connection.execute('CREATE TABLE agent_run (id INTEGER, workspace_id TEXT, bot_id TEXT)')
        self.profile['smoke'].update(ledger_db=str(self.database), mock_records=str(self.records))
        self.suite = SimpleNamespace(
            profile=self.profile,
            variables={
                'workspace_uuid': 'workspace',
                'chat_pipeline': 'original-pipeline',
                'plugin_command_pipeline': 'isolated-pipeline',
                'group_secret': 'private-signing-secret',
            },
            secrets=['private-signing-secret'],
            env={},
            path=lambda value: value,
            timeout=lambda value: value,
            write=lambda name, value: (self.root / name).write_text(json.dumps(value)),
        )

    def case(self, scenario):
        return next(case for case in self.profile['cases'] if case.get('scenario') == scenario)

    def test_profile_adds_only_one_isolated_pipeline_and_two_scenarios(self):
        original = expanded_profile()
        profile = copy.deepcopy(original)
        plugins.add_cases(profile)
        self.assertEqual(profile['resources'][:-1], original['resources'])
        self.assertEqual(profile['cases'][:-2], original['cases'])
        pipeline = profile['resources'][-1]
        self.assertEqual(pipeline['id'], 'plugin_command_pipeline')
        self.assertEqual(
            pipeline['body']['extensions_preferences'],
            {
                'enable_all_plugins': False,
                'plugins': [
                    {'author': 'langbot-team', 'name': name}
                    for name in ('LocalAgent', 'LangRAG', 'GeneralParsers', 'EssentialCommands')
                ],
            },
        )
        self.assertEqual({case['scenario'] for case in profile['cases'][-2:]}, plugins.CASE_NAMES)
        self.assertTrue(all('http_group' not in case for case in profile['cases'][-2:]))

    def command_api(self, failure=None):
        state = {}

        def request(suite, method, path, body=None, headers=None):
            if path == '/api/v1/pipelines/isolated-pipeline':
                return success(
                    {
                        'pipeline': {
                            'extensions_preferences': {
                                'enable_all_plugins': failure == 'bindings',
                                'plugins': copy.deepcopy(plugins.COMMAND_PLUGINS),
                            }
                        }
                    }
                )
            if path == '/api/v1/system/info':
                return success({'version': '9.5.1'})
            if path == '/api/v1/platform/bots' and method == 'POST':
                self.assertEqual(body['event_bindings'][0]['target_uuid'], 'isolated-pipeline')
                self.assertEqual(body['plugin_processors'], [])
                self.assertEqual(body['adapter_config']['inbound_secret'], 'private-signing-secret')
                state.update(uuid='owned-bot', name=body['name'])
                return success({'uuid': 'owned-bot'})
            if path == '/bots/owned-bot/sync':
                self.assertEqual(body['session_type'], 'person')
                self.assertEqual(body['message'], [{'type': 'Plain', 'text': '!version'}])
                signed = headers['X-LB-Timestamp'].encode() + b'.' + json.dumps(body).encode()
                expected = 'sha256=' + hmac.new(b'private-signing-secret', signed, hashlib.sha256).hexdigest()
                self.assertEqual(headers['X-LB-Signature'], expected)
                if failure == 'run':
                    with sqlite3.connect(self.database) as connection:
                        connection.execute("INSERT INTO agent_run VALUES (1, 'workspace', 'owned-bot')")
                if failure == 'model':
                    with self.records.open('a') as stream:
                        stream.write(
                            json.dumps({'path': '/v1/chat/completions', 'request': {'model': 'wrong'}, 'status': 200})
                            + '\n'
                        )
                return success(
                    {
                        'session_id': 'wrong-session' if failure == 'session' else body['session_id'],
                        'reply_to': 'in_message',
                        'message': [
                            {
                                'type': 'Plain',
                                'text': '[bot] LangBot Version: ' + ('9.4.0' if failure == 'version' else '9.5.1'),
                            }
                        ],
                    }
                )
            if path == '/api/v1/platform/bots/owned-bot':
                if method == 'DELETE':
                    state['deleted'] = True
                    return success()  # The real Bot DELETE returns data=null.
                return (404, {'code': -1}) if state.get('deleted') else success({'bot': dict(state)})
            self.fail(f'Unexpected command API call: {method} {path}')

        return request, state

    def test_command_checks_signed_reply_without_requiring_a_run(self):
        request, state = self.command_api()
        row = {'after_id': 0}
        with patch.object(plugins, 'api', side_effect=request):
            result = plugins.run_case(self.suite, self.case('plugins.command_version'), row)
        self.assertEqual(
            result, {'result': 'LANGBOT_PLUGIN_COMMAND_OK', 'version': '9.5.1', 'agent_runs': 0, 'model_requests': 0}
        )
        self.assertTrue(state['deleted'])
        self.assertNotIn('scenario_runs', row)
        self.assertTrue(all(value == 'passed' for value in row['assertions'].values()))

    def test_command_rejects_bad_reply_model_calls_runs_and_plugin_leakage(self):
        for failure in ('version', 'session', 'model', 'run', 'bindings'):
            with self.subTest(failure=failure):
                with sqlite3.connect(self.database) as connection:
                    connection.execute('DELETE FROM agent_run')
                request, state = self.command_api(failure)
                row = {'after_id': 0}
                with patch.object(plugins, 'api', side_effect=request), self.assertRaises(ValueError):
                    plugins.run_case(self.suite, self.case('plugins.command_version'), row)
                if failure != 'bindings':
                    self.assertTrue(state['deleted'])
                self.assertIn('failed', row['assertions'].values())

    def faq_api(self, failure=None, cleanup_failure=False):
        unrelated = {'id': 'unrelated', 'question': 'Existing question', 'answer': 'Existing answer'}
        state = {'entries': [unrelated], 'created': 0, 'deletes': []}

        def request(suite, method, path, body=None, headers=None):
            self.assertEqual((method, path, body['page_id']), ('POST', plugins.FAQ_API, 'manager'))
            verb, endpoint, payload = body['method'], body['endpoint'], body['body']
            if (verb, endpoint) == ('GET', '/entries'):
                return success({'entries': copy.deepcopy(state['entries'])})
            if (verb, endpoint) == ('POST', '/entries'):
                state['created'] += 1
                entry = {'id': 'owned-faq', **payload}
                state['entries'].append(entry)
                state['original'] = copy.deepcopy(entry)
                if failure == 'lost_create':
                    raise ConnectionResetError('creation response lost')
                return success({'entry': copy.deepcopy(entry)})
            if (verb, endpoint) == ('PUT', '/entries'):
                self.assertEqual(payload['id'], 'owned-faq')
                if failure == 'update_error':
                    raise ValueError('primary update failure')
                if failure != 'stale_update':
                    state['entries'][1].update(payload)
                return success({'entry': copy.deepcopy(payload)})
            if (verb, endpoint) == ('POST', '/search'):
                rows = list(state['entries'])
                if failure == 'stale_search' and state['deletes']:
                    rows.append(state['original'])
                return success(
                    {
                        'results': copy.deepcopy(
                            [
                                item
                                for item in rows
                                if payload['query'] in item['question'] or payload['query'] in item['answer']
                            ]
                        )
                    }
                )
            if (verb, endpoint) == ('DELETE', '/entries'):
                self.assertEqual(payload, {'id': 'owned-faq'})
                if cleanup_failure:
                    raise RuntimeError('cleanup private-signing-secret failed')
                state['deletes'].append(payload['id'])
                state['entries'] = [item for item in state['entries'] if item['id'] != payload['id']]
                return success({'deleted': payload['id']})
            self.fail(f'Unexpected Page API call: {body}')

        return request, state

    def test_faq_crud_checks_content_and_removes_only_its_entry(self):
        request, state = self.faq_api()
        row = {}
        with patch.object(plugins, 'api', side_effect=request):
            result = plugins.run_case(self.suite, self.case('plugins.faq_crud'), row)
        self.assertEqual(result, {'result': 'LANGBOT_PLUGIN_FAQ_OK', 'entry_id': 'owned-faq', 'deleted': True})
        self.assertEqual(state['deletes'], ['owned-faq'])
        self.assertEqual([entry['id'] for entry in state['entries']], ['unrelated'])
        self.assertTrue(all(value == 'passed' for value in row['assertions'].values()))

    def test_faq_rejects_stale_readback_and_search(self):
        for failure, assertion in (('stale_update', 'faq_update_read'), ('stale_search', 'faq_delete')):
            with self.subTest(failure=failure):
                request, state = self.faq_api(failure)
                row = {}
                with patch.object(plugins, 'api', side_effect=request), self.assertRaises(ValueError):
                    plugins.run_case(self.suite, self.case('plugins.faq_crud'), row)
                self.assertEqual(row['assertions'][assertion], 'failed')
                self.assertEqual(state['deletes'], ['owned-faq'])
                self.assertEqual([entry['id'] for entry in state['entries']], ['unrelated'])

    def test_faq_lost_create_response_recovers_owned_id_without_retrying_creation(self):
        request, state = self.faq_api('lost_create')
        row = {}
        with patch.object(plugins, 'api', side_effect=request), self.assertRaises(ConnectionResetError):
            plugins.run_case(self.suite, self.case('plugins.faq_crud'), row)
        self.assertEqual(state['created'], 1)
        self.assertEqual(state['deletes'], ['owned-faq'])
        self.assertEqual(row['owned_resources'][0]['state'], 'deleted')

    def test_faq_preserves_original_error_and_redacts_cleanup_error(self):
        request, _ = self.faq_api('update_error', cleanup_failure=True)
        row = {}
        with (
            patch.object(plugins, 'api', side_effect=request),
            self.assertRaisesRegex(ValueError, 'primary update failure'),
        ):
            plugins.run_case(self.suite, self.case('plugins.faq_crud'), row)
        self.assertEqual(row['cleanup_errors'], ['RuntimeError: cleanup [REDACTED] failed'])
        evidence = (self.root / row['resource_journal']).read_text()
        self.assertNotIn('private-signing-secret', evidence)
        self.assertIn('owned-faq', evidence)


if __name__ == '__main__':
    unittest.main()
