"""Optional resource lifecycle scenarios against the authenticated Workspace APIs."""

import copy
import json
from pathlib import Path
import sys
import tempfile
from uuid import uuid4

from regression_coverage import checked
from regression_local_cases import ScenarioUnavailable, api, require
from regression_suite import resolve

GROUP = 'resources'
CASE_NAMES = {'auth_revocation', 'agent_direct_execution', 'retrieval_delete_visibility'}


def add_cases(profile):
    resources = {item['id']: item for item in profile['resources']}
    base = copy.deepcopy(resources['empty_knowledge_base'])
    base.update(id='resource_knowledge_base')
    base['body']['name'] = 'regression document lifecycle'
    base.pop('documents', None)
    profile['resources'].append(base)
    for name, stage, expected in (
        ('auth_revocation', 'auth', 'LANGBOT_AUTH_REVOCATION_OK'),
        ('agent_direct_execution', 'agent', 'LANGBOT_CHAT_OK'),
        ('retrieval_delete_visibility', 'retrieval', 'LANGBOT_DOCUMENT_DELETE_OK'),
    ):
        profile['cases'].append({'name': name, 'scenario': name, 'stage': stage, 'expect': expected})


def data(suite, method, path, body=None, *, headers=None):
    status, response = api(suite, method, path, body, headers=headers)
    require(
        status == 200 and isinstance(response, dict) and response.get('code') == 0,
        f'{method} {path} did not return a successful response (HTTP {status})',
    )
    return response.get('data', {})


def journal(suite, row):
    row.setdefault('resource_journal', f'resource-case-{uuid4().hex}.json')
    suite.write(
        row['resource_journal'],
        {
            'workspace_uuid': suite.variables['workspace_uuid'],
            'resources': row.get('owned_resources', []),
            'cleanup_errors': row.get('cleanup_errors', []),
        },
    )


def cleanup(suite, row, assertion, action):
    original = sys.exc_info()[1]
    try:
        checked(row, assertion, action)
    except Exception as exc:
        message = f'{type(exc).__name__}: {exc}'
        for secret in suite.secrets:
            message = message.replace(secret, '[REDACTED]')
        row.setdefault('cleanup_errors', []).append(message)
        if original is None:
            raise
    finally:
        journal(suite, row)


def auth_revocation(suite, case, row):
    token = suite.env.get('LANGBOT_QA_USER_TOKEN')
    if not token:
        raise ScenarioUnavailable('auth.revocation requires LANGBOT_QA_USER_TOKEN with api_key.manage')
    if token not in suite.secrets:
        suite.secrets.append(token)
    manager = {'Authorization': 'Bearer ' + token}
    name = 'qa-revoke-' + uuid4().hex
    owned = {'kind': 'api-key', 'name': name, 'state': 'creating'}
    row.setdefault('owned_resources', []).append(owned)
    journal(suite, row)

    def revoke_owned():
        if 'id' not in owned:
            keys = data(suite, 'GET', '/api/v1/apikeys', headers=manager)['keys']
            matches = [key for key in keys if key.get('name') == name]
            require(len(matches) == 1, 'Created key identity is unresolved; inspect the resource journal')
            owned['id'] = matches[0]['id']
            journal(suite, row)
        path = f'/api/v1/apikeys/{owned["id"]}'
        key = data(suite, 'GET', path, headers=manager)['key']
        if key['status'] != 'revoked':
            data(suite, 'DELETE', path, headers=manager)
            key = data(suite, 'GET', path, headers=manager)['key']
        require(key['status'] == 'revoked', 'Owned credential remains active after cleanup')
        owned['state'] = 'revoked'

    try:
        created = data(suite, 'POST', '/api/v1/apikeys', {'name': name, 'scopes': ['resource.view']}, headers=manager)[
            'key'
        ]
        owned.update(id=created['id'], uuid=created['uuid'], state='active')
        journal(suite, row)
        secret = created['key']
        require(isinstance(secret, str) and bool(secret), 'Key creation did not return its one-time secret')
        suite.secrets.append(secret)
        child = {'X-API-Key': secret}
        identity = data(suite, 'GET', '/api/v1/system/context', headers=child)
        checked(
            row,
            'credential_active',
            lambda: require(
                identity.get('workspace_uuid') == suite.variables['workspace_uuid']
                and identity.get('api_key_id') == owned['uuid'],
                'New credential did not authenticate as its own Workspace key',
            ),
        )
        data(suite, 'GET', '/api/v1/pipelines', headers=child)
        data(suite, 'DELETE', f'/api/v1/apikeys/{owned["id"]}', headers=manager)
        status, response = api(suite, 'GET', '/api/v1/pipelines', headers=child)
        checked(
            row,
            'credential_revoked',
            lambda: require(
                status == 401 and isinstance(response, dict) and response.get('code') != 0,
                'Revoked credential still authorizes resource access',
            ),
        )
        key = data(suite, 'GET', f'/api/v1/apikeys/{owned["id"]}', headers=manager)['key']
        checked(
            row,
            'key_status',
            lambda: require(
                key.get('status') == 'revoked' and key.get('secret_available') is False and 'key' not in key,
                'Revoked key readback has incorrect status or exposes its secret',
            ),
        )
        return {'result': case['expect'], 'key_id': owned['id'], 'status': 'revoked'}
    finally:
        cleanup(suite, row, 'key_cleanup', revoke_owned)


def agent_direct_execution(suite, case, row):
    template = next(item for item in suite.profile['resources'] if item['id'] == 'chat_pipeline')
    config = resolve(copy.deepcopy(template['body']['config']['ai']), suite.variables)
    name = 'qa-agent-' + uuid4().hex
    conversation = 'qa-direct-' + uuid4().hex
    owned = {'kind': 'agent', 'name': name, 'state': 'creating'}
    row.setdefault('owned_resources', []).append(owned)
    journal(suite, row)

    def delete_owned():
        if 'uuid' not in owned:
            agents = data(suite, 'GET', '/api/v1/agents')['agents']
            matches = [agent for agent in agents if agent.get('name') == name and agent.get('kind') == 'agent']
            require(len(matches) == 1, 'Created Agent identity is unresolved; inspect the resource journal')
            owned['uuid'] = matches[0]['uuid']
            journal(suite, row)
        path = f'/api/v1/agents/{owned["uuid"]}'
        status, _ = api(suite, 'GET', path)
        if status != 404:
            require(status == 200, 'Cannot read owned Agent before cleanup')
            data(suite, 'DELETE', path)
        status, _ = api(suite, 'GET', path)
        require(status == 404, 'Owned Agent remains visible after cleanup')
        owned['state'] = 'deleted'

    try:
        created = data(suite, 'POST', '/api/v1/agents', {'name': name, 'kind': 'agent', 'config': config})
        owned.update(uuid=created['uuid'], state='created')
        journal(suite, row)
        path = f'/api/v1/agents/{owned["uuid"]}'
        reply = data(
            suite, 'POST', path + '/debug', {'text': 'Run the direct Agent scenario', 'conversation_id': conversation}
        )
        runs = data(suite, 'GET', path + '/runs')['items']
        matches = [run for run in runs if run.get('conversation_id') == conversation]
        require(len(matches) == 1, 'Direct Agent request did not produce exactly one matching Run')
        run = matches[0]
        row.setdefault('scenario_runs', []).append(
            {
                'run_id': run['run_id'],
                'conversation_id': conversation,
                'expected_status': 'completed',
                'after_id': row['after_id'],
            }
        )
        checked(
            row,
            'agent_terminal',
            lambda: require(
                run.get('status') == 'completed' and bool(run.get('finished_at')),
                'Direct Agent Run did not reach completed status',
            ),
        )
        checked(
            row,
            'agent_response',
            lambda: require(
                reply.get('conversation_id') == conversation and case['expect'] in reply.get('final_text', ''),
                'Direct Agent returned the wrong conversation or business reply',
            ),
        )
        events = data(suite, 'GET', path + f'/runs/{run["run_id"]}/events')
        checked(
            row,
            'agent_events',
            lambda: require(
                events.get('run', {}).get('run_id') == run['run_id']
                and any(
                    event.get('type') == 'run.completed' and event.get('run_id') == run['run_id']
                    for event in events.get('items', [])
                ),
                'Direct Agent completion event is missing',
            ),
        )
        return {'result': reply['final_text'], 'run_id': run['run_id'], 'conversation_id': conversation}
    finally:
        cleanup(suite, row, 'agent_cleanup', delete_owned)


def retrieval_delete_visibility(suite, case, row):
    kb_uuid = suite.variables['resource_knowledge_base']
    path = f'/api/v1/knowledge/bases/{kb_uuid}'
    before = {item['uuid'] for item in data(suite, 'GET', path + '/files')['files']}
    owned = {'kind': 'knowledge-files', 'knowledge_base_uuid': kb_uuid, 'files': [], 'state': 'ingesting'}
    row.setdefault('owned_resources', []).append(owned)
    journal(suite, row)

    def files():
        return [item for item in data(suite, 'GET', path + '/files')['files'] if item['uuid'] not in before]

    def cleanup_documents():
        remaining = files()
        owned['files'] = [{'uuid': item['uuid'], 'status': item['status']} for item in remaining]
        journal(suite, row)
        unresolved = [item['uuid'] for item in remaining if item['status'] in {'pending', 'processing', 'interrupted'}]
        for item in remaining:
            if item['uuid'] not in unresolved:
                data(suite, 'DELETE', path + '/files/' + item['uuid'])
        require(
            not unresolved, 'Document ingestion outcome is unresolved; retain the owned knowledge base for inspection'
        )
        require(not files(), 'Owned documents remain visible after cleanup')
        owned['state'] = 'deleted'

    def retrieve(query):
        found = data(suite, 'POST', path + '/retrieve', {'query': query, 'retrieval_settings': {'top_k': 10}})[
            'results'
        ]
        require(
            isinstance(found, list)
            and all(
                isinstance(item, dict)
                and isinstance(item.get('metadata'), dict)
                and isinstance(item.get('content'), list)
                for item in found
            ),
            'Malformed retrieval response',
        )
        return found

    def contains(found, document, marker):
        return any(
            item.get('metadata', {}).get('file_id') == document['engine_document_id']
            and marker in json.dumps(item.get('content', []), ensure_ascii=False)
            for item in found
        )

    try:
        documents, markers = [], ['obsolete' + uuid4().hex, 'retained' + uuid4().hex]
        with tempfile.TemporaryDirectory(prefix='resource-documents-', dir=suite.output) as directory:
            for index, marker in enumerate(markers):
                document = Path(directory) / f'document-{index}.txt'
                document.write_text(f'Lifecycle fixture: {marker}. This is document {index}.\n')
                previous = {item['uuid'] for item in files()}
                suite.call(
                    [
                        'knowledge-base',
                        'ingest',
                        kb_uuid,
                        '--file',
                        str(document),
                        '--parser-plugin-id',
                        'langbot-team/GeneralParsers',
                        '--wait',
                    ]
                )
                added = [item for item in files() if item['uuid'] not in previous]
                require(
                    len(added) == 1 and added[0].get('status') == 'completed',
                    'Document ingestion did not create exactly one completed file',
                )
                documents.append(added[0])
                owned['files'].append({'uuid': added[0]['uuid'], 'status': added[0]['status']})
                journal(suite, row)
        initial = retrieve(' '.join(markers))
        checked(
            row,
            'retrieval_initial',
            lambda: require(
                all(contains(initial, document, marker) for document, marker in zip(documents, markers)),
                'Both fixture documents must be independently retrievable before deletion',
            ),
        )
        data(suite, 'DELETE', path + '/files/' + documents[0]['uuid'])
        after = retrieve(' '.join(markers))
        checked(
            row,
            'retrieval_deleted',
            lambda: require(
                all(
                    item.get('metadata', {}).get('file_id') != documents[0]['engine_document_id']
                    and markers[0] not in json.dumps(item, ensure_ascii=False)
                    for item in after
                )
                and documents[0]['uuid'] not in {item['uuid'] for item in files()},
                'Deleted document remains visible in retrieval or the file list',
            ),
        )
        checked(
            row,
            'retrieval_control',
            lambda: require(
                contains(after, documents[1], markers[1]),
                'Deleting one document removed the surviving control document',
            ),
        )
        return {
            'result': case['expect'],
            'deleted_document_id': documents[0]['uuid'],
            'control_document_id': documents[1]['uuid'],
        }
    finally:
        cleanup(suite, row, 'document_cleanup', cleanup_documents)


def run_case(suite, case, row):
    actions = {
        'auth_revocation': auth_revocation,
        'agent_direct_execution': agent_direct_execution,
        'retrieval_delete_visibility': retrieval_delete_visibility,
    }
    return actions[case['scenario']](suite, case, row)
