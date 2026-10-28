"""Optional local scenarios share the Suite's verified Workspace and credentials."""

from contextlib import closing
import importlib
import json
from pathlib import Path
import sqlite3
import time
import urllib.error
import urllib.request

GROUPS = {
    'faults': 'regression_execution_cases',
    'resources': 'regression_resource_cases',
    'lifecycle': 'regression_lifecycle_cases',
    'plugins': 'regression_plugin_cases',
}


class ScenarioUnavailable(RuntimeError):
    """An explicit prerequisite is missing; this is not a passed assertion."""


def require(condition, message):
    if not condition:
        raise ValueError(message)


def endpoint(suite, path):
    require(path.startswith('/') and not path.startswith('//'), 'Scenario API path must be relative to Core')
    base = suite.connection.get('endpoint')
    require(bool(base), 'Scenario needs the endpoint verified by lbctl whoami')
    return base.rstrip('/') + path


def auth_headers(suite):
    source = suite.connection.get('credential_source', '')
    key = suite.env.get(source.removeprefix('env:')) if source.startswith('env:') else None
    require(bool(key), 'Scenario requires environment-backed lbctl credentials')
    if key not in suite.secrets:
        suite.secrets.append(key)
    return {'Authorization': 'Bearer ' + key, 'X-Workspace-Id': suite.variables['workspace_uuid']}


headers = auth_headers


def api(suite, method, path, body=None, headers=None):
    request_headers = dict(auth_headers(suite) if headers is None else headers)
    request_headers.setdefault('X-Workspace-Id', suite.variables['workspace_uuid'])
    if body is not None:
        request_headers['Content-Type'] = 'application/json'
    request = urllib.request.Request(
        endpoint(suite, path),
        method=method,
        headers=request_headers,
        data=json.dumps(body).encode() if body is not None else None,
    )
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    try:
        response = opener.open(request, timeout=suite.timeout(90))
    except urllib.error.HTTPError as exc:
        response = exc
    with response:
        return response.status, json.load(response)


def record_run(suite, row, run_id, expected_status):
    """Register exact run ownership for the independent final ledger check."""
    require(expected_status in {'completed', 'failed', 'cancelled', 'timeout'}, 'Expected Run status must be terminal')
    path = Path(suite.path(suite.profile['smoke']['ledger_db'])).resolve()
    deadline = time.monotonic() + suite.timeout(30)
    with closing(sqlite3.connect(path.as_uri() + '?mode=ro', uri=True, timeout=5)) as connection:
        connection.row_factory = sqlite3.Row
        while True:
            run = connection.execute(
                'SELECT run_id, conversation_id, status, finished_at FROM agent_run '
                'WHERE workspace_id=? AND run_id=? AND id>?',
                (suite.variables['workspace_uuid'], run_id, row['after_id']),
            ).fetchone()
            if run and run['finished_at']:
                observed = dict(run)
                observed.update(expected_status=expected_status, after_id=row['after_id'])
                row.setdefault('scenario_runs', []).append(observed)
                require(run['status'] == expected_status, f'Run ended as {run["status"]}; expected {expected_status}')
                return observed
            if time.monotonic() >= deadline:
                raise TimeoutError('Scenario Run did not reach a persisted terminal state')
            time.sleep(0.1)


def modules():
    return {name: importlib.import_module(module) for name, module in GROUPS.items()}


def add_cases(profile, groups):
    groups = list(groups)
    require(len(groups) == len(set(groups)), 'Scenario groups must not repeat')
    require(not (set(groups) - GROUPS.keys()), 'Unknown local scenario group')
    for name in groups:
        importlib.import_module(GROUPS[name]).add_cases(profile)
    profile['scenario_groups'] = groups


def run_case(suite, case, row):
    for name, module in modules().items():
        if case['scenario'] in module.CASE_NAMES:
            require(name in suite.profile.get('scenario_groups', []), f'Scenario group is disabled: {name}')
            return module.run_case(suite, case, row)
    raise ValueError(f'Unknown local scenario: {case["scenario"]}')
