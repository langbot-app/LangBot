"""Finite durable-state lifecycle against the runner's disposable Core and Runtime."""

import copy
import json
from pathlib import Path
import secrets
import time

from tools.regression.regression_api_checks import check, request
from tools.entrypoints.regression_coverage import checked
from tools.regression.regression_lifecycle_cases import after_id, completed
from tools.regression.regression_local_cases import require
from tools.regression.regression_smoke import reconcile_scenario_runs
from tools.entrypoints.regression_suite import Suite, contains_fields, resolve, validate
from tools.entrypoints.regression_traffic import group_request


def state_profile(profile):
    """Keep only the fixtures used by the dependent lifecycle chain."""
    profile = copy.deepcopy(profile)
    wanted = {
        'mock_provider',
        'embedding_provider',
        'chat_model',
        'unicode_model',
        'embedding_model',
        'empty_knowledge_base',
        'chat_pipeline',
        'chat_bot',
    }
    profile['resources'] = [item for item in profile['resources'] if item['id'] in wanted]
    require({item['id'] for item in profile['resources']} == wanted, 'State lifecycle fixtures are incomplete')
    profile.update(coverage_suite='state', cleanup='always')
    profile['cases'] = [
        {
            'name': 'durable_state_lifecycle',
            'stage': 'state',
            'expect': 'LANGBOT_CHAT_OK',
            'http_group': {
                'url': '${core_base_url}/bots/${chat_bot}/sync',
                'secret_env': 'LANGBOT_QA_GROUP_SECRET',
                'message': 'ai Run the durable state scenario',
            },
        }
    ]
    return profile


def document_visible(results, document, marker):
    return any(
        item.get('metadata', {}).get('file_id') == document['engine_document_id']
        and marker in json.dumps(item.get('content', []), ensure_ascii=False)
        for item in results
    )


def document_absent(results, document, marker):
    return all(
        item.get('metadata', {}).get('file_id') != document['engine_document_id']
        and marker not in json.dumps(item, ensure_ascii=False)
        for item in results
    )


def run_state_checks(profile, profile_path, output, env, restart_owned, budget=300):
    """Exercise create/restart/update/restart/delete while retaining exact business evidence."""
    validate(profile)
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False, mode=0o700)
    started = time.monotonic()
    deadline = started + budget - 30
    suite = Suite(profile, profile_path, output, env)

    def timeout(maximum):
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise TimeoutError('State lifecycle exhausted its execution deadline')
        return min(maximum, remaining)

    suite.timeout = timeout
    suite.write('profile.json', profile)
    row = {'case': 'durable_state_lifecycle', 'stage': 'state', 'status': 'unknown', 'restarts': []}
    result = {'mode': 'state', 'cases': [row], 'errors': [], 'incomplete': [], 'phases': []}

    def restart(service, phase):
        receipt = restart_owned(service, timeout=timeout(60))
        check(
            row,
            phase + '_process_replaced',
            bool(receipt.get('old_pid')) and bool(receipt.get('new_pid')) and receipt['old_pid'] != receipt['new_pid'],
            'Owned restart did not replace its process',
        )
        row['restarts'].append({'phase': phase, **receipt})

    try:
        suite.prepare()
        row['after_id'] = after_id(suite)
        case = resolve(profile['cases'][0], suite.variables)
        pipeline_path = '/api/v1/pipelines/' + suite.variables['chat_pipeline']
        kb_path = '/api/v1/knowledge/bases/' + suite.variables['empty_knowledge_base']
        pipeline = request(suite, row, 'GET', pipeline_path)['pipeline']
        submitted = resolve(
            next(r for r in profile['resources'] if r['id'] == 'chat_pipeline')['body'], suite.variables
        )
        check(
            row,
            'created_configuration',
            contains_fields(pipeline, submitted),
            'Pipeline differs from created configuration',
        )
        expected_pipeline = {
            key: pipeline[key] for key in ('uuid', 'name', 'description', 'config', 'extensions_preferences')
        }

        def configuration(phase):
            current = request(suite, row, 'GET', pipeline_path)['pipeline']
            check(
                row,
                phase + '_configuration',
                contains_fields(current, expected_pipeline),
                'Persisted pipeline configuration changed',
            )

        def files():
            return request(suite, row, 'GET', kb_path + '/files')['files']

        def ingest(label, marker):
            previous = {item['uuid'] for item in files()}
            document = output / (label + '.txt')
            document.write_text(f'Durable lifecycle document {label}: {marker}.\n', encoding='utf-8')
            suite.call(
                [
                    'knowledge-base',
                    'ingest',
                    suite.variables['empty_knowledge_base'],
                    '--file',
                    str(document),
                    '--parser-plugin-id',
                    'langbot-team/GeneralParsers',
                    '--wait',
                ]
            )
            added = [item for item in files() if item['uuid'] not in previous]
            check(
                row,
                label + '_ingested',
                len(added) == 1 and added[0].get('status') == 'completed' and bool(added[0].get('engine_document_id')),
                'Expected exactly one completed document',
            )
            row.setdefault('documents', {})[label] = {
                'uuid': added[0]['uuid'],
                'engine_document_id': added[0]['engine_document_id'],
                'marker': marker,
            }
            return added[0]

        markers = {name: name + secrets.token_hex(16) for name in ('original', 'control', 'replacement')}
        documents = {name: ingest(name, markers[name]) for name in ('original', 'control')}
        session, previous, turn = 'qa-state-' + secrets.token_hex(16), 'none', 0

        def chat(phase):
            nonlocal previous, turn
            token = secrets.token_hex(16)
            after = after_id(suite)
            turn += 1
            checked(
                row,
                phase + '_chat_history',
                lambda: group_request(
                    case,
                    session,
                    'qa-state-member',
                    turn,
                    token,
                    previous,
                    suite.env,
                    timeout=timeout(30),
                ),
            )
            completed(suite, row, session, after)
            previous = token

        def retrieval(phase, *, updated=False):
            found = request(
                suite,
                row,
                'POST',
                kb_path + '/retrieve',
                {
                    'query': ' '.join(markers.values()),
                    'retrieval_settings': {'top_k': 10},
                },
            )['results']
            check(
                row,
                phase + '_retrieval_shape',
                isinstance(found, list)
                and all(
                    isinstance(item, dict)
                    and isinstance(item.get('metadata'), dict)
                    and isinstance(item.get('content'), list)
                    for item in found
                ),
                'Malformed retrieval response',
            )
            selected = ('replacement', 'control') if updated else ('original', 'control')
            check(
                row,
                phase + '_retrievable',
                all(document_visible(found, documents[name], markers[name]) for name in selected),
                'Persisted documents are missing or return incorrect content',
            )
            if updated:
                check(
                    row,
                    phase + '_obsolete_absent',
                    document_absent(found, documents['original'], markers['original'])
                    and documents['original']['uuid'] not in {item['uuid'] for item in files()},
                    'Replaced document is still visible through retrieval or file listing',
                )
            row.setdefault('retrievals', []).append({'phase': phase, 'results': found})

        chat('created')
        retrieval('created')
        for service in ('runtime', 'core'):
            restart(service, 'initial_' + service)
            configuration('after_' + service)
            chat('after_' + service)
            retrieval('after_' + service)

        updated = copy.deepcopy(expected_pipeline['config'])
        updated['ai']['runner_config']['plugin:langbot-team/LocalAgent/default']['model']['primary'] = suite.variables[
            'unicode_model'
        ]
        request(suite, row, 'PUT', pipeline_path, {'description': 'Updated durable state fixture', 'config': updated})
        expected_pipeline.update(description='Updated durable state fixture', config=updated)
        configuration('updated')
        case['expect'] = 'LANGBOT_UNICODE_OK'
        case['http_group']['message'] = 'ai 请原样处理：你好，世界 🌍'
        chat('updated')
        documents['replacement'] = ingest('replacement', markers['replacement'])
        request(suite, row, 'DELETE', kb_path + '/files/' + documents['original']['uuid'])
        retrieval('updated', updated=True)
        restart('core', 'updated_core')
        configuration('persisted_update')
        chat('persisted_update')
        retrieval('persisted_update', updated=True)
        for name in ('replacement', 'control'):
            request(suite, row, 'DELETE', kb_path + '/files/' + documents[name]['uuid'])
        check(row, 'documents_deleted', not files(), 'Deleted document metadata remains visible')
        found = request(
            suite,
            row,
            'POST',
            kb_path + '/retrieve',
            {
                'query': ' '.join(markers.values()),
                'retrieval_settings': {'top_k': 10},
            },
        )['results']
        check(row, 'deleted_retrieval_empty', found == [], 'Deleted knowledge content remains retrievable')
        reconcile_scenario_runs(suite, result, key='ledger_closeout')
        require(not result['errors'], 'Lifecycle run ledger did not reconcile')
        row['status'] = 'passed'
    except Exception as exc:
        row.update(status='unknown' if isinstance(exc, (TimeoutError, OSError)) else 'failed', error=str(exc))
        result['errors'].append('state lifecycle: ' + str(exc))
        if row['status'] == 'unknown':
            result['incomplete'].append(result['errors'][-1])
    finally:
        row['seconds'] = time.monotonic() - started
        suite.write('cases.json', result['cases'])
        # Keep a bounded cleanup window even when the business chain reaches its deadline.
        deadline = time.monotonic() + 30
        suite.finish(result)
        result.update(elapsed_seconds=time.monotonic() - started, case_count=1, requests=1)
        suite.write('summary.json', result)
    return result
