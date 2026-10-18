"""Bounded real Core/RT/OneBot probe; no shared Docker access or external messages."""

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
source = Path(os.environ.get('LANG17_SOURCE', str(repo))).resolve()
root = repo.parent / 'evidence' / ('live-' + time.strftime('%Y%m%d-%H%M%S'))
root.mkdir(mode=0o700)
ports = [16399, 16400, 16401, 14000, 13280, 13281, 16420, 16410]
for port in ports:
    with socket.socket() as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind(('127.0.0.1', port))
env = {key: os.environ[key] for key in ('PATH', 'HOME', 'LANG') if key in os.environ}
for key in ('XDG_CACHE_HOME', 'UV_CACHE_DIR', 'TMPDIR'):
    path = root / key.lower()
    path.mkdir()
    env[key] = str(path)
env.update(
    LANGBOT_DATA_ROOT=str(root / 'data'),
    PYTHONPATH=str(source / 'src'),
    PYTHONUNBUFFERED='1',
    PLAYWRIGHT_BROWSERS_PATH=str(repo.parent / 'evidence/playwright-browsers'),
    NO_PROXY='127.0.0.1,localhost',
    LANGBOT_PLUGIN_RUNTIME_CONTROL_TOKEN=secrets.token_hex(32),
    VITE_API_PROXY_TARGET='http://127.0.0.1:16399',
    LANG17_BASE='1' if source != repo else '',
    DOCKER_HOST='unix://' + str(root / 'nonexistent-docker.sock'),
)
config = yaml.safe_load((source / 'src/langbot/templates/config.yaml').read_text())
config['api'].update(host='127.0.0.1', port=16399, webhook_prefix='http://127.0.0.1:16399')
config['plugin'].update(runtime_ws_url='ws://127.0.0.1:16400/control/ws')
config['box']['enabled'] = bool(os.environ.get('LANG17_BOX_ROOT'))
if os.environ.get('LANG17_BOX_ROOT'):
    env['PATH'] = str(Path(os.environ['LANG17_DOCKER_BIN']).resolve()) + os.pathsep + env['PATH']
    env['LANG17_TOOL'] = '1'
    env['LANGBOT_BOX_CONTROL_TOKEN'] = secrets.token_hex(32)
    config['box']['backend'] = 'docker'
    config['box']['runtime']['endpoint'] = 'ws://127.0.0.1:16410'
    config['box']['local']['host_root'] = str(Path(os.environ['LANG17_BOX_ROOT']).resolve())
    config['box']['local']['allowed_mount_roots'] = [config['box']['local']['host_root']]
    config['box']['local']['image'] = 'alpine:3.21'
    config['box']['limits']['max_sessions'] = 1
    config['box']['default_memory_mb'] = 256
config['space']['disable_telemetry'] = True
if os.environ.get('LANG17_NETWORK'):
    config['space']['url'] = 'http://127.0.0.1:16420'
    config['space']['disable_models_service'] = True
config['database']['sqlite']['path'] = str(root / 'data/langbot.db')
(root / 'data').mkdir()
if os.environ.get('LANG17_SEED_DB'):
    import shutil

    seed = Path(os.environ['LANG17_SEED_DB'])
    shutil.copy2(seed, root / 'data/langbot.db')
    shutil.copytree(seed.parent / 'labels', root / 'data/labels')
    env['LANG17_UPGRADE_ACCOUNT'] = str(Path(os.environ['LANG17_UPGRADE_ACCOUNT']).resolve())
(root / 'data/config.yaml').write_text(yaml.safe_dump(config))
for key in ('LANG17_LISTENERS', 'LANG17_SHORT', 'LANG17_SOAK_ROUNDS', 'LANG17_BOUND', 'LANG17_INSTALL'):
    if key in os.environ:
        env[key] = os.environ[key]
duration = int(os.environ.get('LANG17_SECONDS', '150'))
owned, logs, children = {}, [], []
result = {
    'sha': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=source, text=True).strip(),
    'limits': {'rss_bytes': 2 * 1024**3, 'cpu_percent': 200, 'hot_samples': 5, 'seconds': duration},
    'box': 'isolated daemon via task Docker wrapper' if os.environ.get('LANG17_BOX_ROOT') else 'disabled',
    'samples': [],
    'health': {},
}


def launch(role, command, cwd):
    log = (root / (role + '.log')).open('w')
    logs.append(log)
    child = subprocess.Popen(command, cwd=cwd, env=env, stdout=log, stderr=subprocess.STDOUT)
    children.append(child)
    owned[child.pid] = (role, psutil.Process(child.pid))
    return child


try:
    launch(
        'rt',
        [sys.executable, '-m', 'langbot_plugin.cli', 'rt', '--ws-control-port', '16400', '--ws-debug-port', '16401'],
        root,
    )
    if os.environ.get('LANG17_BOX_ROOT'):
        launch(
            'box',
            [sys.executable, '-m', 'langbot_plugin.cli', 'box', '--host', '127.0.0.1', '--ws-control-port', '16410'],
            root,
        )
    core = launch(
        'core',
        [sys.executable, str(source / 'main.py'), '--standalone-runtime']
        + (['--standalone-box'] if os.environ.get('LANG17_BOX_ROOT') else []),
        root,
    )
    launch(
        'web',
        [str(repo / 'web/node_modules/.bin/vite'), 'preview', '--host', '127.0.0.1', '--port', '14000', '--strictPort'],
        repo / 'web',
    )
    started, hot, probe = time.monotonic(), 0, None
    while time.monotonic() - started < duration:
        if core.poll() is not None:
            raise RuntimeError('Core exited')
        for role, parent in list(owned.values()):
            try:
                for child in parent.children(recursive=True):
                    owned.setdefault(child.pid, (role.split('-child')[0] + '-child', child))
            except psutil.NoSuchProcess:
                pass
        rows = []
        for pid, (role, proc) in list(owned.items()):
            try:
                rows.append(
                    {
                        'pid': pid,
                        'role': role,
                        'rss': proc.memory_info().rss,
                        'cpu': proc.cpu_percent(),
                        'fds': proc.num_fds(),
                        'threads': proc.num_threads(),
                    }
                )
            except psutil.NoSuchProcess:
                pass
        sample = {'seconds': round(time.monotonic() - started, 2), 'processes': rows}
        for role, port in [('core', 16399), ('rt', 16400), ('web', 14000)]:
            try:
                with urllib.request.urlopen(
                    f'http://127.0.0.1:{port}' + ('/' if role == 'web' else '/healthz'), timeout=0.5
                ) as response:
                    body = response.read()
                    result['health'][role] = response.status
                    if role != 'web':
                        sample[role] = json.loads(body)
            except Exception:
                pass
        result['samples'].append(sample)
        # Include a short idle baseline before synthetic OneBot traffic.
        if probe is None and len(result['health']) == 3 and sample['seconds'] >= 25:
            probe = launch(
                'probe',
                [
                    sys.executable,
                    str(
                        repo
                        / (
                            'tests/manual/lang17_upgrade.py'
                            if os.environ.get('LANG17_SEED_DB')
                            else (
                                'tests/manual/lang17_localagent.py'
                                if os.environ.get('LANG17_LOCALAGENT')
                                else (
                                    'tests/manual/lang17_matrix.py'
                                    if os.environ.get('LANG17_MATRIX')
                                    else (
                                        'tests/manual/lang17_network.py'
                                        if os.environ.get('LANG17_NETWORK')
                                        else (
                                            'tests/manual/lang17_install.py'
                                            if os.environ.get('LANG17_INSTALL')
                                            else 'tests/manual/lang17_onebot.py'
                                        )
                                    )
                                )
                            )
                        )
                    ),
                ]
                + (['--fault'] if os.environ.get('LANG17_FAULT') else []),
                root,
            )
        if probe is not None and probe.poll() is not None:
            result['probe_exit_code'] = probe.returncode
            if time.monotonic() - started >= int(os.environ.get('LANG17_MIN_SECONDS', '70')):
                break
        hot = hot + 1 if sum(row['cpu'] for row in rows) > 200 else 0
        if sum(row['rss'] for row in rows) > 2 * 1024**3 or hot >= 5:
            raise RuntimeError('Resource threshold')
        time.sleep(2)
finally:
    daemon = json.loads(subprocess.check_output(['multica', 'daemon', 'status', '--output', 'json']))['pid']
    for pid, (_, proc) in reversed(list(owned.items())):
        assert pid != daemon
        try:
            proc.terminate()
        except psutil.NoSuchProcess:
            pass
    _, alive = psutil.wait_procs([proc for _, proc in owned.values()], timeout=8)
    for proc in alive:
        assert proc.pid != daemon
        proc.kill()
    psutil.wait_procs(alive, timeout=3)
    for child in children:
        child.wait(timeout=3)
    for log in logs:
        log.close()
    result['survivors'] = [pid for pid, (_, proc) in owned.items() if proc.is_running()]
    (root / 'metrics.json').write_text(json.dumps(result, indent=2))
    print(
        json.dumps(
            {
                'directory': root.name,
                'health': result['health'],
                'probe_exit_code': result.get('probe_exit_code'),
                'survivors': result['survivors'],
            }
        )
    )

if result.get('probe_exit_code') != 0:
    raise SystemExit('Probe failed or exceeded its deadline')
