"""Published CLI compatibility checks with strict backend state and flexible presentation."""

import subprocess

from regression_api_checks import check, request, tracked_resource, unique_name
from regression_coverage import checked
from regression_local_cases import require
from regression_resource_cases import journal

CASE_NAMES = ('cli.identity', 'cli.pipeline_roundtrip', 'cli.invalid_credential')


def configure(profile):
    profile.update(resources=[], cases=[], coverage_suite='cli', scenario_groups=['cli'])
    profile['cases'] = [
        {'name': name, 'scenario': name, 'stage': 'cli', 'expect': 'CLI_COMPAT_OK'} for name in CASE_NAMES
    ]


def identity(suite, row):
    row['cli_version'] = suite.call(['version'])
    result = suite.call(['whoami'])
    check(
        row,
        'workspace_identity',
        result.get('workspace_uuid') == suite.variables['workspace_uuid'],
        'CLI resolved a different Workspace',
    )
    capabilities = suite.call(['capabilities'])
    check(row, 'capability_discovery', bool(capabilities), 'CLI capability discovery returned no data')


def pipeline_roundtrip(suite, row):
    name, collection = unique_name(), '/api/v1/pipelines'
    with tracked_resource(suite, row, collection, name, item_key='pipeline', list_key='pipelines') as owned:
        created = suite.call(['pipeline', 'apply'], {'name': name, 'description': 'CLI fixture 中文'})
        matches = [p for p in request(suite, row, 'GET', collection)['pipelines'] if p['name'] == name]
        require(len(matches) == 1, 'CLI create did not persist exactly one owned Pipeline')
        uid = matches[0]['uuid']
        owned.update(uuid=uid, state='created')
        journal(suite, row)
        path = collection + '/' + uid
        check(
            row,
            'create_identity',
            created.get('pipeline', created).get('uuid') == uid,
            'CLI create omitted the created resource identity',
        )
        current = suite.call(['pipeline', 'get', uid])
        check(
            row,
            'cli_get',
            current.get('pipeline', current).get('uuid') == uid,
            'CLI get omitted the owned entity identity',
        )
        listed = suite.call(['pipeline', 'list'])
        items = listed.get('pipelines', []) if isinstance(listed, dict) else listed
        check(
            row,
            'cli_list',
            isinstance(items, list) and any(item.get('uuid') == uid for item in items),
            'CLI list omitted the owned entity identity',
        )
        before = request(suite, row, 'GET', path)['pipeline']
        check(row, 'create_state', before['description'] == 'CLI fixture 中文', 'CLI create changed submitted content')
        suite.call(
            ['pipeline', 'apply'],
            {
                'uuid': uid,
                'name': name + '-updated',
                'description': 'CLI updated 🌍',
                'config': before['config'],
            },
        )
        after = request(suite, row, 'GET', path)['pipeline']
        check(
            row,
            'update_state',
            after['name'] == name + '-updated'
            and after['description'] == 'CLI updated 🌍'
            and after['config'] == before['config'],
            'CLI update lost submitted or existing configuration',
        )
        suite.call(['pipeline', 'delete', uid, '--yes'])
        request(suite, row, 'GET', path, expected=404)


def invalid_credential(suite, row):
    source = suite.connection.get('credential_source', '')
    require(source.startswith('env:'), 'CLI credential probe requires the disposable environment credential')
    result = subprocess.run(
        [*suite.cli, 'pipeline', 'list'],
        capture_output=True,
        text=True,
        timeout=suite.timeout(30),
        env={**suite.env, source.removeprefix('env:'): 'qa-invalid-credential'},
    )
    row['rejected_exit_code'] = result.returncode
    # Exit code is stable; error wording and JSON error details may evolve.
    check(row, 'credential_rejected', result.returncode != 0, 'CLI reported success with an invalid credential')
    check(row, 'error_signal', bool(result.stdout.strip() or result.stderr.strip()), 'CLI failure had no diagnostic')
    suite.call(['pipeline', 'list'])


def run_case(suite, case, row):
    checked(
        row,
        'cli_chain',
        lambda: {
            'cli.identity': identity,
            'cli.pipeline_roundtrip': pipeline_roundtrip,
            'cli.invalid_credential': invalid_credential,
        }[case['scenario']](suite, row),
    )
    return {'result': case['expect']}
