#!/usr/bin/env python3
"""Prepare a disposable Linux CI stack from this checkout, then run the 60s gate."""

import argparse
import json
import os
from pathlib import Path
import secrets
import shutil
import signal
import subprocess
import sys
import time

import yaml

from regression_gate import supervise
from regression_plugins import install_published_plugins, prepare_published_plugins
from regression_suite import Suite
from regression_traffic import owned_box_containers, read_endpoint_snapshot

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tests.e2e.utils.config_factory import create_minimal_config, create_test_directories  # noqa: E402


def ready(url, processes, timeout=120):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if any(p.poll() is not None for p in processes):
            raise RuntimeError('A smoke dependency exited; inspect service logs')
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
        log = (root / f'{name}.log').open('w')
        logs.append(log)
        process = subprocess.Popen(
            command, cwd=private, env=env, stdout=log, stderr=subprocess.STDOUT, start_new_session=True
        )
        processes.append(process)
        return process.pid

    try:
        published = None
        if args.plugins is None:
            published = prepare_published_plugins(root / 'plugins', args.plugin_manifest)
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
        profile_path = ROOT / 'tools/regression_profiles/smoke.json'
        profile = json.loads(profile_path.read_text())
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
        # Two turns retain the history/isolation oracle while leaving room for setup and cleanup.
        profile['smoke']['group_turns'] = 2
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
        for url in profile['observe']['health'].values():
            ready(url, processes)
        preparation = root / 'preparation'
        preparation.mkdir()
        suite = Suite(profile, profile_path, preparation, env)
        identity = suite.call(['whoami'])
        # Bind the CLI to the newly bootstrapped Workspace before installing plugins.
        cli_data = yaml.safe_load(cli_config.read_text())
        cli_data['contexts']['smoke']['expected_workspace_uuid'] = identity['workspace_uuid']
        cli_config.write_text(yaml.safe_dump(cli_data))
        if published is not None:
            install_published_plugins(suite.call, root / 'plugins', published)
        else:
            for directory in ('Runner/LocalAgent', 'KnowledgeEngine/LangRAG', 'misc/GeneralParsers'):
                source = args.plugins / directory
                package_source = private / source.name
                shutil.copytree(source, package_source, ignore=shutil.ignore_patterns('.git', '.venv*', '__pycache__'))
                archive = shutil.make_archive(str(private / source.name), 'zip', root_dir=package_source)
                suite.call(['plugin', 'install', 'local', '--file', archive, '--wait'])
        generated = private / 'smoke.json'
        generated.write_text(json.dumps(profile, indent=2))
        return supervise(
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
            60,
            pids,
            env,
        )
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
    plugins.add_argument('--plugins', type=Path, help='Explicit developer override: package a plugin source checkout')
    plugins.add_argument('--plugin-manifest', type=Path, help='Replay published versions and hashes from a prior run')
    args = parser.parse_args()
    if args.output.exists():
        parser.error('--output must be a new directory')
    try:
        result = run(args)
    except Exception as exc:
        verdict = args.output / 'gate' / 'gate.json'
        result = json.loads(verdict.read_text()) if verdict.exists() else {}
        result.update(passed=False, infrastructure_error=f'{type(exc).__name__}: {exc}')
        verdict.parent.mkdir(parents=True, exist_ok=True)
        verdict.write_text(json.dumps(result, indent=2) + '\n')
        raise
    print(json.dumps(result, indent=2))
    raise SystemExit(0 if result['passed'] else 1)


if __name__ == '__main__':
    main()
