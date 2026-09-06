"""Exercise Codex provider wiring through a real LangBot process.

The default run does not contact OpenAI. Set LANGBOT_TEST_CODEX_DEVICE_AUTH=1
to also exercise live device start/pending/cancel, without account sign-in.
OAuth exchange and inference behavior are covered by deterministic tests.
"""

from __future__ import annotations

import os
import time

import pytest

pytestmark = pytest.mark.e2e


def test_codex_provider_disconnected_journey(e2e_client):
    credentials = {'user': 'codex-e2e@example.com', 'password': 'codex-local-test-password'}
    initialized = e2e_client.post('/api/v1/user/init', json=credentials)
    assert initialized.status_code == 200, initialized.text
    authenticated = e2e_client.post('/api/v1/user/auth', json=credentials)
    assert authenticated.status_code == 200, authenticated.text
    headers = {'Authorization': f'Bearer {authenticated.json()["data"]["token"]}'}
    bootstrap = e2e_client.get('/api/v1/workspaces/bootstrap', headers=headers)
    assert bootstrap.status_code == 200, bootstrap.text
    headers['X-Workspace-Id'] = bootstrap.json()['data']['workspaces'][0]['workspace']['uuid']

    requesters = e2e_client.get('/api/v1/provider/requesters?type=llm', headers=headers)
    assert requesters.status_code == 200, requesters.text
    codex = next(item for item in requesters.json()['data']['requesters'] if item['name'] == 'openai-codex')
    assert codex['spec']['support_type'] == ['llm']
    icon = e2e_client.get('/api/v1/provider/requesters/openai-codex/icon')
    assert icon.status_code == 200
    assert 'image/' in icon.headers['content-type']

    base = '/api/v1/provider/providers'
    created = e2e_client.post(
        base,
        headers=headers,
        json={'name': 'Codex E2E', 'requester': 'openai-codex', 'base_url': '', 'api_keys': []},
    )
    assert created.status_code == 200, created.text
    provider_path = f'{base}/{created.json()["data"]["uuid"]}'
    try:
        provider = e2e_client.get(provider_path, headers=headers)
        assert provider.status_code == 200, provider.text
        data = provider.json()['data']['provider']
        assert data['requester'] == 'openai-codex'
        assert data['api_keys'] == []
        assert data['base_url'] == 'https://chatgpt.com/backend-api/codex'
        assert not {'access_token', 'refresh_token', 'id_token'} & data.keys()

        status = e2e_client.get(f'{provider_path}/codex/status', headers=headers)
        assert status.status_code == 200, status.text
        assert status.json()['data']['connected'] is False
        assert status.json()['data']['status'] == 'disconnected'

        anonymous = e2e_client.post(f'{provider_path}/codex/device', json={})
        assert anonymous.status_code == 401
        invalid = e2e_client.put(provider_path, headers=headers, json={'base_url': 'https://example.com'})
        assert invalid.status_code == 400, invalid.text
        invalid_key = e2e_client.put(provider_path, headers=headers, json={'api_keys': ['not-a-codex-key']})
        assert invalid_key.status_code == 400, invalid_key.text

        scanned = e2e_client.get(f'{provider_path}/scan-models?type=llm', headers=headers)
        assert scanned.status_code == 400, scanned.text
        assert 'sign in' in scanned.json()['msg'].lower()

        renamed = e2e_client.put(provider_path, headers=headers, json={'name': 'Codex renamed'})
        assert renamed.status_code == 200, renamed.text
        reread = e2e_client.get(provider_path, headers=headers)
        assert reread.json()['data']['provider']['name'] == 'Codex renamed'
        disconnected = e2e_client.delete(f'{provider_path}/codex/auth', headers=headers)
        assert disconnected.status_code == 200, disconnected.text

        # Opt-in smoke contacts real OpenAI device endpoints, but never completes
        # account sign-in or prints the one-time code/device credentials.
        if os.environ.get('LANGBOT_TEST_CODEX_DEVICE_AUTH') == '1':
            started = e2e_client.post(f'{provider_path}/codex/device', headers=headers, json={})
            assert started.status_code == 200, started.json().get('msg', 'Device start failed')
            attempt = started.json()['data']
            assert attempt['verification_uri'] == 'https://auth.openai.com/codex/device'
            assert isinstance(attempt['user_code'], str) and attempt['user_code']
            assert 0 < attempt['expires_at'] - time.time() <= 900
            assert not {'access_token', 'refresh_token', 'device_auth_id'} & attempt.keys()
            time.sleep(attempt['interval'])
            pending = e2e_client.post(
                f'{provider_path}/codex/device/poll',
                headers=headers,
                json={'authorization_id': attempt['authorization_id']},
            )
            assert pending.status_code == 200
            assert pending.json()['data']['status'] == 'pending'
            canceled = e2e_client.delete(f'{provider_path}/codex/device/{attempt["authorization_id"]}', headers=headers)
            assert canceled.status_code == 200
            expired = e2e_client.post(
                f'{provider_path}/codex/device/poll',
                headers=headers,
                json={'authorization_id': attempt['authorization_id']},
            )
            assert expired.json()['data']['status'] == 'expired'
    finally:
        deleted = e2e_client.delete(provider_path, headers=headers)
        assert deleted.status_code == 200, deleted.text
    assert e2e_client.get(provider_path, headers=headers).status_code == 404
