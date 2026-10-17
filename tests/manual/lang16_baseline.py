"""Bounded local startup probe; never uses an existing deployment's data."""

import json
import os
from pathlib import Path
import secrets
import socket
import subprocess
import sys
import time
import urllib.request

import psutil
import yaml


repo = Path(__file__).resolve().parents[2]
root = repo.parent / 'evidence' / ('baseline-' + time.strftime('%Y%m%d-%H%M%S'))
root.mkdir(parents=True, mode=0o700)
ports = [15399, 15400, 15401, 15410, 13000]
if os.environ.get('LANG16_ONEBOT') == '1':
    ports.append(12280)
if os.environ.get('LANG16_NETWORK') == '1':
    ports.append(15420)
if os.environ.get('LANG16_MATRIX') == '1':
    ports.extend([12280, 12281])
if os.environ.get('LANG16_UPGRADE'):
    ports.append(12280)
if os.environ.get('LANG16_SEED_DB'):
    ports.extend([12280, 12281])
ports = sorted(set(ports))
for port in ports:
    with socket.socket() as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind(('127.0.0.1', port))
env = {k: os.environ[k] for k in ('PATH', 'HOME', 'LANG', 'SYSTEMROOT') if k in os.environ}
for key in ('XDG_CACHE_HOME', 'UV_CACHE_DIR', 'TMPDIR'):
    directory = root / key.lower()
    directory.mkdir()
    env[key] = str(directory)
env.update(
    LANGBOT_DATA_ROOT=str(root / 'data'),
    PYTHONUNBUFFERED='1',
    NO_PROXY='127.0.0.1,localhost',
    LANGBOT_PLUGIN_RUNTIME_CONTROL_TOKEN=secrets.token_hex(32),
    VITE_API_PROXY_TARGET='http://127.0.0.1:15399',
)
core_source = Path(os.environ.get('LANG16_CORE_SOURCE', str(repo))).resolve()
env['PYTHONPATH'] = str(core_source / 'src')
core_python = os.environ.get('LANG16_CORE_PYTHON', sys.executable)
config = yaml.safe_load((core_source / 'src/langbot/templates/config.yaml').read_text())
config['api'].update(host='127.0.0.1', port=15399, webhook_prefix='http://127.0.0.1:15399')
config['plugin'].update(
    runtime_ws_url='ws://127.0.0.1:15400/control/ws', display_plugin_debug_url='ws://127.0.0.1:15401/plugin/debug/ws'
)
config['space']['disable_telemetry'] = True
if os.environ.get('LANG16_NETWORK') == '1':
    config['space']['url'] = 'http://127.0.0.1:15420'
    config['space']['disable_models_service'] = True
config['box']['runtime']['endpoint'] = 'ws://127.0.0.1:15410'
if os.environ.get('LANG16_BOX') == '1':
    config['box']['backend'] = 'docker'
    config['box']['local']['host_root'] = str(root / 'data/box')
    config['box']['local']['allowed_mount_roots'] = [str(root / 'data/box')]
    config['box']['limits']['max_sessions'] = 1
    config['box']['default_memory_mb'] = 256
config['database']['sqlite']['path'] = str(root / 'data/langbot.db')
(root / 'data').mkdir()
if os.environ.get('LANG16_SEED_DB'):
    import shutil

    seed = Path(os.environ['LANG16_SEED_DB'])
    shutil.copy2(seed, root / 'data/langbot.db')
    # Preserve this synthetic instance's identity as a real data-directory upgrade does.
    (root / 'data/labels').mkdir()
    shutil.copy2(seed.parent / 'labels/instance_id.json', root / 'data/labels/instance_id.json')
(root / 'data/config.yaml').write_text(yaml.safe_dump(config))
rss_limit = (3 if os.environ.get('LANG16_NETWORK') == '1' else 2) * 1024**3
owned = {}
handles = []
samples = []
result = {
    'sha': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=core_source, text=True).strip(),
    'core_source': str(core_source),
    'ports': ports,
    'limits': {'rss_bytes': rss_limit, 'cpu_percent': 200, 'cpu_samples': 5},
    'health': {},
    'reason': 'duration_complete',
}


def launch(name, args, cwd):
    log = (root / (name + '.log')).open('w')
    handles.append(log)
    child_env = dict(env)
    if name == 'network' and os.environ.get('LANG16_NETWORK_UI_ONLY'):
        child_env['LANG16_NETWORK_UI_ONLY'] = os.environ['LANG16_NETWORK_UI_ONLY']
    if name == 'upgrade':
        for key in ('LANG16_UPGRADE', 'LANG16_UPGRADE_ACCOUNT'):
            if key in os.environ:
                child_env[key] = os.environ[key]
    if name == 'matrix' and os.environ.get('LANG16_BOUND'):
        child_env['LANG16_BOUND'] = os.environ['LANG16_BOUND']
    if name == 'matrix' and os.environ.get('LANG16_CANCEL'):
        child_env['LANG16_CANCEL'] = os.environ['LANG16_CANCEL']
    if name == 'matrix' and os.environ.get('LANG16_SOAK_ROUNDS'):
        child_env['LANG16_SOAK_ROUNDS'] = os.environ['LANG16_SOAK_ROUNDS']
    if name == 'onebot':
        for key in ('LANG16_LLM_KEY', 'LANG16_LLM_MODEL', 'LANG16_LLM_BASE_URL', 'LANG16_PLUGIN_PACKAGE'):
            if key in os.environ:
                child_env[key] = os.environ[key]
    proc = subprocess.Popen(args, cwd=cwd, env=child_env, stdout=log, stderr=subprocess.STDOUT)
    owned[proc.pid] = (name, psutil.Process(proc.pid))
    return proc


try:
    rt_process = launch(
        'rt',
        [core_python, '-m', 'langbot_plugin.cli', 'rt', '--ws-control-port', '15400', '--ws-debug-port', '15401'],
        root,
    )
    launch(
        'box',
        [core_python, '-m', 'langbot_plugin.cli', 'box', '--host', '127.0.0.1', '--ws-control-port', '15410'],
        root,
    )
    core_process = launch(
        'core', [core_python, str(core_source / 'main.py'), '--standalone-runtime', '--standalone-box'], root
    )
    launch(
        'web',
        [str(repo / 'web/node_modules/.bin/vite'), '--host', '127.0.0.1', '--port', '13000', '--strictPort'],
        repo / 'web',
    )
    start = time.monotonic()
    result['started_monotonic'] = start
    hot = 0
    ui_started = False
    onebot_started = False
    rt_stopped = False
    rt_restarted = False
    install_started = False
    network_started = False
    matrix_started = False
    upgrade_started = False
    while time.monotonic() - start < min(900, int(os.environ.get('LANG16_SECONDS', '90'))):
        if core_process.poll() is not None:
            result['reason'] = 'core_exited'
            break
        for parent_role, parent in list(owned.values()):
            try:
                for child in parent.children(recursive=True):
                    owned.setdefault(child.pid, (parent_role.split('-child')[0] + '-child', child))
            except psutil.NoSuchProcess:
                pass
        rows = []
        for pid, (name, proc) in owned.items():
            try:
                rows.append(
                    {
                        'pid': pid,
                        'role': name,
                        'rss': proc.memory_info().rss,
                        'cpu': proc.cpu_percent(),
                        'threads': proc.num_threads(),
                        'fds': proc.num_fds(),
                    }
                )
            except psutil.NoSuchProcess:
                pass
        sample = {'seconds': round(time.monotonic() - start, 2), 'processes': rows}
        sample['probes'] = {}
        samples.append(sample)
        for name, port, path in [
            ('core', 15399, '/healthz'),
            ('rt', 15400, '/healthz'),
            ('box', 15410, '/healthz'),
            ('web', 13000, '/'),
        ]:
            try:
                with urllib.request.urlopen(f'http://127.0.0.1:{port}{path}', timeout=0.5) as response:
                    body = response.read()
                    entry = {'status': response.status, 'seconds': sample['seconds']}
                    if name != 'web':
                        entry['body'] = json.loads(body)
                    result['health'][name] = entry
                    sample['probes'][name] = entry
            except Exception:
                sample['probes'][name] = {'status': None}
        if os.environ.get('LANG16_RT_FAULT') == '1':
            if sample['seconds'] >= 20 and not rt_stopped:
                daemon_pid = json.loads(subprocess.check_output(['multica', 'daemon', 'status', '--output', 'json']))[
                    'pid'
                ]
                if rt_process.pid == daemon_pid:
                    raise RuntimeError('Refusing to terminate daemon')
                rt_process.terminate()
                rt_stopped = True
            if sample['seconds'] >= 27 and rt_stopped and not rt_restarted:
                if rt_process.poll() is None:
                    raise RuntimeError('Original owned RT has not stopped')
                rt_process = launch(
                    'rt-restarted',
                    [
                        sys.executable,
                        '-m',
                        'langbot_plugin.cli',
                        'rt',
                        '--ws-control-port',
                        '15400',
                        '--ws-debug-port',
                        '15401',
                    ],
                    root,
                )
                rt_restarted = True
        if os.environ.get('LANG16_UI') == '1' and not ui_started and {'core', 'web'} <= result['health'].keys():
            launch('ui', ['node', str(repo / 'tests/manual/lang16_ui.mjs')], root)
            ui_started = True
        if (
            os.environ.get('LANG16_ONEBOT') == '1'
            and not onebot_started
            and {'core', 'rt', 'box'} <= result['health'].keys()
        ):
            args = [sys.executable, str(repo / 'tests/manual/lang16_onebot.py')]
            if os.environ.get('LANG16_BOX') == '1':
                args.append('--box')
            if os.environ.get('LANG16_RUNNER') == '1':
                args.append('--installed')
            if os.environ.get('LANG16_FAULT') == '1':
                args.append('--fault')
            launch('onebot', args, root)
            onebot_started = True
        if (
            os.environ.get('LANG16_INSTALL')
            and not install_started
            and {'core', 'rt', 'box'} <= result['health'].keys()
        ):
            launch(
                'install',
                [sys.executable, str(repo / 'tests/manual/lang16_install.py'), os.environ['LANG16_INSTALL']],
                root,
            )
            install_started = True
        if (
            os.environ.get('LANG16_NETWORK') == '1'
            and not network_started
            and {'core', 'rt'} <= result['health'].keys()
        ):
            launch('network', [sys.executable, str(repo / 'tests/manual/lang16_network.py')], root)
            network_started = True
        if os.environ.get('LANG16_MATRIX') == '1' and not matrix_started and {'core', 'rt'} <= result['health'].keys():
            launch('matrix', [sys.executable, str(repo / 'tests/manual/lang16_matrix.py')], root)
            matrix_started = True
        if os.environ.get('LANG16_UPGRADE') and not upgrade_started and {'core', 'rt'} <= result['health'].keys():
            launch('upgrade', [sys.executable, str(repo / 'tests/manual/lang16_upgrade.py')], root)
            upgrade_started = True
        if upgrade_started and (root / 'upgrade-result.json').exists():
            result['reason'] = 'upgrade_probe_finished'
            break
        if os.environ.get('LANG16_CANCEL') == '1' and (root / 'cancel-ready').exists():
            # This is the recorded task-owned core, never an existing service.
            daemon_pid = json.loads(subprocess.check_output(['multica', 'daemon', 'status', '--output', 'json']))['pid']
            if core_process.pid == daemon_pid:
                raise RuntimeError('Refusing to terminate daemon')
            core_process.terminate()
            try:
                core_process.wait(timeout=10)
                result['reason'] = 'cancellation_probe_finished'
            except subprocess.TimeoutExpired:
                result['reason'] = 'cancellation_shutdown_timeout'
            break
        if matrix_started and (root / 'matrix-finished').exists():
            result['reason'] = 'matrix_probe_finished'
            break
        if network_started and (root / 'network-finished').exists():
            result['reason'] = 'network_probe_finished'
            break
        if install_started and (root / 'install-result.json').exists():
            result['reason'] = 'install_probe_finished'
            break
        hot = hot + 1 if sum(row['cpu'] for row in rows) > 200 else 0
        if sum(row['rss'] for row in rows) > rss_limit or hot >= 5:
            result['reason'] = 'resource_threshold'
            break
        time.sleep(2)
finally:
    daemon = json.loads(subprocess.check_output(['multica', 'daemon', 'status', '--output', 'json']))['pid']
    for pid, (_, proc) in reversed(list(owned.items())):
        if pid == daemon:
            raise RuntimeError('Refusing to terminate daemon')
        try:
            if proc.is_running():
                proc.terminate()
        except psutil.NoSuchProcess:
            pass
    _, alive = psutil.wait_procs([p for _, p in owned.values()], timeout=8)
    for proc in alive:
        if proc.pid != daemon and proc.is_running():
            proc.kill()
    psutil.wait_procs(alive, timeout=3)
    # Only containers whose bind mounts are inside this newly-created probe
    # directory belong to this run; unrelated containers must never be stopped.
    if os.environ.get('LANG16_BOX') == '1':
        ids = subprocess.check_output(['docker', 'ps', '-aq'], text=True).split()
        owned_containers = []
        for cid in ids:
            mounts = json.loads(subprocess.check_output(['docker', 'inspect', '--format', '{{json .Mounts}}', cid]))
            if any(str(m.get('Source', '')).startswith(str(root) + '/') for m in mounts):
                owned_containers.append(cid)
        result['owned_containers'] = owned_containers
        for cid in owned_containers:
            subprocess.run(['docker', 'rm', '-f', cid], check=True, stdout=subprocess.DEVNULL)
    for handle in handles:
        handle.close()
    if os.environ.get('LANG16_LLM_KEY'):
        # Remove the task-owned credential database, including SQLite journals.
        for database_file in (root / 'data').glob('langbot.db*'):
            database_file.unlink()
        for log_file in root.glob('*.log'):
            log_file.write_text(log_file.read_text().replace(os.environ['LANG16_LLM_KEY'], '[REDACTED]'))
    if os.environ.get('LANG16_CANCEL') == '1' or os.environ.get('LANG16_SEED_DB'):
        import sqlite3

        with sqlite3.connect(root / 'data/langbot.db') as db:
            result['post_shutdown_messages'] = list(
                db.execute('select role,status,message_content from monitoring_messages order by timestamp')
            )
    result['samples'] = samples
    result['owned_pids'] = list(owned)
    result['survivors'] = [pid for pid, (_, p) in owned.items() if p.is_running()]
    (root / 'metrics.json').write_text(json.dumps(result, indent=2))
    print(
        json.dumps(
            {
                'evidence': str(root),
                'reason': result['reason'],
                'health': result['health'],
                'survivors': result['survivors'],
            },
            indent=2,
        )
    )
