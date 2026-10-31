"""Opt-in live model -> Docker -> Core export acceptance test.

Requires BOX_LIVE_API_KEY and BOX_LIVE_MODEL; never records credentials.
"""
import base64
import json
import logging
import os

import httpx
import pytest

from langbot.pkg.box.runner import RunnerBoxService, binding_for, exported_message
from langbot.pkg.box.service import BoxService
from langbot_plugin.box.runtime import BoxRuntime
from tests.integration_tests.box.test_outbox_export import _TestDockerBackend, _Client
from tests.unit_tests.box.test_box_service import make_app, make_query, _CONTEXT


@pytest.mark.asyncio
async def test_live_model_explicit_export(tmp_path):
    key = os.environ.get('BOX_LIVE_API_KEY')
    if not key:
        pytest.skip('BOX_LIVE_API_KEY is required')
    logger = logging.getLogger('test.box.live')
    backend = _TestDockerBackend(logger)
    assert await backend.is_available(), 'Docker required'
    app = make_app(logger, allowed_mount_roots=[str(tmp_path)], host_root=str(tmp_path / 'box'))
    app.instance_config.data['box']['backend'] = 'docker'
    app.instance_config.data['box']['local']['image'] = 'python:3.12-alpine'
    runtime = BoxRuntime(logger=logger, backends=[backend], max_sessions=1)
    box = BoxService(app, client=_Client(logger, runtime))
    api = RunnerBoxService(box)
    await box.initialize()
    tools = [
        {'type': 'function', 'function': {'name': 'exec', 'description': 'Run shell in sandbox',
         'parameters': {'type': 'object', 'properties': {'command': {'type': 'string'}}, 'required': ['command']}}},
        {'type': 'function', 'function': {'name': 'export_box_files',
         'description': 'Export selected absolute sandbox file paths. Success accepts files and removes only selected files. Failure preserves files; fix the problem and retry.',
         'parameters': {'type': 'object', 'properties': {'paths': {'type': 'array', 'items': {'type': 'string'}}}, 'required': ['paths']}}},
    ]
    try:
        acquired = await api.acquire(_CONTEXT, {'reuse_key': 'live-export'})
        query = make_query(0)
        object.__setattr__(query, '_box_binding', None)
        await api.bind(_CONTEXT, query, 'live-explicit-export', acquired['id'])
        outbox = f'/workspace/outbox/{binding_for(query).io_scope}'
        target = outbox + '/answer.txt'
        keep = outbox + '/keep.txt'
        messages = [{'role': 'user', 'content': (
            f'Use tools to create {target} containing exactly LIVE_EXPORT_OK (no newline) and {keep} containing KEEP. '
            'First deliberately attempt to export /workspace/does-not-exist.txt to test error feedback. '
            f'After that fails, explicitly export only {target}. Do not export or delete {keep}. '
            'Then finish. Prefer outbox for deliverables; file creation alone does not deliver them.'
        )}]
        errors = 0
        items = []
        async with httpx.AsyncClient(timeout=120) as client:
            for _ in range(12):
                response = await client.post(
                    os.environ.get('BOX_LIVE_BASE_URL', 'https://newapi.rockchin.top/v1') + '/chat/completions',
                    headers={'Authorization': 'Bearer ' + key},
                    json={'model': os.environ['BOX_LIVE_MODEL'], 'messages': messages, 'tools': tools},
                )
                assert response.status_code == 200, f'Gateway HTTP {response.status_code}'
                message = response.json()['choices'][0]['message']
                messages.append(message)
                calls = message.get('tool_calls', [])
                if not calls:
                    break
                for call in calls:
                    args = json.loads(call['function']['arguments'])
                    try:
                        if call['function']['name'] == 'exec':
                            result = await box.execute_tool(args, query)
                        else:
                            result = await api.export_files(query, args['paths'])
                            items.extend(result['items'])
                    except Exception as exc:
                        errors += 1
                        result = {'error': str(exc)}
                    messages.append({'role': 'tool', 'tool_call_id': call['id'], 'content': json.dumps(result)})
        assert errors >= 1, 'Model did not exercise the requested failing export'
        assert len(items) == 1
        message = exported_message(query, [items[0]['id']])
        assert base64.b64decode(message.root[0].base64) == b'LIVE_EXPORT_OK'
        result = await box.execute_tool({'command': f'test ! -e {target} && cat {keep}'}, query)
        assert result['ok'] and result['stdout'] == 'KEEP'
    finally:
        await box.shutdown()
