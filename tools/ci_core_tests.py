"""Select changed Core suites and verify their CI evidence."""

import argparse
import json
import os
from pathlib import Path, PurePosixPath
import sys


UNIT_AREAS = {
    'agent': ('agent', 'pipeline', 'provider'),
    'api': ('api', 'plugin', 'workspace'),
    'box': ('box', 'agent', 'plugin'),
    'cloud': ('cloud', 'core', 'workspace'),
    'command': ('command', 'pipeline'),
    'discover': ('discover', 'plugin'),
    'operation_trace': (
        'test_operation_trace_incremental.py',
        'test_operation_trace_integrity.py',
        'test_operation_trace_tenant_scope.py',
    ),
    'pipeline': ('pipeline', 'agent', 'plugin', 'provider'),
    'platform': ('platform', 'pipeline'),
    'provider': ('provider', 'agent', 'pipeline'),
    'rag': ('rag', 'plugin', 'vector'),
    'survey': ('survey', 'api'),
    'telemetry': ('telemetry', 'api'),
    'vector': ('vector', 'rag'),
}
INTEGRATION_AREAS = {
    'agent': ('api', 'pipeline', 'plugin'),
    'api': ('api', 'plugin'),
    'box': ('api', 'plugin', 'skill'),
    'cloud': ('api',),
    'command': ('pipeline',),
    'discover': ('plugin',),
    'operation_trace': ('api',),
    'pipeline': ('pipeline', 'api', 'plugin'),
    'platform': ('pipeline',),
    'provider': ('pipeline', 'plugin'),
    'rag': ('plugin', 'vector', 'persistence'),
    'survey': ('api',),
    'telemetry': ('api',),
    'vector': ('vector', 'persistence'),
}
TEST_ROOTS = ('tests/unit_tests', 'tests/integration', 'tests/smoke', 'tests/e2e', 'tests/integration_tests')
FULL = (['tests/unit_tests', 'tests/smoke'], ['tests/integration'])


def select_core_tests(paths, full, root):
    if full or not paths:
        return FULL
    unit = {'tests/smoke'}
    integration = set()
    for raw in paths:
        path = PurePosixPath(raw)
        if path.is_absolute() or '..' in path.parts:
            return FULL
        name = path.as_posix()
        if name.startswith('src/langbot/'):
            if path.suffix not in ('.pyc', '.md'):
                if len(path.parts) < 5 or path.parts[2] != 'pkg' or path.parts[3] not in UNIT_AREAS:
                    return FULL
                area = path.parts[3]
                unit.update(f'tests/unit_tests/{item}' for item in UNIT_AREAS[area])
                # Legacy root-level regressions also exercise these source areas.
                unit.update(test.relative_to(root).as_posix() for test in (root / 'tests/unit_tests').glob('test_*.py'))
                integration.update(f'tests/integration/{item}' for item in INTEGRATION_AREAS.get(area, ()))
        elif name.startswith('tests/'):
            test_root = next((prefix for prefix in TEST_ROOTS if name.startswith(prefix + '/')), None)
            if path.suffix == '.md':
                continue
            # A helper, fixture, or removed test can affect more than one module.
            if (
                not test_root
                or path.suffix != '.py'
                or not path.name.startswith('test_')
                or not (root / name).is_file()
            ):
                return FULL
            if test_root == 'tests/unit_tests':
                unit.add(name)
            elif test_root == 'tests/integration':
                # Probe the area, not just the changed file: a slow-only file is
                # deselected in the fast lane, but may run in a service-backed lane.
                area = '/'.join(path.parts[:3])
                integration.add(area if (root / area).is_dir() else test_root)
    if any(not (root / target).exists() for target in unit | integration):
        raise ValueError('Mapped Core test target missing; update UNIT_AREAS/INTEGRATION_AREAS')

    def remove_redundant(targets):
        return sorted(item for item in targets if not any(item.startswith(parent + '/') for parent in targets))

    return remove_redundant(unit), remove_redundant(integration)


def _enabled(key):
    value = os.environ.get(key)
    if value not in ('true', 'false'):
        raise ValueError(f'Missing or invalid CI selection: {key}')
    return value == 'true'


def build_plan():
    paths = json.loads(os.environ['CHANGED_PATHS'])
    if not isinstance(paths, list) or not all(isinstance(path, str) for path in paths):
        raise ValueError('Expected an array of changed paths')
    flags = {
        key: _enabled(key.upper())
        for key in ('core', 'core_full', 'sdk', 'compatibility', 'persistence', 'permissions', 'box', 'frontend')
    }
    unit = any(
        flags[flag] for flag in ('core', 'core_full', 'sdk', 'compatibility', 'persistence', 'permissions', 'box')
    )
    targets, integration = select_core_tests(paths, flags['core_full'] or flags['compatibility'], Path.cwd())
    full_unit = unit and targets == FULL[0]
    full_e2e = any(flags[flag] for flag in ('core_full', 'sdk', 'compatibility', 'permissions', 'box'))
    full_e2e = full_e2e or any(path.startswith('tests/e2e/') for path in paths)
    box = flags['box'] or flags['sdk'] or flags['compatibility']
    box = box or any(path.startswith('tests/integration_tests/') for path in paths)
    plan = {
        'test': unit,
        'sqlalchemy-compat': flags['compatibility'] or flags['persistence'],
        'integration': unit and integration == FULL[1],
        'api-contracts': unit and os.environ.get('GITHUB_EVENT_NAME') == 'pull_request',
        'postgres-contracts': flags['persistence'] or flags['permissions'] or flags['compatibility'],
        'e2e': full_e2e or flags['frontend'],
        'box-integration': box,
    }
    versions = ['3.12', '3.11', '3.13', '3.14'] if flags['compatibility'] else ['3.12']
    return {
        'selection': plan,
        'python_versions': versions,
        'full_unit': full_unit,
        'runtime_contracts': full_unit or any(flags[name] for name in ('sdk', 'permissions', 'box', 'persistence')),
        'full_e2e': full_e2e,
        'unit_targets': targets,
        'integration_targets': [] if plan['integration'] else integration,
    }


def verify_gate(needs):
    plan = needs['plan']
    if plan['result'] != 'success':
        raise ValueError(f'Core test selection did not succeed: {plan["result"]}')
    selection = json.loads(plan['outputs']['selection'])
    actual_jobs = needs.keys() - {'plan'}
    if selection.keys() != actual_jobs or any(type(value) is not bool for value in selection.values()):
        raise ValueError(f'Unaccounted Core jobs: {actual_jobs ^ selection.keys()}')
    for job, selected in selection.items():
        actual = needs[job]['result']
        expected = 'success' if selected else 'skipped'
        if actual != expected:
            raise ValueError(f'{job}: expected {expected}, got {actual}')
        print(f'{job}: {actual}')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=('plan', 'gate'))
    args = parser.parse_args()
    if args.command == 'plan':
        data = build_plan()
        with open(os.environ['GITHUB_OUTPUT'], 'a', encoding='utf-8') as out:
            for key, value in data.items():
                print(f'{key}={json.dumps(value, separators=(",", ":"))}', file=out)
        print(json.dumps(data, indent=2))
    else:
        verify_gate(json.loads(os.environ['NEEDS_JSON']))


if __name__ == '__main__':
    try:
        main()
    except (KeyError, OSError, ValueError) as exc:
        print(exc, file=sys.stderr)
        sys.exit(1)
