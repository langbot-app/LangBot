"""
Integration smoke tests for Passkey API endpoints.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, Mock

import pytest

from tests.integration.api.test_smoke import (
    fake_api_app,
    mock_circular_import_chain,
    quart_test_client,
)


pytestmark = [pytest.mark.integration, pytest.mark.usefixtures('mock_circular_import_chain')]


class TestPasskeyPublicEndpoints:
    @pytest.mark.asyncio
    async def test_auth_options_endpoint(self, quart_test_client, fake_api_app):
        fake_api_app.user_service.generate_passkey_authentication_options = AsyncMock(
            return_value=({'challenge': 'test_chal', 'rpId': 'localhost'}, 'token_123')
        )

        response = await quart_test_client.post(
            '/api/v1/user/passkey/auth/options',
            json={'origin': 'http://localhost:3000'},
        )

        assert response.status_code == 200
        data = await response.get_json()
        assert data['code'] == 0
        assert data['data']['challenge_token'] == 'token_123'
        assert data['data']['options']['rpId'] == 'localhost'

    @pytest.mark.asyncio
    async def test_auth_verify_missing_payload(self, quart_test_client, fake_api_app):
        response = await quart_test_client.post(
            '/api/v1/user/passkey/auth/verify',
            json={},
        )
        assert response.status_code == 200
        data = await response.get_json()
        assert data['code'] != 0
        assert 'Missing challenge_token or credential' in data['msg']

    @pytest.mark.asyncio
    async def test_auth_verify_success(self, quart_test_client, fake_api_app):
        fake_api_app.user_service.verify_passkey_authentication = AsyncMock(
            return_value=('jwt_token_abc', Mock(user='user@example.com'))
        )

        response = await quart_test_client.post(
            '/api/v1/user/passkey/auth/verify',
            json={'challenge_token': 'token_123', 'credential': {'id': 'cred_id'}},
        )

        assert response.status_code == 200
        data = await response.get_json()
        assert data['code'] == 0
        assert data['data']['token'] == 'jwt_token_abc'
        assert data['data']['user'] == 'user@example.com'


class TestPasskeyProtectedEndpoints:
    @pytest.mark.asyncio
    async def test_register_options_requires_auth(self, quart_test_client):
        response = await quart_test_client.post('/api/v1/user/passkey/register/options', json={})
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_passkeys_list_requires_auth(self, quart_test_client):
        response = await quart_test_client.get('/api/v1/user/passkeys')
        assert response.status_code == 401


class TestPasskeyReverseProxyScenarios:
    @pytest.mark.asyncio
    async def test_auth_options_respects_custom_origin_body_behind_proxy(self, quart_test_client, fake_api_app):
        fake_api_app.user_service.generate_passkey_authentication_options = AsyncMock(
            return_value=({'challenge': 'test_chal', 'rpId': 'proxy.company.com'}, 'token_proxy')
        )

        response = await quart_test_client.post(
            '/api/v1/user/passkey/auth/options',
            json={'origin': 'https://proxy.company.com:8443'},
            headers={'Host': '127.0.0.1:5300'},
        )

        assert response.status_code == 200
        data = await response.get_json()
        assert data['code'] == 0
        fake_api_app.user_service.generate_passkey_authentication_options.assert_awaited_once_with(
            rp_id='proxy.company.com',
            origin='https://proxy.company.com:8443',
            email=None,
        )

    @pytest.mark.asyncio
    async def test_auth_options_falls_back_to_origin_header(self, quart_test_client, fake_api_app):
        fake_api_app.user_service.generate_passkey_authentication_options = AsyncMock(
            return_value=({'challenge': 'test_chal', 'rpId': 'bot.example.com'}, 'token_header')
        )

        response = await quart_test_client.post(
            '/api/v1/user/passkey/auth/options',
            json={},
            headers={'Origin': 'https://bot.example.com'},
        )

        assert response.status_code == 200
        fake_api_app.user_service.generate_passkey_authentication_options.assert_awaited_once_with(
            rp_id='bot.example.com',
            origin='https://bot.example.com',
            email=None,
        )

    @pytest.mark.asyncio
    async def test_auth_options_falls_back_to_referer_header(self, quart_test_client, fake_api_app):
        fake_api_app.user_service.generate_passkey_authentication_options = AsyncMock(
            return_value=({'challenge': 'test_chal', 'rpId': 'bot.example.com'}, 'token_referer')
        )

        response = await quart_test_client.post(
            '/api/v1/user/passkey/auth/options',
            json={},
            headers={'Referer': 'https://bot.example.com:9000/login'},
        )

        assert response.status_code == 200
        fake_api_app.user_service.generate_passkey_authentication_options.assert_awaited_once_with(
            rp_id='bot.example.com',
            origin='https://bot.example.com:9000',
            email=None,
        )
