"""Run media contracts in a recorded, bounded, disposable PostgreSQL container."""

import json
import os
from pathlib import Path
import secrets
import socket
import subprocess
import sys
import time

repo = Path(__file__).resolve().parents[2]
evidence = repo.parent / 'evidence'
with socket.socket() as sock:
    sock.bind(('127.0.0.1', 0))
    port = sock.getsockname()[1]
password = secrets.token_hex(20)
env = dict(os.environ, POSTGRES_PASSWORD=password)
cid = subprocess.check_output(
    [
        'docker',
        'run',
        '-d',
        '--name',
        'lang17-pg-' + secrets.token_hex(4),
        '--label',
        'qa.task=LANG-17',
        '--memory',
        '512m',
        '--cpus',
        '1',
        '--pids-limit',
        '128',
        '-e',
        'POSTGRES_PASSWORD',
        '-p',
        f'127.0.0.1:{port}:5432',
        'pgvector/pgvector:pg16',
    ],
    env=env,
    text=True,
).strip()
(evidence / 'owned-postgres.json').write_text(json.dumps({'id': cid, 'port': port}))
try:
    for _ in range(30):
        ready = subprocess.run(['docker', 'exec', cid, 'pg_isready', '-U', 'postgres'], capture_output=True)
        if ready.returncode == 0:
            break
        time.sleep(1)
    else:
        raise RuntimeError('PostgreSQL startup timeout')
    env['TEST_POSTGRES_URL'] = f'postgresql+asyncpg://postgres:{password}@127.0.0.1:{port}/postgres'
    with (evidence / 'integration-postgres.log').open('w') as log:
        run = subprocess.run(
            [
                sys.executable,
                '-m',
                'pytest',
                'tests/integration/persistence/test_media_reference_postgres.py',
                'tests/integration/persistence/test_migrations_postgres.py',
                'tests/integration/persistence/test_partial_history_postgres.py',
                '-q',
                '--tb=short',
            ],
            cwd=repo,
            env=env,
            stdout=log,
            stderr=subprocess.STDOUT,
            timeout=240,
        )
    print('PostgreSQL media tests exit:', run.returncode)
    if run.returncode:
        raise RuntimeError('PostgreSQL media tests failed')
finally:
    labels = json.loads(subprocess.check_output(['docker', 'inspect', '--format', '{{json .Config.Labels}}', cid]))
    assert labels.get('qa.task') == 'LANG-17'
    subprocess.run(['docker', 'rm', '-f', cid], check=True, stdout=subprocess.DEVNULL)
    print('Removed recorded task container')
