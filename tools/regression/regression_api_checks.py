"""HTTP and ownership checks shared by the local API contract cases."""

from contextlib import contextmanager
from uuid import uuid4

from tools.entrypoints.regression_coverage import checked
from tools.regression.regression_local_cases import api, require
from tools.regression.regression_resource_cases import cleanup, journal


def check(row, name, condition, message):
    return checked(row, name, lambda: require(condition, message))


def request(suite, row, method, path, body=None, *, expected=200, headers=None):
    step = {'method': method, 'path': path, 'expected_status': expected}
    row.setdefault('http_steps', []).append(step)
    status, response = api(suite, method, path, body, headers=headers)
    step['status'] = status
    check(
        row,
        f'http_{len(row["http_steps"])}',
        status == expected
        and isinstance(response, dict)
        and ((response.get('code') == 0) if expected < 400 else (response.get('code') not in (None, 0))),
        f'{method} {path}: expected HTTP {expected} with matching business status, got {status}',
    )
    return response.get('data', {}) if expected < 400 else response


def unique_name():
    return 'qa-api-' + uuid4().hex


def user_headers(suite):
    token = suite.env.get('LANGBOT_QA_USER_TOKEN')
    require(bool(token), 'API contracts require the disposable test account token')
    if token not in suite.secrets:
        suite.secrets.append(token)
    return {'Authorization': 'Bearer ' + token}


@contextmanager
def tracked_resource(suite, row, collection, name, *, item_key, list_key):
    """Clean an owned UUID resource even if its creation unexpectedly succeeds or times out."""
    owned = {'kind': item_key, 'name': name, 'state': 'creating'}
    row.setdefault('owned_resources', []).append(owned)
    journal(suite, row)

    def remove():
        if 'uuid' not in owned:
            items = request(suite, row, 'GET', collection)[list_key]
            matches = [item for item in items if item.get('name') in (name, name + '-updated')]
            require(len(matches) <= 1, 'Ambiguous owned resource identity')
            if not matches:
                owned['state'] = 'absent'
                return
            owned['uuid'] = matches[0]['uuid']
        path = collection + '/' + owned['uuid']
        status, response = api(suite, 'GET', path)
        if status != 404:
            require(status == 200 and response.get('code') == 0, 'Cannot read resource before cleanup')
            item = response['data'][item_key]
            require(
                item.get('uuid') == owned['uuid'] and item.get('name') in (name, name + '-updated'),
                'Resource ownership changed before cleanup',
            )
            request(suite, row, 'DELETE', path)
        request(suite, row, 'GET', path, expected=404)
        owned['state'] = 'deleted'

    try:
        yield owned
    finally:
        cleanup(suite, row, 'cleanup_' + item_key + '_' + name, remove)


@contextmanager
def owned_resource(suite, row, collection, body, *, item_key, list_key):
    with tracked_resource(suite, row, collection, body['name'], item_key=item_key, list_key=list_key) as owned:
        result = request(suite, row, 'POST', collection, body)
        owned.update(uuid=result['uuid'], state='created')
        journal(suite, row)
        yield collection + '/' + owned['uuid'], owned['uuid']
