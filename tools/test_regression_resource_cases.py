"""Challenge public resource lifecycle oracles and their cleanup without starting services."""

import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from regression_local_cases import ScenarioUnavailable
from regression_resource_cases import run_case


def success(data=None):
    return 200, {'code': 0, 'data': data or {}}


class ResourceCasesTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.suite = SimpleNamespace(
            output=self.root,
            env={'LANGBOT_QA_USER_TOKEN': 'private-user-token'},
            secrets=[],
            variables={'workspace_uuid': 'workspace', 'resource_knowledge_base': 'owned-kb'},
            profile={
                'resources': [
                    {
                        'id': 'chat_pipeline',
                        'body': {'config': {'ai': {'runner': {'id': 'runner'}, 'runner_config': {'runner': {}}}}},
                    }
                ]
            },
            write=lambda name, value: (self.root / name).write_text(json.dumps(value)),
        )

    def test_missing_management_session_skips_without_creating_credentials(self):
        self.suite.env.clear()
        with patch('regression_resource_cases.api') as request, self.assertRaises(ScenarioUnavailable):
            run_case(self.suite, {'scenario': 'auth_revocation'}, {})
        request.assert_not_called()

    def test_revocation_rejects_still_authorized_key_and_never_persists_secrets(self):
        for stale_authorization in (False, True):
            with self.subTest(stale_authorization=stale_authorization):
                key = {'id': 7, 'uuid': 'managed-key', 'status': 'active', 'secret_available': False}
                row = {'after_id': 0}

                def request(suite, method, path, body=None, headers=None):
                    if method == 'POST':
                        return success({'key': {**key, 'key': 'private-child-secret', 'secret_available': True}})
                    if method == 'DELETE':
                        key['status'] = 'revoked'
                        return success()
                    if path == '/api/v1/system/context':
                        self.assertEqual(headers, {'X-API-Key': 'private-child-secret'})
                        return success({'workspace_uuid': 'workspace', 'api_key_id': 'managed-key'})
                    if path == '/api/v1/pipelines':
                        return (
                            success({'pipelines': []})
                            if key['status'] == 'active' or stale_authorization
                            else (401, {'code': -1})
                        )
                    return success({'key': key})

                with patch('regression_resource_cases.api', side_effect=request):
                    case = {'scenario': 'auth_revocation', 'expect': 'REVOKED'}
                    if stale_authorization:
                        with self.assertRaisesRegex(ValueError, 'still authorizes'):
                            run_case(self.suite, case, row)
                        self.assertEqual(row['assertions']['credential_revoked'], 'failed')
                    else:
                        self.assertEqual(run_case(self.suite, case, row)['status'], 'revoked')
                self.assertEqual(key['status'], 'revoked')
                self.assertEqual(row['assertions']['key_cleanup'], 'passed')
                evidence = json.dumps(row) + (self.root / row['resource_journal']).read_text()
                self.assertNotIn('private-child-secret', evidence)
                self.assertNotIn('private-user-token', evidence)

    def test_direct_agent_records_run_and_cleans_after_failed_public_event_oracle(self):
        for missing_event in (False, True):
            with self.subTest(missing_event=missing_event):
                state, row = {}, {'after_id': 12}

                def request(suite, method, path, body=None, headers=None):
                    if method == 'POST' and path == '/api/v1/agents':
                        state.update(uuid='own-agent', name=body['name'])
                        return success({'uuid': 'own-agent'})
                    if path.endswith('/debug'):
                        state['conversation'] = body['conversation_id']
                        return success({'conversation_id': state['conversation'], 'final_text': 'DIRECT_OK'})
                    run = {
                        'run_id': 'own-run',
                        'conversation_id': state.get('conversation'),
                        'status': 'completed',
                        'finished_at': 1,
                    }
                    if path.endswith('/runs'):
                        return success({'items': [run]})
                    if path.endswith('/events'):
                        return success(
                            {
                                'run': run,
                                'items': [] if missing_event else [{'type': 'run.completed', 'run_id': 'own-run'}],
                            }
                        )
                    if method == 'DELETE':
                        self.assertEqual(path, '/api/v1/agents/own-agent')
                        state['deleted'] = True
                        return success()
                    return (404, {'code': -1}) if state.get('deleted') else success({'agent': state})

                with patch('regression_resource_cases.api', side_effect=request):
                    case = {'scenario': 'agent_direct_execution', 'expect': 'DIRECT_OK'}
                    if missing_event:
                        with self.assertRaisesRegex(ValueError, 'completion event'):
                            run_case(self.suite, case, row)
                    else:
                        self.assertEqual(run_case(self.suite, case, row)['run_id'], 'own-run')
                self.assertEqual(
                    row['scenario_runs'],
                    [
                        {
                            'run_id': 'own-run',
                            'conversation_id': state['conversation'],
                            'after_id': 12,
                            'expected_status': 'completed',
                        }
                    ],
                )
                self.assertTrue(state['deleted'])
                self.assertEqual(row['assertions']['agent_cleanup'], 'passed')

    def test_unknown_agent_create_recovers_owned_identity_without_retrying_creation(self):
        calls, state, row = [], {}, {'after_id': 0}

        def request(suite, method, path, body=None, headers=None):
            calls.append((method, path))
            if method == 'POST':
                state.update(uuid='own-agent', name=body['name'], kind='agent')
                raise ConnectionResetError('creation response lost')
            if path == '/api/v1/agents':
                return success({'agents': [state, {'uuid': 'unrelated', 'name': 'other', 'kind': 'agent'}]})
            if method == 'DELETE':
                self.assertEqual(path, '/api/v1/agents/own-agent')
                state['deleted'] = True
                return success()
            return (404, {'code': -1}) if state.get('deleted') else success({'agent': state})

        with patch('regression_resource_cases.api', side_effect=request), self.assertRaises(ConnectionResetError):
            run_case(self.suite, {'scenario': 'agent_direct_execution', 'expect': 'OK'}, row)
        self.assertEqual(sum(method == 'POST' for method, _ in calls), 1)
        self.assertEqual(row['owned_resources'][0]['state'], 'deleted')

    def test_delete_requires_retrieval_absence_and_preserves_control_document(self):
        for stale_vectors in (False, True):
            with self.subTest(stale_vectors=stale_vectors):
                documents, row = [], {'after_id': 0}

                def ingest(args):
                    content = Path(args[args.index('--file') + 1]).read_text()
                    index = len(documents)
                    documents.append(
                        {
                            'uuid': f'file-{index}',
                            'engine_document_id': f'engine-{index}',
                            'status': 'completed',
                            'content': content,
                            'deleted': False,
                        }
                    )
                    return {}

                def request(suite, method, path, body=None, headers=None):
                    if method == 'DELETE':
                        target = next(document for document in documents if path.endswith('/' + document['uuid']))
                        target['deleted'] = True
                        return success()
                    if method == 'GET':
                        return success({'files': [document for document in documents if not document['deleted']]})
                    return success(
                        {
                            'results': [
                                {
                                    'metadata': {'file_id': document['engine_document_id']},
                                    'content': [{'type': 'text', 'text': document['content']}],
                                }
                                for document in documents
                                if not document['deleted'] or stale_vectors
                            ]
                        }
                    )

                self.suite.call = ingest
                with patch('regression_resource_cases.api', side_effect=request):
                    case = {'scenario': 'retrieval_delete_visibility', 'expect': 'DELETED'}
                    if stale_vectors:
                        with self.assertRaisesRegex(ValueError, 'remains visible'):
                            run_case(self.suite, case, row)
                        self.assertEqual(row['assertions']['retrieval_deleted'], 'failed')
                    else:
                        self.assertEqual(run_case(self.suite, case, row)['result'], 'DELETED')
                        self.assertEqual(row['assertions']['retrieval_control'], 'passed')
                self.assertTrue(all(document['deleted'] for document in documents))
                self.assertEqual(row['assertions']['document_cleanup'], 'passed')
                self.assertEqual(list(self.root.glob('resource-documents-*')), [])


if __name__ == '__main__':
    unittest.main()
