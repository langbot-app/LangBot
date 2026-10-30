"""Exercise local plugin generations through HTTP tasks and real Page invocations."""

import io
import json
from pathlib import Path
import time
import urllib.request
from uuid import uuid4
import zipfile

import yaml

from regression_api_checks import check, request
from regression_coverage import checked
from regression_local_cases import api, auth_headers, endpoint, require
from regression_resource_cases import cleanup, journal

CASE_NAMES = ('plugin_upgrade', 'plugin_rejected_package', 'plugin_failed_activation')
FIXTURE = Path(__file__).with_name('regression_fixtures') / 'plugin_lifecycle'
AUTHOR = 'regression-qa'


def add_cases(profile):
    require(profile.get('coverage_suite') == 'plugin-lifecycle', 'Plugin lifecycle requires its dedicated suite')
    profile['scenario_groups'] = ['plugin-lifecycle']
    profile['cases'].extend(
        {'name': name, 'scenario': name, 'stage': 'plugins', 'expect': 'PLUGIN_LIFECYCLE_OK'} for name in CASE_NAMES
    )


def package(name, version, *, broken=False):
    manifest = {
        'apiVersion': 'v1',
        'kind': 'Plugin',
        'metadata': {
            'author': AUTHOR,
            'name': name,
            'version': version,
            'label': {'en_US': 'Lifecycle probe'},
            'description': {'en_US': 'Local regression fixture'},
            'icon': 'icon.svg',
        },
        'spec': {
            'config': [{'name': 'marker', 'type': 'string', 'default': '', 'label': {'en_US': 'Marker'}}],
            'components': {'Page': {'fromDirs': [{'path': 'components/pages/', 'maxDepth': 2}]}},
        },
        'execution': {'python': {'path': 'main.py', 'attr': 'LifecyclePlugin'}},
    }
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, 'w', zipfile.ZIP_DEFLATED) as archive:
        archive.writestr('manifest.yaml', yaml.safe_dump(manifest))
        archive.writestr('icon.svg', '<svg xmlns="http://www.w3.org/2000/svg"/>')
        for path in sorted(FIXTURE.rglob('*')):
            if not path.is_file() or '__pycache__' in path.parts:
                continue
            content = path.read_text()
            if path.name == 'main.py':
                content = content.replace("VERSION = '0.0.0'", f'VERSION = {version!r}')
                if broken:
                    content = content.replace('FAIL_INITIALIZE = False', 'FAIL_INITIALIZE = True')
            archive.writestr(str(path.relative_to(FIXTURE)), content)
    return buffer.getvalue()


def wait_task(suite, row, task_id, expected, label):
    deadline = time.monotonic() + suite.timeout(90)
    require(isinstance(task_id, int), 'Plugin operation did not return a task ID')
    while True:
        task = request(suite, row, 'GET', f'/api/v1/system/tasks/{task_id}')
        require(task.get('id') == task_id, 'Plugin task identity changed')
        status = task.get('status')
        require(status in {'running', 'succeeded', 'failed', 'cancelled'}, 'Malformed plugin task status')
        if status != 'running':
            row.setdefault('plugin_tasks', []).append({'label': label, **task})
            check(row, label + '_task', status == expected, f'{label}: expected {expected}, got {status}')
            if expected == 'failed':
                check(row, label + '_error', bool(task.get('error')), 'Failed task omitted its error')
            return
        if time.monotonic() >= deadline:
            raise TimeoutError(f'{label}: plugin task did not finish')
        time.sleep(0.2)


def upload(suite, row, content, name, *, expected='succeeded'):
    boundary = 'qa' + uuid4().hex
    body = (
        (
            f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="{name}.lbpkg"\r\n'
            'Content-Type: application/octet-stream\r\n\r\n'
        ).encode()
        + content
        + f'\r\n--{boundary}--\r\n'.encode()
    )
    headers = auth_headers(suite)
    headers['Content-Type'] = 'multipart/form-data; boundary=' + boundary
    path = '/api/v1/plugins/install/local'
    call = urllib.request.Request(endpoint(suite, path), data=body, headers=headers, method='POST')
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    with opener.open(call, timeout=suite.timeout(90)) as response:
        result = json.load(response)
        check(
            row,
            name + '_upload',
            response.status == 200 and result.get('code') == 0,
            'Local plugin upload was not accepted',
        )
    wait_task(suite, row, result['data']['task_id'], expected, name)


def process_identity(pid):
    try:
        # Start time distinguishes an old worker from a reused PID.
        return Path(f'/proc/{pid}/stat').read_text().rsplit(')', 1)[1].split()[19]
    except FileNotFoundError:
        return None


def metadata(plugin):
    return plugin['manifest']['manifest']['metadata']


def failed_generation_safe(suite, row, path, verify_good):
    def verify():
        status, response = api(suite, 'GET', path)
        row['failed_generation'] = {'http_status': status, 'plugin': response.get('data', {}).get('plugin')}
        if status == 404:
            require(response.get('code') not in (None, 0), 'Missing plugin returned a successful business status')
            return
        require(status == 200 and response.get('code') == 0, 'Failed generation cannot be observed')
        info = response.get('data', {}).get('plugin')
        require(isinstance(info, dict), 'Failed generation metadata is missing')
        identity = metadata(info)
        require(
            identity.get('author') == AUTHOR and identity.get('name') == path.rsplit('/', 1)[1],
            'Failed generation identity changed',
        )
        if identity.get('version') == '0.0.1':
            verify_good()  # A future automatic restore must pass the complete old-version state oracle.
            return
        require(
            identity.get('version') == '0.0.2' and info.get('status') in {'unmounted', 'mounted'},
            'Failed plugin generation is initialized or has an unexpected version/state',
        )
        page_status, page = api(
            suite,
            'POST',
            path + '/page-api',
            {
                'page_id': 'probe',
                'endpoint': '/state',
                'method': 'GET',
                'body': None,
            },
        )
        row['failed_generation']['page_status'] = page_status
        require(
            page_status in {400, 404, 409, 500, 503} and page.get('code') not in (None, 0),
            'Failed plugin generation remains callable',
        )

    checked(row, 'failed_generation_safe', verify)


def workers_stopped(suite, workers):
    deadline = time.monotonic() + suite.timeout(10)
    while any(process_identity(int(pid)) == started for pid, started in workers.items()):
        if time.monotonic() >= deadline:
            raise ValueError('An observed plugin worker remains after uninstall or upgrade')
        time.sleep(0.1)


def run_case(suite, case, row):
    name = 'lifecycle-' + uuid4().hex
    path = f'/api/v1/plugins/{AUTHOR}/{name}'
    owned = {'kind': 'plugin', 'author': AUTHOR, 'name': name, 'state': 'creating'}
    row.setdefault('owned_resources', []).append(owned)
    journal(suite, row)
    workers = row['plugin_workers'] = {}
    marker = 'persistent-中文-' + uuid4().hex

    def installed(version, label, *, write=False):
        deadline = time.monotonic() + suite.timeout(45)
        while True:
            status, response = api(suite, 'GET', path)
            info = response.get('data', {}).get('plugin', {})
            if status == 200 and info.get('status') == 'initialized':
                break
            require(status in {200, 404}, 'Plugin readiness query failed')
            if time.monotonic() >= deadline:
                raise TimeoutError('Plugin did not become ready after operation')
            time.sleep(0.2)
        identity = metadata(info)
        check(
            row,
            label + '_identity',
            identity.get('author') == AUTHOR
            and identity.get('name') == name
            and identity.get('version') == version
            and info.get('enabled') is True,
            'Plugin generation differs',
        )
        listed = request(suite, row, 'GET', '/api/v1/plugins')['plugins']
        check(
            row,
            label + '_unique',
            sum(metadata(p)['author'] == AUTHOR and metadata(p)['name'] == name for p in listed) == 1,
            'Plugin generation is missing or duplicated',
        )
        state = request(
            suite,
            row,
            'POST',
            path + '/page-api',
            {
                'page_id': 'probe',
                'endpoint': '/state',
                'method': 'POST' if write else 'GET',
                'body': {'token': marker} if write else None,
            },
        )
        check(
            row,
            label + '_state',
            state.get('version') == version
            and state.get('token') == marker
            and state.get('config') == {'marker': marker},
            'Plugin call lost version, stored data, or config',
        )
        pid = state.get('pid')
        require(isinstance(pid, int) and pid > 0, 'Plugin did not return its worker PID')
        started = process_identity(pid)
        require(started is not None, 'Observed plugin worker already disappeared')
        old = {key: value for key, value in workers.items() if key != str(pid)}
        workers[str(pid)] = started
        checked(row, label + '_old_workers_stopped', lambda: workers_stopped(suite, old))
        return state

    def remove():
        status, response = api(suite, 'GET', path)
        if status != 404:
            require(status == 200 and response.get('code') == 0, 'Cannot confirm owned plugin before cleanup')
            info = metadata(response['data']['plugin'])
            require(info.get('author') == AUTHOR and info.get('name') == name, 'Plugin cleanup identity changed')
        # A failed generation can have a durable installation without a registered worker.
        task = request(suite, row, 'DELETE', path + '?delete_data=true')
        wait_task(suite, row, task['task_id'], 'succeeded', 'uninstall')
        request(suite, row, 'GET', path, expected=404)
        listed = request(suite, row, 'GET', '/api/v1/plugins')['plugins']
        check(
            row,
            'uninstalled_from_list',
            not any(metadata(p)['author'] == AUTHOR and metadata(p)['name'] == name for p in listed),
            'Uninstalled plugin remains listed',
        )
        checked(row, 'uninstalled_workers_stopped', lambda: workers_stopped(suite, workers))
        owned['state'] = 'deleted'

    request(suite, row, 'GET', path, expected=404)
    try:
        first = package(name, '0.0.1')
        upload(suite, row, first, 'install_v1')
        owned['state'] = 'installed'
        journal(suite, row)
        request(suite, row, 'PUT', path + '/config', {'marker': marker})
        installed('0.0.1', 'v1', write=True)
        if case['scenario'] == 'plugin_upgrade':
            upload(suite, row, package(name, '0.0.2'), 'upgrade_v2')
            installed('0.0.2', 'v2')
        elif case['scenario'] == 'plugin_rejected_package':
            upload(suite, row, first, 'reinstall_v1')
            installed('0.0.1', 'after_reinstall')
            upload(suite, row, b'not a plugin zip', 'invalid_archive', expected='failed')
            installed('0.0.1', 'after_invalid_archive')
        elif case['scenario'] == 'plugin_failed_activation':
            upload(suite, row, package(name, '0.0.2', broken=True), 'broken_v2', expected='failed')
            failed_generation_safe(suite, row, path, lambda: installed('0.0.1', 'automatic_restore_v1'))
            upload(suite, row, first, 'restore_v1')
            installed('0.0.1', 'restored_v1')
            upload(suite, row, package(name, '0.0.3'), 'recovered_v3')
            installed('0.0.3', 'v3')
        else:
            raise ValueError('Unknown plugin lifecycle case')
        return {'result': case['expect']}
    finally:
        cleanup(suite, row, 'plugin_cleanup', remove)
