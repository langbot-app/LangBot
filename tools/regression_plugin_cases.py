"""Local plugin business checks through signed Bot ingress and the Page API."""

from contextlib import closing
import copy
import json
from pathlib import Path
from uuid import uuid4

from regression_coverage import checked
from regression_lifecycle_cases import ledger
from regression_local_cases import api, require
from regression_resource_cases import cleanup, journal
from regression_smoke import check_mock_requests, signed_headers
from regression_suite import resolve

GROUP = 'plugins'
CASE_NAMES = {'plugins.command_version', 'plugins.faq_crud'}
COMMAND_PLUGINS = [
    {'author': 'langbot-team', 'name': name}
    for name in ('LocalAgent', 'LangRAG', 'GeneralParsers', 'EssentialCommands')
]
FAQ_API = '/api/v1/plugins/RockChinQ/FAQManager/page-api'


def add_cases(profile):
    pipeline = copy.deepcopy(next(item for item in profile['resources'] if item['id'] == 'chat_pipeline'))
    pipeline['id'] = 'plugin_command_pipeline'
    pipeline['body']['name'] = 'regression plugin commands'
    pipeline['body']['extensions_preferences'] = {
        'enable_all_plugins': False,
        'plugins': copy.deepcopy(COMMAND_PLUGINS),
    }
    profile['resources'].append(pipeline)
    for name, expected in (
        ('plugins.command_version', 'LANGBOT_PLUGIN_COMMAND_OK'),
        ('plugins.faq_crud', 'LANGBOT_PLUGIN_FAQ_OK'),
    ):
        profile['cases'].append({'name': name, 'scenario': name, 'stage': 'plugins', 'expect': expected})


def data(suite, method, path, body=None, *, headers=None):
    status, response = api(suite, method, path, body, headers=headers)
    require(
        status == 200 and isinstance(response, dict) and response.get('code') == 0,
        f'{method} {path} did not return a successful response (HTTP {status})',
    )
    result = response.get('data')
    if method == 'DELETE' and result is None:
        return {}
    require(isinstance(result, dict), f'{method} {path} returned malformed data')
    return result


def command_version(suite, case, row):
    pipeline = data(suite, 'GET', f'/api/v1/pipelines/{suite.variables["plugin_command_pipeline"]}')['pipeline']
    preferences = pipeline.get('extensions_preferences', {})
    checked(
        row,
        'command_plugin_bindings',
        lambda: require(
            preferences.get('enable_all_plugins') is False and preferences.get('plugins') == COMMAND_PLUGINS,
            'Command pipeline must bind only the three base plugins and EssentialCommands',
        ),
    )
    version = data(suite, 'GET', '/api/v1/system/info').get('version')
    require(isinstance(version, str) and bool(version), 'Core did not report its version')
    records = Path(suite.path(suite.profile['smoke']['mock_records']))
    require(records.is_file(), 'Command model-call evidence requires the dedicated mock recording file')
    body = resolve(
        copy.deepcopy(next(item['body'] for item in suite.profile['resources'] if item['id'] == 'chat_bot')),
        suite.variables,
    )
    body['name'] = 'qa-plugin-command-' + uuid4().hex
    body['adapter_config']['default_session_type'] = 'person'
    body['event_bindings'] = [
        {
            'event_pattern': 'message.received',
            'target_type': 'pipeline',
            'target_uuid': suite.variables['plugin_command_pipeline'],
            'enabled': True,
            'filters': [],
        }
    ]
    body['plugin_processors'] = []
    owned = {'kind': 'bot', 'name': body['name'], 'state': 'creating'}
    row.setdefault('owned_resources', []).append(owned)
    journal(suite, row)

    def delete_bot():
        if 'uuid' not in owned:
            bots = data(suite, 'GET', '/api/v1/platform/bots')['bots']
            matches = [bot for bot in bots if bot.get('name') == owned['name']]
            require(len(matches) == 1, 'Created command Bot identity is unresolved; inspect the resource journal')
            owned['uuid'] = matches[0]['uuid']
            journal(suite, row)
        path = f'/api/v1/platform/bots/{owned["uuid"]}'
        status, response = api(suite, 'GET', path)
        if status != 404:
            require(
                status == 200
                and response.get('code') == 0
                and response.get('data', {}).get('bot', {}).get('name') == owned['name'],
                'Cannot confirm ownership of the command Bot before cleanup',
            )
            data(suite, 'DELETE', path)
        status, _ = api(suite, 'GET', path)
        require(status == 404, 'Command Bot remains visible after cleanup')
        owned['state'] = 'deleted'

    try:
        created = data(suite, 'POST', '/api/v1/platform/bots', body)
        owned.update(uuid=created['uuid'], state='created')
        journal(suite, row)
        session = 'qa-plugin-version-' + uuid4().hex
        payload = {
            'session_id': session,
            'session_type': 'person',
            'message': [{'type': 'Plain', 'text': '!version'}],
        }
        offset = records.stat().st_size
        reply = data(
            suite,
            'POST',
            f'/bots/{owned["uuid"]}/sync',
            payload,
            headers=signed_headers(json.dumps(payload).encode(), body['adapter_config']['inbound_secret']),
        )
        row['command_response'] = reply
        parts = reply.get('message')
        checked(
            row,
            'command_version',
            lambda: require(
                reply.get('session_id') == session
                and bool(reply.get('reply_to'))
                and isinstance(parts, list)
                and all(isinstance(part, dict) and part.get('type') == 'Plain' for part in parts)
                and ''.join(part.get('text', '') for part in parts) == f'[bot] LangBot Version: {version}',
                'Version command did not return the exact Core version in the originating session',
            ),
        )
        with closing(ledger(suite)) as connection:
            count = connection.execute(
                'SELECT COUNT(*) FROM agent_run WHERE workspace_id=? AND bot_id=? AND id>?',
                (suite.variables['workspace_uuid'], owned['uuid'], row['after_id']),
            ).fetchone()[0]
        checked(row, 'command_no_run', lambda: require(count == 0, 'Version command unexpectedly created an AgentRun'))
        checked(
            row,
            'command_no_model',
            lambda: check_mock_requests(records, offset, [], timeout=suite.timeout(3)),
        )
        return {'result': case['expect'], 'version': version, 'agent_runs': count, 'model_requests': 0}
    finally:
        cleanup(suite, row, 'command_bot_cleanup', delete_bot)


def faq_crud(suite, case, row):
    def page(method, endpoint, body=None):
        return data(
            suite, 'POST', FAQ_API, {'page_id': 'manager', 'endpoint': endpoint, 'method': method, 'body': body}
        )

    def entries():
        values = page('GET', '/entries').get('entries')
        require(
            isinstance(values, list) and all(isinstance(item, dict) and item.get('id') for item in values),
            'FAQ entries response is malformed',
        )
        return values

    previous = {item['id'] for item in entries()}
    marker = 'qa-faq-' + uuid4().hex
    question, before, after = marker + '-question', marker + '-before', marker + '-after'
    owned = {'kind': 'faq-entry', 'question': question, 'state': 'creating'}
    row.setdefault('owned_resources', []).append(owned)
    journal(suite, row)

    def expect_entry(values, answer):
        expected = {'id': owned['id'], 'question': question, 'answer': answer}
        require(values == [expected], 'FAQ content or entry identity differs from the submitted value')

    def delete_entry():
        current = entries()
        if 'id' not in owned:
            matches = [item for item in current if item.get('question') == question and item['id'] not in previous]
            require(len(matches) <= 1, 'Created FAQ identity is ambiguous; inspect the resource journal')
            if not matches:
                owned['state'] = 'absent'
                return
            owned['id'] = matches[0]['id']
            journal(suite, row)
        require(owned['id'] not in previous, 'Refusing to delete a pre-existing FAQ entry')
        matches = [item for item in current if item['id'] == owned['id']]
        if matches:
            require(
                len(matches) == 1 and matches[0].get('question') == question, 'FAQ ownership changed before cleanup'
            )
            deleted = page('DELETE', '/entries', {'id': owned['id']})
            require(deleted.get('deleted') == owned['id'], 'FAQ deletion returned a different entry ID')
        require(not any(item['id'] == owned['id'] for item in entries()), 'Deleted FAQ remains visible')
        require(page('POST', '/search', {'query': marker}).get('results') == [], 'Deleted FAQ remains searchable')
        owned['state'] = 'deleted'

    try:
        created = page('POST', '/entries', {'question': question, 'answer': before}).get('entry')
        require(isinstance(created, dict) and bool(created.get('id')), 'FAQ creation did not return an entry ID')
        owned.update(id=created['id'], state='created')
        journal(suite, row)
        require(owned['id'] not in previous, 'FAQ creation reused a pre-existing entry ID')
        checked(row, 'faq_create', lambda: expect_entry([created], before))
        checked(
            row, 'faq_read', lambda: expect_entry([item for item in entries() if item['id'] == owned['id']], before)
        )
        checked(
            row, 'faq_search', lambda: expect_entry(page('POST', '/search', {'query': before}).get('results'), before)
        )
        updated = page('PUT', '/entries', {'id': owned['id'], 'question': question, 'answer': after}).get('entry')
        checked(row, 'faq_update', lambda: expect_entry([updated], after))
        checked(
            row,
            'faq_update_read',
            lambda: expect_entry([item for item in entries() if item['id'] == owned['id']], after),
        )
        checked(
            row,
            'faq_update_search',
            lambda: expect_entry(page('POST', '/search', {'query': after}).get('results'), after),
        )
        checked(
            row,
            'faq_old_answer_absent',
            lambda: require(
                page('POST', '/search', {'query': before}).get('results') == [], 'FAQ search returned stale content'
            ),
        )
        checked(row, 'faq_delete', delete_entry)
        return {'result': case['expect'], 'entry_id': owned['id'], 'deleted': True}
    finally:
        if owned['state'] != 'deleted':
            cleanup(suite, row, 'faq_cleanup', delete_entry)
        else:
            journal(suite, row)


def run_case(suite, case, row):
    require(case['scenario'] in CASE_NAMES, 'Unknown plugin scenario')
    return (command_version if case['scenario'] == 'plugins.command_version' else faq_crud)(suite, case, row)
