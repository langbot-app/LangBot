import base64
import io
import json
import sqlite3
from contextlib import closing

import httpx
import pytest
from PIL import Image, ImageFont

from tests.e2e import test_runner_plugin_runtime as runtime
from tools.regression.http_bot import signed_headers


@pytest.mark.e2e
def test_signed_command_policy(tmp_path):
    port = runtime._free_port()
    runtime.create_minimal_config(tmp_path, port)
    runtime.create_test_directories(tmp_path)
    font = tmp_path / 'policy-font.ttf'
    font.write_bytes(ImageFont.load_default(size=32).font_bytes)
    dictionary = tmp_path / 'data/metadata/sensitive-words.json'
    dictionary.parent.mkdir(parents=True, exist_ok=True)
    dictionary.write_text(json.dumps({'words': ['policyprobe'], 'mask': '*', 'mask_word': 'MASKED'}))
    proc = runtime.LangBotProcess(
        runtime.find_project_root(),
        tmp_path,
        port=port,
        timeout=360,
        collect_coverage=False,
        cli_args=['--standalone-runtime'],
    )
    try:
        assert proc.start()
        with httpx.Client(base_url=f'http://127.0.0.1:{port}', trust_env=False, timeout=30) as client:
            headers = {'Authorization': 'Bearer ' + runtime._init_and_auth(client)}
            result = client.post(
                '/api/v1/platform/bots',
                headers=headers,
                json={
                    'name': 'Signed policy',
                    'adapter': 'http_bot',
                    'enable': True,
                    'adapter_config': {'signature_required': True, 'inbound_secret': 'qa-sign', 'callback_timeout': 2},
                },
            ).json()
            assert result['code'] == 0, result
            bot = result['data']['uuid']

            def configure(rules=None, scope='all', filtering=False, strategy='none'):
                policy = {
                    'plugins': {'enable_all': False, 'plugins': []},
                    'trigger': {
                        'group-respond-rules': {
                            'enabled': rules is not None,
                            'at': False,
                            'prefix': [],
                            'regexp': [],
                            'random': 0,
                            **(rules or {}),
                        }
                    },
                    'safety': {'content-filter': {'scope': scope, 'check-sensitive-words': filtering}},
                    'output': {
                        'long-text-processing': {'strategy': strategy, 'threshold': 8, 'font-path': str(font)},
                        'misc': {'at-sender': False, 'content-filter-hint': 'filtered'},
                    },
                }
                result = client.put(
                    '/api/v1/platform/bots/' + bot, headers=headers, json={'message_policy': policy}
                ).json()
                assert result['code'] == 0, result

            def send(kind, text='/whoami', mention=None):
                parts = [{'type': 'Plain', 'text': text}]
                if mention:
                    parts.append({'type': 'At', 'target': mention})
                body = json.dumps({'session_type': kind, 'session_id': 'policyprobe', 'message': parts}).encode()
                result = client.post(
                    '/bots/' + bot + '/sync', content=body, headers=signed_headers(body, 'qa-sign')
                ).json()
                assert result['code'] == 0, result
                with closing(sqlite3.connect(tmp_path / 'data/langbot.db')) as db:
                    row = db.execute(
                        'SELECT metadata_json FROM event_log WHERE bot_id=? AND event_type=? ORDER BY id DESC LIMIT 1',
                        (bot, 'message.received'),
                    ).fetchone()
                return result['data']['message'], json.loads(row[0])

            for kind in ('person', 'group'):
                for scope, enabled in [('income-msg', True), ('output-msg', True), ('all', False)]:
                    configure(scope=scope, filtering=enabled)
                    parts, metadata = send(kind, '/whoami policyprobe')
                    if scope == 'income-msg':
                        assert metadata['routes'][0]['policy_item'] == 'content-filter', metadata
                        assert metadata['status'] == 'ignored' and not any('policyprobe' in str(part) for part in parts)
                    else:
                        text = parts[0]['text']
                        assert ('policyprobe' in text, 'MASKED' in text) == (not enabled, enabled), text
                        assert metadata['routes'][0]['status'] == 'delivered', metadata
                for strategy, component in [('forward', 'Forward'), ('image', 'Image'), ('none', 'Plain')]:
                    configure(strategy=strategy)
                    parts, metadata = send(kind)
                    assert [part['type'] for part in parts] == [component], metadata
                    if strategy == 'image':
                        with Image.open(io.BytesIO(base64.b64decode(parts[0]['base64']))) as image:
                            image.verify()
                    actions = [
                        action for event in metadata.get('policy_events', []) for action in event.get('actions', [])
                    ]
                    assert [a['strategy'] for a in actions if a['kind'] == 'long_text'] == (
                        [] if strategy == 'none' else [strategy]
                    )

            for rules, mention, allowed in [
                ({'at': True}, 'http_bot', True),
                ({'at': True}, 'other', False),
                ({'prefix': ['/who']}, None, True),
                ({'prefix': ['!']}, None, False),
                ({'regexp': ['^/whoami$']}, None, True),
                ({'regexp': ['^other$']}, None, False),
                ({'random': 1}, None, True),
                ({'random': 0}, None, False),
                (None, None, True),
            ]:
                configure(rules=rules)
                parts, metadata = send('group', mention=mention)
                assert bool(parts) == allowed, (rules, parts, metadata)
                if allowed:
                    assert 'policyprobe' in parts[0]['text'] and metadata['routes'][0]['status'] == 'delivered'
                else:
                    assert (
                        metadata['status'] == 'ignored'
                        and metadata['routes'][0]['policy_item'] == 'group-respond-rules'
                    )
            configure(rules={'random': 0})
            assert 'policyprobe' in send('person')[0][0]['text']
    finally:
        proc.stop()
