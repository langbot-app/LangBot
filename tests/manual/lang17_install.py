"""Real marketplace install through isolated Core APIs; no model calls."""

import asyncio
import json
from pathlib import Path
import secrets
import sqlite3
import subprocess
import os
import time

import httpx


async def main():
    mode = os.environ['LANG17_INSTALL']
    result = {'mode': mode, 'requested_plugin': 'langbot-team/LocalAgent@0.2.1'}
    async with httpx.AsyncClient(base_url='http://127.0.0.1:16399', timeout=20, trust_env=False) as client:

        async def api(method, path, data=None):
            response = await client.request(method, '/api/v1' + path, json=data)
            body = response.json()
            if response.status_code >= 400 or body.get('code') != 0:
                raise RuntimeError(f'{path}: HTTP {response.status_code}: {body.get("msg")}')
            return body.get('data', {})

        try:
            account = {'user': 'lang17-install@example.invalid', 'password': secrets.token_urlsafe(24)}
            await api('POST', '/user/init', account)
            auth = await api('POST', '/user/auth', account)
            client.headers['Authorization'] = 'Bearer ' + auth['token']
            if mode == 'migration':
                pipeline = (await api('POST', '/pipelines', {'name': '4.10.10 synthetic', 'description': 'QA'}))['uuid']
                repo = Path(__file__).resolve().parents[2]
                old_config = subprocess.check_output(
                    ['git', 'show', 'v4.10.10:src/langbot/templates/default-pipeline-config.json'], cwd=repo
                ).decode()
                with sqlite3.connect('data/langbot.db') as db:
                    db.execute(
                        'update legacy_pipelines set config=?, for_version=? where uuid=?',
                        (old_config, '4.10.10', pipeline),
                    )
                preview = await api('GET', '/pipelines/_/migration/preview')
                result['preview'] = [
                    {k: v for k, v in item.items() if k != 'preview_token'} for item in preview['items']
                ]
                task = await api(
                    'POST', '/pipelines/_/migration/execute', {'confirmed': True, 'all': True, 'install_plugins': True}
                )
            else:
                task = await api(
                    'POST',
                    '/plugins/install/marketplace',
                    {'plugin_author': 'langbot-team', 'plugin_name': 'LocalAgent', 'plugin_version': '0.2.1'},
                )
            start = time.monotonic()
            while time.monotonic() - start < 120:
                current = await api('GET', '/system/tasks/' + str(task['task_id']))
                result['task'] = {
                    'runtime': {k: v for k, v in current.get('runtime', {}).items() if k != 'exception_traceback'},
                    'context': {k: v for k, v in current.get('context', {}).items() if k != 'log'},
                }
                if current.get('runtime', {}).get('done'):
                    break
                await asyncio.sleep(1)
            result['seconds'] = round(time.monotonic() - start, 2)
            result['plugins'] = await api('GET', '/plugins')
            assert result['task']['runtime']['done'], 'Install deadline exceeded'
            assert not result['task']['runtime'].get('exception'), 'Install task failed'
            assert 'LocalAgent' in str(result['plugins']), 'Plugin missing from actual inventory'
        except Exception as exc:
            result['probe_error'] = str(exc)
            raise
        finally:
            Path('install-result.json').write_text(json.dumps(result, ensure_ascii=False, indent=2))


asyncio.run(main())
