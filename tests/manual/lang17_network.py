"""Real migration/extension API failures against a synthetic local marketplace."""

import asyncio
import json
from pathlib import Path
import secrets
import sqlite3
import subprocess
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import httpx

mode = 'http503'


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def do_GET(self):
        if mode == 'timeout':
            time.sleep(17)
        if mode == 'disconnect':
            self.connection.close()
            return
        self.send_response(503 if mode == 'http503' else 200)
        self.send_header('Content-Length', '9999' if mode == 'truncated' else '0')
        self.end_headers()
        if mode == 'truncated':
            self.wfile.write(b'incomplete package')
            self.wfile.flush()
            self.close_connection = True


async def main():
    global mode
    server = ThreadingHTTPServer(('127.0.0.1', 16420), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    results = []
    try:
        async with httpx.AsyncClient(base_url='http://127.0.0.1:16399', timeout=20, trust_env=False) as client:

            async def api(method, path, data=None):
                r = await client.request(method, '/api/v1' + path, json=data)
                b = r.json()
                if r.status_code >= 400 or b.get('code') != 0:
                    raise RuntimeError(f'{path}: HTTP {r.status_code}')
                return b.get('data', {})

            account = {'user': 'qa-network@example.invalid', 'password': secrets.token_urlsafe(24)}
            await api('POST', '/user/init', account)
            token = (await api('POST', '/user/auth', account))['token']
            client.headers['Authorization'] = 'Bearer ' + token
            pipeline = (
                await api('POST', '/pipelines', {'name': 'Network failure probe', 'description': 'isolated QA'})
            )['uuid']
            old = subprocess.check_output(
                ['git', 'show', 'v4.10.10:src/langbot/templates/default-pipeline-config.json'],
                cwd=Path(__file__).resolve().parents[2],
            ).decode()
            with sqlite3.connect('data/langbot.db') as db:
                db.execute(
                    'update legacy_pipelines set config=?,for_version=? where uuid=?', (old, '4.10.10', pipeline)
                )
            for scenario in ('http503', 'disconnect', 'truncated', 'timeout', 'offline'):
                mode = scenario
                if scenario == 'offline':
                    server.shutdown()
                    server.server_close()
                for route in ('migration', 'extension'):
                    start = time.monotonic()
                    if route == 'migration':
                        task = await api(
                            'POST',
                            '/pipelines/_/migration/execute',
                            {'confirmed': True, 'all': True, 'install_plugins': True},
                        )
                    else:
                        task = await api(
                            'POST',
                            '/plugins/install/marketplace',
                            {'plugin_author': 'langbot-team', 'plugin_name': 'LocalAgent', 'plugin_version': '0.2.1'},
                        )
                    for _ in range(45):
                        state = await api('GET', '/system/tasks/' + str(task['task_id']))
                        if state['runtime']['done']:
                            break
                        await asyncio.sleep(1)
                    runtime = state['runtime']
                    assert runtime['done'], (scenario, route, 'task failed to terminate')
                    results.append(
                        {
                            'scenario': scenario,
                            'route': route,
                            'seconds': round(time.monotonic() - start, 2),
                            'done': runtime['done'],
                            'state': runtime['state'],
                            'exception_type': str(runtime.get('exception', '')).split(':')[0][:150],
                            'result': runtime.get('result'),
                        }
                    )
                    Path('network-result.json').write_text(json.dumps(results, indent=2))
    finally:
        server.shutdown()
        server.server_close()
        Path('network-finished').touch()


asyncio.run(main())
