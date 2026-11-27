"""Run opt-in public RAG experiments on a disposable Linux LangBot and Chroma."""

import argparse
from contextlib import ExitStack, contextmanager
from hashlib import file_digest, sha256
from importlib.metadata import PackageNotFoundError, version
import json
import os
from pathlib import Path
import platform
import secrets
import shutil
import signal
import subprocess
import sys
import time
import urllib.error
import urllib.request
from uuid import UUID

import yaml

from tests.e2e.utils.config_factory import create_minimal_config, create_test_directories
from tools.entrypoints.regression_ci import HOST_RUNTIME, ROOT, allocate_ports, host_environment, ready
from tools.regression.vdb_benchmark_public import ASSETS, MODEL as PUBLIC_MODEL, plan
from tools.regression.vdb_public_assets import fetch_asset
from tools.regression.regression_plugins import package_marketplace, prepare_source_plugins

PUBLIC_RUNNER = 'tools.entrypoints.vdb_benchmark_public'
UPLOAD_RUNNER = 'tools.entrypoints.vdb_benchmark_upload'
TOKEN_ENV = 'LANGBOT_QA_VDB_TOKEN'


def wheelhouse_signature(path):
    digest = sha256()
    wheels = sorted(wheel for wheel in path.glob('*.whl') if wheel.is_file())
    if not wheels:
        raise ValueError('Supply a local plugin dependency wheelhouse (--plugin-wheelhouse)')
    for wheel in wheels:
        with wheel.open('rb') as source:
            digest.update(wheel.name.encode() + b'\0' + file_digest(source, 'sha256').digest())
    return digest.hexdigest()


def installed_versions(dependencies):
    versions = {}
    for dependency in dependencies:
        try:
            versions[dependency] = version(dependency)
        except PackageNotFoundError as exc:
            raise ValueError(f'Missing benchmark dependency: {dependency}; see tools/vdb-benchmark-public.md') from exc
    return versions


def core_config(config, private, ports, marketplace):
    config['vdb'] = {'use': 'chroma', 'chroma': {'path': str(private / 'chroma')}}
    config['api'].update(host='127.0.0.1')
    config['system']['jwt']['secret'] = secrets.token_urlsafe(32)
    config['plugin'].update(enable=True, runtime_ws_url=f'ws://127.0.0.1:{ports["runtime"]}/control/ws')
    config['space'].update(url=marketplace, disable_telemetry=True, disable_models_service=True)
    config['box']['enabled'] = False
    return config


class LocalAPI:
    def __init__(self, endpoint):
        self.endpoint = endpoint
        self.opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        self.headers = {}

    def call(self, method, path, body=None):
        data = None if body is None else json.dumps(body).encode()
        request = urllib.request.Request(
            self.endpoint + path,
            data=data,
            headers={**self.headers, 'Content-Type': 'application/json'},
            method=method,
        )
        try:
            with self.opener.open(request, timeout=30) as result:
                envelope = json.load(result)
        except urllib.error.HTTPError as exc:
            # Do not include a response body that could echo provisioning secrets.
            raise RuntimeError(f'Core setup {method} {path}: HTTP {exc.code}') from None
        if not isinstance(envelope, dict) or envelope.get('code') != 0:
            raise RuntimeError(f'Core setup rejected {method} {path}')
        return envelope.get('data') or {}

    def initialize(self):
        credentials = {'user': 'vdb-benchmark@langbot.test', 'password': secrets.token_urlsafe(32)}
        self.call('POST', '/api/v1/user/init', credentials)
        token = self.call('POST', '/api/v1/user/auth', credentials)['token']
        self.headers['Authorization'] = 'Bearer ' + token
        workspaces = self.call('GET', '/api/v1/workspaces')['workspaces']
        if len(workspaces) != 1:
            raise RuntimeError('Fresh local benchmark Core must return exactly one Workspace')
        workspace = str(UUID(workspaces[0]['uuid']))
        self.headers['X-Workspace-Id'] = workspace
        return token, workspace

    def install(self, manifest):
        for package in manifest['plugins']:
            author, name = package['id'].split('/')
            task = self.call(
                'POST',
                '/api/v1/plugins/install/marketplace',
                {
                    'plugin_author': author,
                    'plugin_name': name,
                    'plugin_version': package['version'],
                    'auto_confirm_permissions': True,
                },
            )['task_id']
            deadline = time.monotonic() + 180
            while time.monotonic() < deadline:
                state = self.call('GET', f'/api/v1/system/tasks/{task}')['runtime']
                if state.get('done'):
                    if state.get('exception'):
                        raise RuntimeError(f'Benchmark fixture installation failed: {package["id"]}')
                    break
                time.sleep(0.2)
            else:
                raise TimeoutError(f'Benchmark fixture installation timed out: {package["id"]}')
            while time.monotonic() < deadline:
                matches = []
                for plugin in self.call('GET', '/api/v1/plugins')['plugins']:
                    metadata = plugin.get('manifest', {}).get('manifest', {}).get('metadata', {})
                    if (metadata.get('author'), metadata.get('name')) == (author, name):
                        matches.append((metadata.get('version'), plugin.get('enabled'), plugin.get('status')))
                if matches == [(package['version'], True, 'initialized')]:
                    break
                time.sleep(0.2)
            else:
                raise RuntimeError(f'Benchmark fixture never became ready: {package["id"]}')

    def embedding_model(self, port, name):
        provider = self.call(
            'POST',
            '/api/v1/provider/providers',
            {
                'name': 'QA private local embedding',
                'requester': 'openai-chat-completions',
                'base_url': f'http://127.0.0.1:{port}/v1',
                'api_keys': ['qa-local-only'],
            },
        )['uuid']
        return str(
            UUID(
                self.call(
                    'POST',
                    '/api/v1/provider/models/embedding',
                    {
                        'name': name,
                        'provider_uuid': provider,
                    },
                )['uuid']
            )
        )


@contextmanager
def local_processes(root, private, env):
    with ExitStack() as stack:
        processes = []

        def stop(process):
            if process.poll() is None:
                try:
                    os.killpg(process.pid, signal.SIGTERM)
                except ProcessLookupError:
                    pass
                try:
                    process.wait(timeout=8)
                except subprocess.TimeoutExpired:
                    try:
                        os.killpg(process.pid, signal.SIGKILL)
                    except ProcessLookupError:
                        pass
                    process.wait(timeout=8)

        def start(name, *args):
            logfile = stack.enter_context((root / f'{name}.log').open('x', encoding='utf-8'))
            process = subprocess.Popen(
                [sys.executable, *args],
                cwd=private,
                env=env,
                stdout=logfile,
                stderr=subprocess.STDOUT,
                start_new_session=True,
            )
            stack.callback(stop, process)
            processes.append(process)
            return process

        yield start, processes


def write_json(path, data):
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    temporary.replace(path)


def run_trial(args, location, package_dir, packages, core_sha):
    location.mkdir(mode=0o700)
    private = location / '.private'
    private.mkdir(mode=0o700)
    ports = allocate_ports()
    env = host_environment(private, args.plugin_wheelhouse)
    env.update(
        LANGBOT_DATA_ROOT=str(private / 'data'),
        LANGBOT_PLUGIN_RUNTIME_CONTROL_TOKEN=secrets.token_urlsafe(32),
        PYTHONPATH=os.pathsep.join((str(ROOT), str(ROOT / 'src'))),
        LITELLM_LOCAL_MODEL_COST_MAP='True',
        PYTHONUNBUFFERED='1',
        PATH=os.pathsep.join((str(Path(sys.executable).parent), env.get('PATH', os.defpath))),
    )
    versions = {
        'python': sys.version.split()[0],
        'architecture': platform.machine(),
        'wheelhouse-sha256': args.wheelhouse_sha256,
        'logical-cpus': str(os.process_cpu_count() if hasattr(os, 'process_cpu_count') else os.cpu_count()),
        'langbot': version('langbot'),
        'langbot-plugin': version('langbot-plugin'),
    }
    versions.update(args.backend_versions)
    for plugin in packages['plugins']:
        versions[plugin['id'].split('/')[-1]] = plugin['version']
        versions[plugin['id'].split('/')[-1] + '-archive-sha256'] = plugin['sha256']
    provenance = location / 'provenance.json'
    write_json(
        provenance,
        {
            'backend': 'chroma',
            'mode': 'local',
            'core_sha': core_sha,
            'versions': versions,
        },
    )
    endpoint = f'http://127.0.0.1:{ports["core"]}'
    upload_memory = args.suite == 'rss'
    mapping_every = getattr(args, 'memory_mapping_every', 0)
    observe_memory = upload_memory or getattr(args, 'measure_memory', False) or mapping_every > 0
    with (
        package_marketplace(package_dir, packages) as marketplace,
        local_processes(location, private, env) as (start, processes),
    ):
        config_path = create_minimal_config(private, port=ports['core'])
        create_test_directories(private)
        config = core_config(yaml.safe_load(config_path.read_text()), private, ports, marketplace)
        config_path.write_text(yaml.safe_dump(config), encoding='utf-8')
        config_path.chmod(0o600)
        if upload_memory:
            embedder = start('embedder', '-m', 'tools.entrypoints.mock_llm', '--port', str(ports['mock']))
        else:
            embedder = start(
                'embedder',
                '-m',
                'tools.entrypoints.vdb_benchmark_minilm',
                '--assets',
                str(args.asset_cache),
                '--port',
                str(ports['mock']),
            )
        runtime = start(
            'runtime',
            '-c',
            HOST_RUNTIME,
            'rt',
            '--ws-control-port',
            str(ports['runtime']),
            '--ws-debug-port',
            str(ports['debug']),
        )
        ready(f'http://127.0.0.1:{ports["mock"]}/healthz', processes)
        ready(f'http://127.0.0.1:{ports["runtime"]}/healthz', processes)
        core_args = [str(ROOT / 'main.py'), '--standalone-runtime']
        if getattr(args, 'core_memray', False):
            if args.memray_site:
                env['PYTHONPATH'] = str(args.memray_site) + os.pathsep + env['PYTHONPATH']
            core_args[:0] = [
                '-m',
                'memray',
                'run',
                '--aggregate',
                '--native',
                '-o',
                str(location / 'core-allocations.bin'),
            ]
        core = start('core', *core_args)
        ready(endpoint + '/healthz', processes)
        api = LocalAPI(endpoint)
        token, workspace = api.initialize()
        api.install(packages)
        model = api.embedding_model(ports['mock'], 'mock-embedding' if upload_memory else PUBLIC_MODEL)
        # Launch last; the child will drain before owned Core/Runtime are stopped.
        env[TOKEN_ENV] = token
        result = location / 'result'
        with ExitStack() as monitor:
            sampler = None
            if observe_memory:
                from tools.regression.vdb_benchmark_memory import MemorySampler

                sampler = monitor.enter_context(
                    MemorySampler(
                        location / 'memory',
                        roots={'core': core.pid, 'runtime': runtime.pid, 'embedder': embedder.pid},
                        interval_seconds=0.10,
                        pss_every=10,
                        stage_events=result / 'stages.jsonl' if upload_memory else None,
                        mapping_every=mapping_every,
                        chroma_dir=private / 'data/chroma' if mapping_every else None,
                    )
                )
                sampler.mark('baseline')
                if not sampler.wait_for_samples('baseline', minimum=4, timeout=5):
                    raise RuntimeError('No complete owned-process memory baseline')
                sampler.mark('workload')
            workload = [
                '-m',
                UPLOAD_RUNNER if upload_memory else PUBLIC_RUNNER,
                'run',
                '--profile',
                str(args.profile),
                '--endpoint',
                endpoint,
                '--workspace',
                workspace,
                '--token-env',
                TOKEN_ENV,
                '--embedding-model',
                model,
                '--output',
                str(result),
            ]
            if upload_memory:
                workload.extend(['--public-corpus-manifest', str(args.public_corpus_manifest)])
            else:
                workload.extend(['--assets', str(args.asset_cache), '--provenance', str(provenance)])
            workload.extend(['--chroma-sqlite', str(private / 'data/chroma/chroma.sqlite3')])
            trial = start('benchmark', *workload)
            try:
                exit_code = trial.wait(timeout=args.trial_timeout)
            except subprocess.TimeoutExpired as exc:
                raise TimeoutError('Chroma benchmark exceeded the trial timeout') from exc
            if sampler:
                sampler.mark('recovery')
                if exit_code == 0 and not sampler.wait_for_samples('recovery', minimum=4, timeout=5):
                    raise RuntimeError('No complete owned-process memory recovery sample')
            return exit_code


def external_path(path, label):
    path = path.resolve()
    if path.is_relative_to(ROOT):
        raise ValueError(f'{label} must be outside the repository checkout')
    return path


def run(args):
    if not sys.platform.startswith('linux'):
        raise ValueError('The public RAG launcher requires a disposable Linux environment')
    args.asset_cache = external_path(args.asset_cache, '--asset-cache')
    args.output = external_path(args.output, '--output')
    upload_memory = args.suite == 'rss'
    dependencies = ('chromadb', 'pyarrow') if upload_memory else ('chromadb', 'onnxruntime', 'tokenizers', 'numpy')
    args.backend_versions = installed_versions(dependencies)
    args.wheelhouse_sha256 = wheelhouse_signature(args.plugin_wheelhouse)
    args.asset_cache.mkdir(mode=0o700, parents=True, exist_ok=True)
    if upload_memory:
        from tools.entrypoints.vdb_benchmark_upload import load_profile
        from tools.entrypoints.vdb_public_corpus import URL, WIKITEXT_SHA256, prepare

        profile = load_profile(args.profile)
        shard = fetch_asset(
            args.asset_cache, 'wikitext-103-train-00000.parquet', URL + '?download=true', WIKITEXT_SHA256, 160 * 1024**2
        )
    else:
        for name, (url, checksum) in ASSETS.items():
            fetch_asset(
                args.asset_cache,
                name,
                url + '?download=true' if name != 'scifact.zip' else url,
                checksum,
                100 * 1024**2,
            )
        plan(args.profile, args.asset_cache)
    core_sha = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True, timeout=10).strip()
    args.output.mkdir(mode=0o700)
    snapshot = args.output / 'profile.json'
    shutil.copyfile(args.profile, snapshot)
    args.profile = snapshot
    if upload_memory:
        replay = args.output / 'public-corpus'
        prepare(shard, profile, replay)
        args.public_corpus_manifest = replay / 'manifest.json'

    package_dir = args.output / 'plugins'
    packages = prepare_source_plugins(package_dir, args.plugins)
    status = []
    for i in range(1, args.repeats + 1):
        location = args.output / f'{i:02d}-chroma'
        row = {'repeat': i, 'backend': 'chroma', 'path': location.name, 'passed': False}
        try:
            code = run_trial(args, location, package_dir, packages, core_sha)
            row.update(exit_code=code, passed=code == 0)
        except (KeyError, OSError, RuntimeError, ValueError) as exc:
            row['error'] = f'{type(exc).__name__}: {exc}'
        status.append(row)
        write_json(args.output / 'trials.json', status)
    return all(row['passed'] for row in status)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--profile', type=Path, required=True)
    parser.add_argument(
        '--output', type=Path, required=True, help='New directory for reports and disposable fixture state'
    )
    parser.add_argument('--plugins', type=Path, default=ROOT / 'plugins', help='Trusted local LangBot fixture sources')
    parser.add_argument('--plugin-wheelhouse', type=Path, required=True)
    parser.add_argument('--suite', choices=('rss', 'scifact'), required=True)
    parser.add_argument(
        '--asset-cache',
        type=Path,
        default=Path.home() / '.cache/langbot/public-rag',
        help='Fetch or reuse hash-pinned public assets here',
    )
    parser.add_argument('--measure-memory', action='store_true', help='Sample owned Core and Runtime memory')
    parser.add_argument('--memory-mapping-every', type=int, default=0)
    parser.add_argument('--core-memray', action='store_true', help='Separate diagnostic allocation run, not for timing')
    parser.add_argument(
        '--memray-site', type=Path, help='Optional isolated directory containing the official Memray wheel'
    )
    parser.add_argument('--repeats', type=int, default=1, help='Fresh local deployment per repetition')
    parser.add_argument('--trial-timeout', type=int, default=900, help='Workload deadline in seconds')
    args = parser.parse_args(argv)
    if not 1 <= args.repeats <= 10 or not 30 <= args.trial_timeout <= 7200:
        parser.error('repeats must be 1..10 and trial-timeout 30..7200 seconds')
    if not 0 <= args.memory_mapping_every <= 100:
        parser.error('memory-mapping-every must be 0..100')
    if args.memray_site and not args.core_memray:
        parser.error('--memray-site requires --core-memray')
    for name in ('profile', 'output', 'plugins', 'plugin_wheelhouse', 'asset_cache', 'memray_site'):
        value = getattr(args, name)
        if value is not None:
            setattr(args, name, value.resolve())

    def interrupted(_signum, _frame):
        raise KeyboardInterrupt

    previous = signal.signal(signal.SIGTERM, interrupted)
    try:
        return 0 if run(args) else 1
    except KeyboardInterrupt:
        parser.exit(130, 'Public RAG benchmark interrupted. Do not treat partial evidence as a complete trial.\n')
    except (OSError, RuntimeError, ValueError, subprocess.SubprocessError) as exc:
        parser.exit(1, f'Local VDB benchmark setup failed: {exc}\n')
    finally:
        signal.signal(signal.SIGTERM, previous)


if __name__ == '__main__':
    raise SystemExit(main())
