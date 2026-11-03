"""Finite API contracts: fixed first pass, then reproducibly shuffled independent chains."""

import json
import random

from tools.regression.regression_api_checks import (
    check,
    owned_resource,
    request,
    tracked_resource,
    unique_name,
    user_headers,
)
from tools.entrypoints.regression_coverage import checked
from tools.regression.regression_local_cases import require
from tools.regression.regression_resource_cases import cleanup, journal

CASE_NAMES = ('api_llm', 'api_embedding', 'api_rerank', 'api_pipeline', 'api_credentials', 'api_skills', 'api_mcp')


def add_cases(profile):
    require(profile.get('coverage_suite') == 'api', 'API contracts require their dedicated suite')
    shuffled = list(CASE_NAMES)
    seed = profile['vars']['api_seed']
    random.Random(seed).shuffle(shuffled)
    for phase, names in (('fixed', CASE_NAMES), ('shuffled', shuffled)):
        for name in names:
            profile['cases'].append(
                {'name': f'{phase}_{name}', 'scenario': name, 'stage': 'api', 'expect': 'API_CONTRACT_OK'}
            )
    profile['scenario_groups'] = ['api']


def model_case(suite, row, model_type):
    providers = '/api/v1/provider/providers'
    name, secret = unique_name(), unique_name()
    suite.secrets.append(secret)
    body = {
        'name': name,
        'requester': 'jina-rerank' if model_type == 'rerank' else 'openai-chat-completions',
        'base_url': suite.variables['mock_base_url'],
        'api_keys': [secret],
    }
    with owned_resource(suite, row, providers, body, item_key='provider', list_key='providers') as (path, uid):
        visible = request(suite, row, 'GET', path + '?include_secret=true')['provider']
        check(
            row,
            'provider_identity',
            visible['name'] == name and visible['api_keys'] == [secret],
            'Provider identity or secret changed',
        )
        redacted = request(suite, row, 'GET', path + '?include_secret=false')['provider']
        check(row, 'provider_redacted', secret not in json.dumps(redacted), 'Provider secret was disclosed')
        request(suite, row, 'GET', path + '?include_secret=invalid', expected=400)
        request(suite, row, 'PUT', path, {'name': name + '-updated'})
        updated = request(suite, row, 'GET', path + '?include_secret=true')['provider']
        check(
            row,
            'provider_update',
            updated['name'] == name + '-updated' and updated['api_keys'] == [secret],
            'Provider metadata update lost its secret',
        )
        collection = '/api/v1/provider/models/' + model_type
        model_name = unique_name()
        with owned_resource(
            suite, row, collection, {'name': model_name, 'provider_uuid': uid}, item_key='model', list_key='models'
        ) as (model_path, model_id):
            model = request(suite, row, 'GET', model_path)['model']
            check(
                row,
                'model_identity',
                model['name'] == model_name and model['provider_uuid'] == uid,
                'Model did not retain its provider binding',
            )
            items = request(suite, row, 'GET', collection + '?provider_uuid=' + uid)['models']
            check(row, 'model_list', [m['uuid'] for m in items] == [model_id], 'Provider model filter is incorrect')
            request(suite, row, 'PUT', model_path, {'name': model_name + '-updated'})
            model = request(suite, row, 'GET', model_path)['model']
            check(
                row,
                'model_update',
                model['name'] == model_name + '-updated' and model['provider_uuid'] == uid,
                'Model metadata update lost its binding',
            )
            request(suite, row, 'DELETE', path, expected=400)
            still = request(suite, row, 'GET', model_path)['model']
            check(row, 'rejected_delete_preserves_model', still == model, 'Rejected provider deletion mutated child')
            request(suite, row, 'GET', path)
        items = request(suite, row, 'GET', collection + '?provider_uuid=' + uid)['models']
        check(row, 'model_deleted_from_list', not items, 'Deleted model remains listed')


def pipeline_case(suite, row):
    collection, name = '/api/v1/pipelines', unique_name()
    with owned_resource(suite, row, collection, {'name': name}, item_key='pipeline', list_key='pipelines') as (
        path,
        uid,
    ):
        pipeline = request(suite, row, 'GET', path)['pipeline']
        check(
            row,
            'pipeline_identity',
            pipeline['name'] == name and pipeline['uuid'] == uid,
            'Pipeline creation readback differs',
        )
        items = request(suite, row, 'GET', collection)['pipelines']
        check(row, 'pipeline_list', sum(p['uuid'] == uid for p in items) == 1, 'Pipeline missing or duplicated')
        request(suite, row, 'PUT', path, {'name': name + '-updated', 'description': 'API contract 中文'})
        updated = request(suite, row, 'GET', path)['pipeline']
        check(
            row,
            'pipeline_update',
            updated['name'] == name + '-updated' and updated['description'] == 'API contract 中文',
            'Pipeline update readback differs',
        )
        bindings = dict(
            bound_plugins=[],
            bound_mcp_servers=[],
            bound_skills=[],
            enable_all_plugins=False,
            enable_all_mcp_servers=False,
            enable_all_skills=False,
        )
        request(suite, row, 'PUT', path + '/extensions', bindings)
        before = request(suite, row, 'GET', path + '/extensions')
        check(row, 'extension_readback', all(before[k] == v for k, v in bindings.items()), 'Extension bindings differ')
        for invalid in ({'enable_all_plugins': 'false'}, {'bound_skills': [42]}, {'bound_plugins': [{}]}):
            request(suite, row, 'PUT', path + '/extensions', invalid, expected=400)
            after = request(suite, row, 'GET', path + '/extensions')
            check(row, 'rejected_extension_' + next(iter(invalid)), after == before, 'Rejected binding changed state')
        for invalid in ({}, {'message': ''}, {'message': 42}):
            request(suite, row, 'POST', path + '/run', invalid, expected=400)
        after = request(suite, row, 'GET', path)['pipeline']
        check(row, 'invalid_run_preserves_config', after['config'] == updated['config'], 'Invalid run changed config')


def credentials_case(suite, row):
    manager, collection, name = user_headers(suite), '/api/v1/apikeys', unique_name()
    for headers in ({}, {'Authorization': 'Bearer qa-invalid'}):
        request(suite, row, 'GET', '/api/v1/pipelines', headers=headers, expected=401)
    owned = {'kind': 'api-key', 'name': name, 'state': 'creating'}
    row.setdefault('owned_resources', []).append(owned)
    journal(suite, row)

    def revoke():
        if 'id' not in owned:
            keys = request(suite, row, 'GET', collection, headers=manager)['keys']
            matches = [k for k in keys if k['name'] in (name, name + '-updated')]
            require(len(matches) <= 1, 'Ambiguous owned key')
            if not matches:
                owned['state'] = 'absent'
                return
            owned['id'] = matches[0]['id']
        path = collection + '/' + str(owned['id'])
        current = request(suite, row, 'GET', path, headers=manager)['key']
        require(current['name'] in (name, name + '-updated'), 'Key ownership changed')
        if current['status'] != 'revoked':
            request(suite, row, 'DELETE', path, headers=manager)
        current = request(suite, row, 'GET', path, headers=manager)['key']
        check(
            row,
            'revoked_readback',
            current['status'] == 'revoked' and current['secret_available'] is False and 'key' not in current,
            'Revoked key remains active or exposes its secret',
        )
        owned['state'] = 'revoked'

    try:
        before = request(suite, row, 'GET', collection, headers=manager)['keys']
        for invalid in ({'scopes': ['qa.invalid']}, {'expires_at': 'not-a-date'}):
            request(suite, row, 'POST', collection, {'name': name, **invalid}, headers=manager, expected=400)
            after = request(suite, row, 'GET', collection, headers=manager)['keys']
            check(row, 'invalid_key_not_created', before == after, 'Invalid key request changed key list')
        key = request(suite, row, 'POST', collection, {'name': name, 'scopes': ['resource.view']}, headers=manager)[
            'key'
        ]
        owned.update(id=key['id'], state='active')
        journal(suite, row)
        secret = key['key']
        suite.secrets.append(secret)
        child = {'X-API-Key': secret}
        path = collection + '/' + str(key['id'])
        request(suite, row, 'PUT', path, {'name': name + '-updated'}, headers=manager)
        current = request(suite, row, 'GET', path, headers=manager)['key']
        check(
            row,
            'key_metadata_redacted',
            current['name'] == name + '-updated' and 'key' not in current,
            'Key metadata update or one-time-secret contract failed',
        )
        with tracked_resource(suite, row, '/api/v1/pipelines', name, item_key='pipeline', list_key='pipelines'):
            before = request(suite, row, 'GET', '/api/v1/pipelines', headers=child)['pipelines']
            request(suite, row, 'POST', '/api/v1/pipelines', {'name': name}, headers=child, expected=403)
            after = request(suite, row, 'GET', '/api/v1/pipelines', headers=child)['pipelines']
            check(row, 'readonly_denial_preserves_state', before == after, 'Read-only key changed resources')
        revoke()
        request(suite, row, 'GET', '/api/v1/pipelines', headers=child, expected=401)
    finally:
        cleanup(suite, row, 'key_cleanup', revoke)


def run_case(suite, case, row):
    from tools.regression.regression_api_resources import mcp_case, skills_case

    name = case['scenario']
    row['api_seed'] = suite.profile['vars']['api_seed']

    def execute():
        if name in ('api_llm', 'api_embedding', 'api_rerank'):
            model_case(suite, row, name.removeprefix('api_'))
        else:
            {
                'api_pipeline': pipeline_case,
                'api_credentials': credentials_case,
                'api_skills': skills_case,
                'api_mcp': mcp_case,
            }[name](suite, row)

    checked(row, 'api_chain', execute)
    return {'result': case['expect']}
