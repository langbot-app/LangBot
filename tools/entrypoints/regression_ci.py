#!/usr/bin/env python3
"""Prepare a disposable Linux CI stack from this checkout, then run a regression suite."""

import argparse
from contextlib import ExitStack
from hashlib import file_digest
from html import escape
import json
import os
from pathlib import Path
import secrets
import signal
import socket
import subprocess
import sys
import time

import yaml

from tools.entrypoints.regression_gate import supervise
from tools.entrypoints.regression_coverage import write_report
from tools.regression.regression_plugins import (
    PLUGIN_IDS,
    install_plugins,
    package_marketplace,
    prepare_published_plugins,
    prepare_source_plugins,
)
from tools.regression.regression_local_cases import DEFAULT_GROUPS, api, require
from tools.entrypoints.regression_suite import Suite, number, validate
from tools.entrypoints.regression_traffic import owned_box_containers
from tools.regression.observations import read_endpoint_snapshot

ROOT = Path(__file__).resolve().parents[2]
# The Runtime CLI does not expose a bind address. Restrict both of its
# listeners in the explicitly local Host lane without changing Runtime defaults.
HOST_RUNTIME = """
from langbot_plugin.runtime.io.controllers.ws import server

class LocalController(server.WebSocketServerController):
    def __init__(self, port, *, host="127.0.0.1", **kwargs):
        super().__init__(port, host="127.0.0.1", **kwargs)

server.WebSocketServerController = LocalController
from langbot_plugin.cli.__init__ import main
main()
"""
SUITE_BUDGETS = {
    'smoke': 60,
    'scenarios': 300,
    'daily': 1860,
    'endurance': 900,
    'api': 600,
    'state': 300,
    'isolation': 300,
    'plugin-lifecycle': 600,
    'cli': 180,
}
sys.path.insert(0, str(ROOT))
from tests.e2e.utils.config_factory import create_minimal_config, create_test_directories  # noqa: E402


def suite_profile(name, run_id, groups=(), api_seed=1, load_settings=None, *, api_fixed_only=False):
    profile_path = ROOT / 'tools/profiles' / ('endurance.json' if name == 'endurance' else 'smoke.json')
    if name in ('scenarios', 'daily'):
        from tools.regression.regression_scenarios import expanded_profile

        profile = expanded_profile(groups)
    else:
        profile = json.loads(profile_path.read_text())
    if name == 'state':
        from tools.regression.regression_state import state_profile

        profile = state_profile(profile)
    if name == 'api':
        from tools.regression.regression_api_cases import add_cases

        profile.update(resources=[], cases=[], coverage_suite='api')
        profile['vars'].update(api_seed=api_seed, api_fixed_only=api_fixed_only)
        add_cases(profile, fixed_only=api_fixed_only)
    if name == 'isolation':
        from tools.regression.regression_isolation_cases import isolation_profile

        profile = isolation_profile(profile)
    if name == 'plugin-lifecycle':
        from tools.regression.regression_plugin_lifecycle import add_cases

        profile.update(resources=[], cases=[], coverage_suite='plugin-lifecycle')
        add_cases(profile)
    if name == 'cli':
        from tools.regression.regression_cli_cases import configure

        configure(profile)
    for resource in profile['resources']:
        if resource['kind'] == 'pipeline':
            resource['body'].setdefault(
                'extensions_preferences',
                {
                    'enable_all_plugins': False,
                    'workspace_operations': [],
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
    if load_settings is not None:
        if name != 'endurance':
            raise ValueError('A load profile requires --suite endurance')
        if not isinstance(load_settings, dict) or not load_settings:
            raise ValueError('A load profile must be a non-empty object')
        allowed = {'phases', 'thresholds', 'resource_limits', 'performance_mode', 'box_command_delay_seconds'}
        if extra := load_settings.keys() - allowed:
            raise ValueError(f'Unsupported load profile fields: {sorted(extra)}')
        number(load_settings.get('box_command_delay_seconds', 1), 'box_command_delay_seconds')
        profile.update({key: value for key, value in load_settings.items() if key != 'box_command_delay_seconds'})
        validate(profile)
    return profile, profile_path


def mixed_scenarios(box_command_delay_seconds=1):
    """Build the measured mixed stimulus with an explicit Box command duration."""
    number(box_command_delay_seconds, 'box_command_delay_seconds')
    scenarios = json.loads((ROOT / 'tools/fixtures/mock_llm_scenarios.json').read_text())
    for model in ('mock-chat', 'mock-smoke-box', 'mock-rag'):
        scenarios[model]['delay_seconds'] = 0.6
    for step in scenarios['mock-smoke-box']['steps']:
        for call in step.get('tool_calls', []):
            call['arguments']['command'] = (
                'printf \'LB_BOX_HOST=%s\\n\' "$(hostname)"; '
                f'sleep {box_command_delay_seconds}; ' + call['arguments']['command']
            )
    return scenarios


def ready(url, processes, timeout=120):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if any(p.poll() is not None for p in processes):
            raise RuntimeError('A regression dependency exited; inspect service logs')
        try:
            read_endpoint_snapshot(url, timeout_seconds=1, require_ready_json=True)
            return
        except (RuntimeError, OSError):
            time.sleep(0.2)
    raise RuntimeError(f'Service did not become ready: {url}')


def allocate_ports():
    # Keep reservations open together so this Job never selects the same port twice.
    with ExitStack() as reservations:
        ports = {}
        for name in ('core', 'runtime', 'debug', 'box', 'mock', 'mock_box', 'mock_rag'):
            listener = reservations.enter_context(socket.socket())
            listener.bind(('127.0.0.1', 0))
            ports[name] = listener.getsockname()[1]
        return ports


def host_wheel_index(private, wheelhouse):
    """Publish a private, file-based PEP 503 index for the OSS installer."""
    from packaging.utils import parse_wheel_filename

    index = private / 'wheel-index'
    index.mkdir()
    entries = {}
    for wheel in sorted(wheelhouse.glob('*.whl')):
        package, _, _, _ = parse_wheel_filename(wheel.name)
        with wheel.open('rb') as contents:
            digest = file_digest(contents, 'sha256').hexdigest()
        href = escape(f'{wheel.resolve().as_uri()}#sha256={digest}', quote=True)
        entries.setdefault(package, []).append(f'<a href="{href}">{escape(wheel.name)}</a>')
    for package, links in entries.items():
        destination = index / package
        destination.mkdir()
        (destination / 'index.html').write_text('\n'.join(links) + '\n')
    return index.as_uri() + '/'


def host_environment(private, wheelhouse):
    """Remove ambient credentials and use only prefetched dependency wheels."""
    home = private / 'home'
    home.mkdir(mode=0o700)
    scratch = private / 'tmp'
    scratch.mkdir(mode=0o700)
    # Control tools and trusted fixture scripts only: Host Box is not a sandbox.
    # These proxy settings are defense in depth for cooperative HTTP clients,
    # not an operating-system network isolation boundary.
    proxy = 'http://127.0.0.1:9'
    loopback = '127.0.0.1,localhost,::1'
    keep = ('PATH', 'LANG', 'LC_ALL', 'LC_CTYPE', 'TZ')
    env = {name: os.environ[name] for name in keep if name in os.environ}
    env.update(
        HOME=str(home),
        TMPDIR=str(scratch),
        PIP_CONFIG_FILE=os.devnull,
        PIP_DISABLE_PIP_VERSION_CHECK='1',
        LANGBOT_PLUGIN_PYPI_INDEX_URL=host_wheel_index(private, wheelhouse),
        UV_OFFLINE='1',
        ANONYMIZED_TELEMETRY='False',
        HTTP_PROXY=proxy,
        HTTPS_PROXY=proxy,
        ALL_PROXY=proxy,
        NO_PROXY=loopback,
        http_proxy=proxy,
        https_proxy=proxy,
        all_proxy=proxy,
        no_proxy=loopback,
    )
    return env


def run(args):
    host = args.box_backend == 'host'
    ports = allocate_ports()
    if (
        not host
        and subprocess.check_output(
            ['docker', 'ps', '-a', '--filter', 'label=langbot.box=true', '--format', '{{.ID}}'], text=True, timeout=10
        ).strip()
    ):
        raise RuntimeError('CI needs a dedicated Docker daemon with no existing Box sandboxes')
    root = args.output.resolve()
    root.mkdir(parents=True, exist_ok=False, mode=0o700)
    private = root / '.private'
    private.mkdir(mode=0o700)
    processes, logs = [], []
    services = ExitStack()
    owned_services = {}
    key, runtime_token, box_token = (secrets.token_urlsafe(32) for _ in range(3))
    env = dict(
        host_environment(private, args.plugin_wheelhouse.resolve()) if host else os.environ,
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
            ready(f'http://127.0.0.1:{ports["runtime"]}/healthz', processes, timeout=remaining())
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
        config_path = create_minimal_config(private, port=ports['core'])
        create_test_directories(private)
        config = yaml.safe_load(config_path.read_text())
        config.setdefault('space', {})['url'] = services.enter_context(package_marketplace(root / 'plugins', packages))
        config['api'].update(global_api_key=key, host='127.0.0.1')
        config['plugin'].update(enable=True, runtime_ws_url=f'ws://127.0.0.1:{ports["runtime"]}/control/ws')
        config['box'].update(
            enabled=True,
            backend='host' if host else 'local',
            runtime={'endpoint': f'ws://127.0.0.1:{ports["box"]}/control/ws'},
        )
        config['box']['local'].update(
            host_root=str(private / 'box'),
            allowed_mount_roots=[str(private / 'box')],
            image='' if host else 'python:3.12-alpine',
        )
        config_path.write_text(yaml.safe_dump(config))
        groups = args.scenario_groups
        if groups is None:
            groups = list(DEFAULT_GROUPS) if args.suite in ('scenarios', 'daily') else []
            if args.suite in ('api', 'isolation', 'plugin-lifecycle', 'cli'):
                groups = [args.suite]
            if 'plugins' in groups and not {'misc/EssentialCommands', 'misc/FAQManager'} <= set(args.extra_plugins):
                groups.remove('plugins')
        profile, profile_path = suite_profile(
            args.suite,
            secrets.token_hex(8),
            groups,
            args.api_seed,
            load_settings=args.load_settings,
            api_fixed_only=args.api_fixed_only,
        )
        if host:
            profile.get('resource_limits', {}).pop('containers', None)
            if args.mixload_profile is None:
                for case in profile['cases']:
                    oracle = case.get('box_exec')
                    if oracle and oracle.get('backend') == 'docker':
                        # Preserve the full count/output/exit oracle, but insist
                        # on actual Host execution rather than mislabel Docker.
                        oracle['backend'] = 'host'
        cli_config = private / 'lbctl.yaml'
        cli_config.write_text(
            yaml.safe_dump(
                {
                    'version': 1,
                    'current_context': 'smoke',
                    'contexts': {
                        'smoke': {
                            'endpoint': f'http://127.0.0.1:{ports["core"]}',
                            'credential': {'type': 'env', 'name': 'LANGBOT_QA_API_KEY'},
                        }
                    },
                }
            )
        )
        profile['cli'] = {'executable': str(args.lbctl.resolve()), 'config': str(cli_config)}
        profile['vars'].update(
            mock_base_url=f'http://127.0.0.1:{ports["mock"]}/v1',
            embedding_base_url=f'http://127.0.0.1:{ports["mock"]}/v1',
            box_mock_base_url=f'http://127.0.0.1:{ports["mock_box"]}/v1',
            rag_mock_base_url=f'http://127.0.0.1:{ports["mock_rag"]}/v1',
            core_base_url=f'http://127.0.0.1:{ports["core"]}',
            core_health=f'http://127.0.0.1:{ports["core"]}/healthz',
            core_db=str(private / 'data/langbot.db'),
            mock_records=str(root / 'mock-requests.jsonl'),
        )
        if args.suite == 'endurance':
            require(
                len({profile['vars'][name] for name in ('mock_base_url', 'box_mock_base_url', 'rag_mock_base_url')})
                == 3,
                'Mixed generation Providers require three distinct endpoints',
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
        mocks = {'mock': ports['mock']}
        mock_args = []
        if args.suite == 'endurance':
            mocks.update(mock_box=ports['mock_box'], mock_rag=ports['mock_rag'])
            # Fixed provider/tool latency makes overlap observable; this is not a performance baseline.
            if args.mixload_profile is not None:
                from tools.regression.mixload_cases import configure_mock_scenarios

                scenarios = json.loads((ROOT / 'tools/fixtures/mock_llm_scenarios.json').read_text())
                scenarios = configure_mock_scenarios(scenarios, box_backend=args.box_backend)
            else:
                scenarios = mixed_scenarios((args.load_settings or {}).get('box_command_delay_seconds', 1))
            scenario_path = private / 'mixed-scenarios.json'
            scenario_path.write_text(json.dumps(scenarios, indent=2))
            profile['vars']['mock_scenarios_file'] = str(scenario_path)
            mock_args = ['--scenarios', str(scenario_path)]
        for name, port in mocks.items():
            pids[name] = start(
                name,
                [
                    sys.executable,
                    str(ROOT / 'tools/entrypoints/mock_llm.py'),
                    '--port',
                    str(port),
                    '--record',
                    str(root / (name + '-requests.jsonl')),
                    *mock_args,
                ],
            )
        pids['runtime'] = start(
            'runtime',
            [
                sys.executable,
                *(['-c', HOST_RUNTIME] if host else ['-m', 'langbot_plugin.cli.__init__']),
                'rt',
                '--ws-control-port',
                str(ports['runtime']),
                '--ws-debug-port',
                str(ports['debug']),
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
                str(ports['box']),
            ],
        )
        pids['core'] = start(
            'core', [sys.executable, str(ROOT / 'main.py'), '--standalone-runtime', '--standalone-box']
        )
        profile['observe'] = {
            'health': {
                'core': f'http://127.0.0.1:{ports["core"]}/healthz',
                'box': f'http://127.0.0.1:{ports["box"]}/readyz',
                **{name: f'http://127.0.0.1:{port}/healthz' for name, port in mocks.items()},
            },
            'pids': pids,
        }
        if not host and args.suite in ('daily', 'endurance'):
            profile['observe']['box_data_root'] = str(private / 'box')
        if host:
            profile['observe']['health']['runtime'] = f'http://127.0.0.1:{ports["runtime"]}/healthz'
        budget = SUITE_BUDGETS[args.suite]
        if args.mixload_profile is not None:
            from tools.regression.profiled_mixload import prepare_profile

            profile = prepare_profile(profile, args.mixload_profile, box_backend=args.box_backend)
            if any(case['name'] == 'memory_chat' for case in profile['cases']):
                require(
                    any(entry['id'] == 'langbot-team/LongTermMemory' for entry in packages['plugins']),
                    'memory_chat requires the LongTermMemory fixture (--extra-plugins KnowledgeEngine/LongTermMemory)',
                )
            budget = 120 + sum(
                phase['duration_seconds'] + phase.get('cooldown_seconds', 0) for phase in profile['phases']
            )
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
        if packages['plugins'] or {'resources', 'api'} & set(groups) or args.restart_services or args.suite == 'state':
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

        def install_confirmed_plugin(entry):
            author, name = entry['id'].split('/')
            headers = {'Authorization': 'Bearer ' + env['LANGBOT_QA_USER_TOKEN']}
            status, response = api(
                suite,
                'POST',
                '/api/v1/plugins/install/marketplace',
                {
                    'plugin_author': author,
                    'plugin_name': name,
                    'plugin_version': entry['version'],
                    'auto_confirm_permissions': True,
                },
                headers=headers,
            )
            require(status == 200 and response.get('code') == 0, 'Wizard plugin installation was rejected')
            task_id = response['data']['task_id']
            deadline = time.monotonic() + suite.timeout(180)
            while time.monotonic() < deadline:
                status, response = api(suite, 'GET', f'/api/v1/system/tasks/{task_id}', headers=headers)
                require(status == 200 and response.get('code') == 0, 'Plugin installation task unavailable')
                task = response['data']
                if task['runtime']['done']:
                    require(not task['runtime']['exception'], f'Plugin installation/confirmation failed: {entry["id"]}')
                    return
                time.sleep(0.2)
            raise TimeoutError(f'Plugin installation/confirmation timed out: {entry["id"]}')

        install_plugins(
            suite.call,
            root / 'plugins',
            packages,
            install=install_confirmed_plugin,
            readiness_timeout=suite.timeout(180),
        )
        restart_result = None
        restart_elapsed = 0
        if args.restart_services:
            from tools.regression.regression_lifecycle_cases import run_restart_checks

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
            from tools.regression.regression_state import run_state_checks

            result = run_state_checks(profile, profile_path, root / 'gate/suite', env, restart_owned)
        else:
            result = supervise(
                [
                    sys.executable,
                    '-m',
                    'tools.entrypoints.regression_suite',
                    'run',
                    '--profile',
                    str(generated),
                    '--output',
                    str(root / 'gate/suite'),
                ],
                root / 'gate',
                (args.budget_seconds or budget) - restart_elapsed,
                pids,
                env,
            )
        if args.suite == 'endurance':
            provider_records = {
                'chat': root / 'mock-requests.jsonl',
                'box': root / 'mock_box-requests.jsonl',
                'rag_chat': root / 'mock_rag-requests.jsonl',
            }
            if args.mixload_profile is not None:
                from tools.regression.profiled_mixload import verify_profiled_run

                mixed = verify_profiled_run(root / 'gate/suite', private / 'data/langbot.db', provider_records, profile)
            else:
                from tools.regression.regression_mixed import verify_mixed

                mixed = verify_mixed(root / 'gate/suite', private / 'data/langbot.db', provider_records)
            (root / 'gate/mixed.json').write_text(json.dumps(mixed, indent=2) + '\n')
            result['mixed'] = mixed
            result['passed'] = result['passed'] and mixed['passed']
        evidence = [root / 'gate/suite']
        if restart_result is not None:
            evidence.append(root / 'restart-checks')
            result['restart_checks'] = restart_result
            result['restart_elapsed_seconds'] = restart_elapsed
        coverage = write_report(evidence, root / 'gate/suite', http_logs=[root / 'core.log'])
        result['coverage_errors'] = coverage['evidence_errors']
        result['scenario_groups'] = groups
        result['box_backend'] = args.box_backend
        if host:
            result['docker_container_evidence'] = 'not_applicable_host'
        if args.suite == 'api':
            result['api_fixed_only'] = args.api_fixed_only
            result['api_seed'] = None if args.api_fixed_only else args.api_seed
            result['case_order'] = [case['name'] for case in profile['cases']]
        result['passed'] = result['passed'] and not result['coverage_errors']
        (root / 'gate/gate.json').write_text(json.dumps(result, indent=2) + '\n')
        return result
    finally:
        services.close()
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
        if not host:
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
    profiles = parser.add_mutually_exclusive_group()
    profiles.add_argument(
        '--load-profile',
        type=Path,
        help='Endurance JSON overrides for load geometry, thresholds, resource limits and Box command delay',
    )
    parser.add_argument('--budget-seconds', type=int, help='Endurance execution guard, excluding service preparation')
    parser.add_argument(
        '--box-backend',
        choices=('docker', 'host'),
        default='docker',
        help='Host is an unsafe, loopback-only fixture lane, not Docker or a sandbox acceptance test',
    )
    parser.add_argument('--plugin-wheelhouse', type=Path, help='Prefetched local plugin dependency wheels for Host')
    profiles.add_argument(
        '--mixload-profile', type=Path, help='Run a configured mixed benchmark (endurance suite only)'
    )
    parser.add_argument(
        '--scenario-groups',
        nargs='*',
        choices=DEFAULT_GROUPS,
        help='Local groups for scenarios/daily (default: all); an empty list selects only the base cases',
    )
    parser.add_argument('--api-seed', type=int, default=1, help='Replay the API suite chain shuffle (default: 1)')
    parser.add_argument('--api-fixed-only', action='store_true', help='Run one fixed pass of the API chains')
    parser.add_argument('--restart-services', action='store_true', help='Check owned Core/Runtime restarts once')
    args = parser.parse_args()
    if args.api_fixed_only and args.suite != 'api':
        parser.error('--api-fixed-only requires --suite api')
    if args.extra_plugins and args.plugins is None:
        parser.error('--extra-plugins requires --plugins')
    if args.suite not in ('scenarios', 'daily') and (args.scenario_groups is not None or args.restart_services):
        parser.error('Optional scenarios and restarts require --suite scenarios or --suite daily')
    if args.suite != 'endurance' and (args.load_profile is not None or args.budget_seconds is not None):
        parser.error('--load-profile and --budget-seconds require --suite endurance')
    if args.budget_seconds is not None and args.budget_seconds <= 0:
        parser.error('--budget-seconds must be positive')
    args.load_settings = None
    if args.load_profile is not None:
        try:
            args.load_settings = json.loads(args.load_profile.read_text())
            suite_profile('endurance', 'validation', load_settings=args.load_settings)
        except (OSError, ValueError) as exc:
            parser.error(str(exc))
    if args.mixload_profile is not None and args.suite != 'endurance':
        parser.error('--mixload-profile requires --suite endurance')
    if args.box_backend == 'host':
        if args.plugins is None or args.plugins.resolve() != (ROOT / 'plugins').resolve():
            parser.error('Host requires --plugins pointing to this checkout’s bundled trusted fixtures')
        if args.plugin_wheelhouse is None or not any(args.plugin_wheelhouse.glob('*.whl')):
            parser.error('Host requires --plugin-wheelhouse with prefetched local wheels')
        if args.suite == 'endurance' and args.mixload_profile is None:
            parser.error('Host endurance requires --mixload-profile; the stock verifier is Docker only')
    elif args.plugin_wheelhouse is not None:
        parser.error('--plugin-wheelhouse is only supported for --box-backend host')
    if args.output.exists():
        parser.error('--output must be a new directory')
    try:
        result = run(args)
    except Exception as exc:
        verdict = args.output / 'gate' / 'gate.json'
        result = json.loads(verdict.read_text()) if verdict.exists() else {}
        result.update(passed=False, infrastructure_error=f'{type(exc).__name__}: {exc}', box_backend=args.box_backend)
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
