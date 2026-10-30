#!/usr/bin/env python3
"""Prepare a disposable Linux CI stack from this checkout, then run a regression suite."""

import argparse
import json
import os
from pathlib import Path
import secrets
import signal
import subprocess
import sys
import time

import yaml

from regression_gate import supervise
from regression_coverage import write_report
from regression_plugins import PLUGIN_IDS, install_plugins, prepare_published_plugins, prepare_source_plugins
from regression_local_cases import DEFAULT_GROUPS, api, require
from regression_suite import Suite
from regression_traffic import owned_box_containers, read_endpoint_snapshot

ROOT = Path(__file__).resolve().parents[1]
SUITE_BUDGETS = {
    'smoke': 60,
    'scenarios': 300,
    'daily': 1860,
    'endurance': 900,
    'api': 600,
    'state': 300,
    'isolation': 300,
    'plugin-lifecycle': 600,
}
sys.path.insert(0, str(ROOT))
from tests.e2e.utils.config_factory import create_minimal_config, create_test_directories  # noqa: E402


def suite_profile(name, run_id, groups=(), api_seed=1):
    profile_path = ROOT / 'tools/regression_profiles' / ('endurance.json' if name == 'endurance' else 'smoke.json')
    if name in ('scenarios', 'daily'):
        from regression_scenarios import expanded_profile

        profile = expanded_profile(groups)
    else:
        profile = json.loads(profile_path.read_text())
    if name == 'state':
        from regression_state import state_profile

        profile = state_profile(profile)
    if name == 'api':
        from regression_api_cases import add_cases

        profile.update(resources=[], cases=[], coverage_suite='api')
        profile['vars']['api_seed'] = api_seed
        add_cases(profile)
    if name == 'isolation':
        from regression_isolation_cases import isolation_profile

        profile = isolation_profile(profile)
    if name == 'plugin-lifecycle':
        from regression_plugin_lifecycle import add_cases

        profile.update(resources=[], cases=[], coverage_suite='plugin-lifecycle')
        add_cases(profile)
    for resource in profile['resources']:
        if resource['kind'] == 'pipeline':
            resource['body'].setdefault(
                'extensions_preferences',
                {
                    'enable_all_plugins': False,
                    'plugins': [dict(zip(('author', 'name'), plugin.split('/'))) for plugin in PLUGIN_IDS],
                },
            )
    if name == 'smoke':
        profile['smoke']['group_turns'] = 2
    if name == 'daily':
        limits = json.loads((profile_path.parent / 'endurance.json').read_text())['resource_limits']
        limits['warmup_seconds'] = 180
        profile.update(
            execution={'total_seconds': 1800, 'drain_seconds': 120, 'cooldown_seconds': 60},
            resource_limits=limits,
        )
        for resource in profile['resources']:
            if resource['kind'] != 'pipeline':
                continue
            for config in resource['body']['config']['ai']['runner_config'].values():
                if config.get('box-enabled'):
                    # This workload measures repeated tool use; each pipeline owns one sandbox per CI run.
                    config['box-session-id-template'] = f'qa-{run_id}-{resource["id"]}'
    profile.update(cleanup='always', performance_mode='observe')
    return profile, profile_path


def ready(url, processes, timeout=120):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if any(p.poll() is not None for p in processes):
            raise RuntimeError('A regression dependency exited; inspect service logs')
        try:
            read_endpoint_snapshot(url, timeout_seconds=1)
            return
        except (RuntimeError, OSError):
            time.sleep(0.2)
    raise RuntimeError(f'Service did not become ready: {url}')


def run(args):
    if subprocess.check_output(
        ['docker', 'ps', '-a', '--filter', 'label=langbot.box=true', '--format', '{{.ID}}'], text=True, timeout=10
    ).strip():
        raise RuntimeError('CI needs a dedicated Docker daemon with no existing Box sandboxes')
    root = args.output.resolve()
    root.mkdir(parents=True, exist_ok=False, mode=0o700)
    private = root / '.private'
    private.mkdir(mode=0o700)
    processes, logs = [], []
    owned_services = {}
    key, runtime_token, box_token = (secrets.token_urlsafe(32) for _ in range(3))
    env = dict(
        os.environ,
        LANGBOT_QA_API_KEY=key,
        LANGBOT_DATA_ROOT=str(private / 'data'),
        PYTHONPATH=str(ROOT / 'src'),
        LITELLM_LOCAL_MODEL_COST_MAP='True',
        PYTHONUNBUFFERED='1',
        LANGBOT_PLUGIN_RUNTIME_CONTROL_TOKEN=runtime_token,
        LANGBOT_BOX_CONTROL_TOKEN=box_token,
    )

    def start(name, command):
        log = (root / f'{name}.log').open('a')
        logs.append(log)
        process = subprocess.Popen(
            command, cwd=private, env=env, stdout=log, stderr=subprocess.STDOUT, start_new_session=True
        )
        processes.append(process)
        owned_services[name] = (process, command)
        return process.pid

    def restart_owned(name, timeout=60):
        deadline = time.monotonic() + timeout

        def remaining():
            value = deadline - time.monotonic()
            if value <= 0:
                raise TimeoutError(f'{name} restart exceeded its deadline')
            return value

        require(name in {'core', 'runtime'}, "Only this runner's Core and Runtime can be restarted")
        process, command = owned_services[name]
        old_pid = process.pid
        require(process.poll() is None, f'{name} exited before the planned restart')
        os.killpg(process.pid, signal.SIGTERM)
        try:
            process.wait(timeout=min(5, remaining()))
        except subprocess.TimeoutExpired:
            os.killpg(process.pid, signal.SIGKILL)
            process.wait(timeout=remaining())
        processes.remove(process)
        pids[name] = start(name, command)
        if name == 'runtime':
            ready('http://127.0.0.1:15340/healthz', processes, timeout=remaining())
        ready(profile['observe']['health']['core'], processes, timeout=remaining())
        while True:
            previous_timeout = suite.timeout
            try:
                suite.timeout = lambda maximum: min(maximum, remaining())
                listed = suite.call(['plugin', 'list'])
            except RuntimeError:
                remaining()
                time.sleep(min(0.2, remaining()))
                continue
            finally:
                suite.timeout = previous_timeout
            initialized = {
                f'{item["author"]}/{item["name"]}'
                for item in listed['plugins']
                if item.get('enabled') and item.get('status') == 'initialized'
            }
            if set(profile['smoke']['required_plugins']) <= initialized:
                break
            time.sleep(min(0.2, remaining()))
        return {'service': name, 'old_pid': old_pid, 'new_pid': pids[name], 'old_exit_code': process.returncode}

    try:
        if args.suite == 'plugin-lifecycle':
            (root / 'plugins').mkdir()
            packages = {'version': 1, 'selection': 'local-fixtures', 'plugins': []}
        else:
            packages = (
                prepare_source_plugins(root / 'plugins', args.plugins, args.extra_plugins)
                if args.plugins is not None
                else prepare_published_plugins(root / 'plugins', args.plugin_manifest)
            )
        config_path = create_minimal_config(private, port=15301)
        create_test_directories(private)
        config = yaml.safe_load(config_path.read_text())
        config['api'].update(global_api_key=key, host='127.0.0.1')
        config['plugin'].update(enable=True, runtime_ws_url='ws://127.0.0.1:15340/control/ws')
        config['box'].update(enabled=True, backend='local', runtime={'endpoint': 'ws://127.0.0.1:15310/control/ws'})
        config['box']['local'].update(
            host_root=str(private / 'box'), allowed_mount_roots=[str(private / 'box')], image='python:3.12-alpine'
        )
        config_path.write_text(yaml.safe_dump(config))
        groups = args.scenario_groups
        if groups is None:
            groups = list(DEFAULT_GROUPS) if args.suite in ('scenarios', 'daily') else []
            if args.suite in ('api', 'isolation', 'plugin-lifecycle'):
                groups = [args.suite]
            if 'plugins' in groups and not {'misc/EssentialCommands', 'misc/FAQManager'} <= set(args.extra_plugins):
                groups.remove('plugins')
        profile, profile_path = suite_profile(args.suite, secrets.token_hex(8), groups, args.api_seed)
        cli_config = private / 'lbctl.yaml'
        cli_config.write_text(
            yaml.safe_dump(
                {
                    'version': 1,
                    'current_context': 'smoke',
                    'contexts': {
                        'smoke': {
                            'endpoint': 'http://127.0.0.1:15301',
                            'credential': {'type': 'env', 'name': 'LANGBOT_QA_API_KEY'},
                        }
                    },
                }
            )
        )
        profile['cli'] = {'executable': str(args.lbctl.resolve()), 'config': str(cli_config)}
        profile['vars'].update(
            mock_base_url='http://127.0.0.1:18080/v1',
            embedding_base_url='http://127.0.0.1:18080/v1',
            core_base_url='http://127.0.0.1:15301',
            core_health='http://127.0.0.1:15301/healthz',
            core_db=str(private / 'data/langbot.db'),
            mock_records=str(root / 'mock-requests.jsonl'),
        )
        profile['plugins'] = []
        if 'smoke' in profile:
            profile['smoke']['required_plugins'] = [entry['id'] for entry in packages['plugins']]
        for resource in profile['resources']:
            if resource['kind'] == 'model' and resource.get('type') == 'embedding':
                resource['body']['name'] = 'mock-embedding'
            for document in resource.get('documents', []):
                document['file'] = str((profile_path.parent / document['file']).resolve())
        pids = {}
        pids['mock'] = start(
            'mock',
            [
                sys.executable,
                str(ROOT / 'tools/mock_llm.py'),
                '--port',
                '18080',
                '--record',
                str(root / 'mock-requests.jsonl'),
            ],
        )
        pids['runtime'] = start(
            'runtime',
            [
                sys.executable,
                '-m',
                'langbot_plugin.cli.__init__',
                'rt',
                '--ws-control-port',
                '15340',
                '--ws-debug-port',
                '15341',
            ],
        )
        pids['box'] = start(
            'box',
            [
                sys.executable,
                '-m',
                'langbot_plugin.cli.__init__',
                'box',
                '--host',
                '127.0.0.1',
                '--ws-control-port',
                '15310',
            ],
        )
        pids['core'] = start(
            'core', [sys.executable, str(ROOT / 'main.py'), '--standalone-runtime', '--standalone-box']
        )
        profile['observe'] = {
            'health': {
                'core': 'http://127.0.0.1:15301/healthz',
                'box': 'http://127.0.0.1:15310/readyz',
                'mock': 'http://127.0.0.1:18080/healthz',
            },
            'pids': pids,
        }
        if args.suite in ('daily', 'endurance'):
            profile['observe']['box_data_root'] = str(private / 'box')
        for url in profile['observe']['health'].values():
            ready(url, processes)
        preparation = root / 'preparation'
        preparation.mkdir()
        suite = Suite(profile, profile_path, preparation, env)
        identity = suite.call(['whoami'])
        suite.variables['workspace_uuid'] = identity['workspace_uuid']
        # Bind the CLI to the newly bootstrapped Workspace before installing plugins.
        cli_data = yaml.safe_load(cli_config.read_text())
        cli_data['contexts']['smoke']['expected_workspace_uuid'] = identity['workspace_uuid']
        cli_config.write_text(yaml.safe_dump(cli_data))
        if {'resources', 'api'} & set(groups) or args.restart_services:
            # Account creation is restricted to this runner's newly created private database.
            credentials = {'user': 'regression@langbot.test', 'password': secrets.token_urlsafe(32)}
            suite.secrets.append(credentials['password'])
            status, response = api(suite, 'POST', '/api/v1/user/init', credentials, headers={})
            require(status == 200 and response.get('code') == 0, 'Disposable test account initialization failed')
            status, response = api(suite, 'POST', '/api/v1/user/auth', credentials, headers={})
            require(status == 200 and response.get('code') == 0, 'Disposable test account authentication failed')
            env['LANGBOT_QA_USER_TOKEN'] = response['data']['token']
            suite.env['LANGBOT_QA_USER_TOKEN'] = env['LANGBOT_QA_USER_TOKEN']
            suite.secrets.append(env['LANGBOT_QA_USER_TOKEN'])
        install_plugins(suite.call, root / 'plugins', packages)
        restart_result = None
        restart_elapsed = 0
        if args.restart_services:
            from regression_lifecycle_cases import run_restart_checks

            started = time.monotonic()
            restart_result = run_restart_checks(profile, profile_path, root / 'restart-checks', env, restart_owned)
            restart_elapsed = time.monotonic() - started
            if not restart_result['passed']:
                raise RuntimeError('Owned-service restart checks failed; inspect restart-checks/summary.json')
            if 'execution' in profile:
                profile['execution']['total_seconds'] -= restart_elapsed
                require(
                    profile['execution']['total_seconds']
                    > profile['execution']['drain_seconds'] + profile['execution']['cooldown_seconds'],
                    'Restart checks consumed the scenario execution budget',
                )
        generated = private / f'{args.suite}.json'
        generated.write_text(json.dumps(profile, indent=2))
        if args.suite == 'state':
            from regression_state import run_state_checks

            result = run_state_checks(profile, profile_path, root / 'gate/suite', env, restart_owned)
        else:
            result = supervise(
                [
                    sys.executable,
                    str(ROOT / 'tools/regression_suite.py'),
                    'run',
                    '--profile',
                    str(generated),
                    '--output',
                    str(root / 'gate/suite'),
                ],
                root / 'gate',
                SUITE_BUDGETS[args.suite] - restart_elapsed,
                pids,
                env,
            )
        evidence = [root / 'gate/suite']
        if restart_result is not None:
            evidence.append(root / 'restart-checks')
            result['restart_checks'] = restart_result
            result['restart_elapsed_seconds'] = restart_elapsed
        coverage = write_report(evidence, root / 'gate/suite', http_logs=[root / 'core.log'])
        result['coverage_errors'] = coverage['evidence_errors']
        result['scenario_groups'] = groups
        if args.suite == 'api':
            result['api_seed'] = args.api_seed
            result['case_order'] = [case['name'] for case in profile['cases']]
        result['passed'] = result['passed'] and not result['coverage_errors']
        (root / 'gate/gate.json').write_text(json.dumps(result, indent=2) + '\n')
        return result
    finally:
        for process in reversed(processes):
            if process.poll() is None:
                os.killpg(process.pid, signal.SIGTERM)
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    os.killpg(process.pid, signal.SIGKILL)
                    process.wait()
        for log in logs:
            log.close()
        # This is a disposable CI daemon; still delete only this run's mounted sandboxes.
        for container in owned_box_containers(private / 'box'):
            subprocess.run(['docker', 'rm', '-f', container], check=True, capture_output=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--lbctl', type=Path, required=True)
    plugins = parser.add_mutually_exclusive_group()
    plugins.add_argument('--plugins', type=Path, help='Build and install plugins from this source root')
    plugins.add_argument('--plugin-manifest', type=Path, help='Replay published versions and hashes from a prior run')
    parser.add_argument(
        '--extra-plugins', nargs='*', default=[], help='Additional paths under --plugins, e.g. misc/HelloPlugin'
    )
    parser.add_argument('--suite', choices=tuple(SUITE_BUDGETS), default='smoke')
    parser.add_argument(
        '--scenario-groups',
        nargs='*',
        choices=DEFAULT_GROUPS,
        help='Local groups for scenarios/daily (default: all); an empty list selects only the base cases',
    )
    parser.add_argument('--api-seed', type=int, default=1, help='Replay the API suite chain shuffle (default: 1)')
    parser.add_argument('--restart-services', action='store_true', help='Check owned Core/Runtime restarts once')
    args = parser.parse_args()
    if args.extra_plugins and args.plugins is None:
        parser.error('--extra-plugins requires --plugins')
    if args.suite not in ('scenarios', 'daily') and (args.scenario_groups is not None or args.restart_services):
        parser.error('Optional scenarios and restarts require --suite scenarios or --suite daily')
    if args.output.exists():
        parser.error('--output must be a new directory')
    try:
        result = run(args)
    except Exception as exc:
        verdict = args.output / 'gate' / 'gate.json'
        result = json.loads(verdict.read_text()) if verdict.exists() else {}
        result.update(passed=False, infrastructure_error=f'{type(exc).__name__}: {exc}')
        restart_summary = args.output / 'restart-checks/summary.json'
        if restart_summary.exists():
            result['restart_checks'] = json.loads(restart_summary.read_text())
        verdict.parent.mkdir(parents=True, exist_ok=True)
        verdict.write_text(json.dumps(result, indent=2) + '\n')
        raise
    print(json.dumps(result, indent=2))
    raise SystemExit(0 if result['passed'] else 1)


if __name__ == '__main__':
    main()
