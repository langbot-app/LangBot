"""Optional local scenarios share the Suite's verified Workspace and credentials."""

import importlib
import json
import urllib.error
import urllib.request

GROUPS = {
    'faults': 'tools.regression.regression_execution_cases',
    'resources': 'tools.regression.regression_resource_cases',
    'lifecycle': 'tools.regression.regression_lifecycle_cases',
    'plugins': 'tools.regression.regression_plugin_cases',
    'api': 'tools.regression.regression_api_cases',
    'isolation': 'tools.regression.regression_isolation_cases',
    'plugin-lifecycle': 'tools.regression.regression_plugin_lifecycle',
    'cli': 'tools.regression.regression_cli_cases',
}


DEFAULT_GROUPS = ('faults', 'resources', 'lifecycle', 'plugins')


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
