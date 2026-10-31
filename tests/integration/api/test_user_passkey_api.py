"""
Integration smoke tests for Passkey API endpoints.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, Mock

import pytest

from tests.factories import FakeApp
from tests.utils.import_isolation import isolated_sys_modules, MockLifecycleControlScope


pytestmark = [pytest.mark.integration, pytest.mark.usefixtures('mock_circular_import_chain')]


@pytest.fixture(scope='module')
def mock_circular_import_chain():
    class FakeMinimalApplication:
        pass

    mock_app = Mock()
    mock_app.Application = FakeMinimalApplication

    mock_entities = Mock()
    mock_entities.LifecycleControlScope = MockLifecycleControlScope

    clear = [
        'langbot.pkg.api.http.controller.group',
        'langbot.pkg.api.http.controller.groups',
        'langbot.pkg.api.http.controller.groups.system',
        'langbot.pkg.api.http.controller.groups.user',
        'langbot.pkg.api.http.controller.main',
    ]

    with isolated_sys_modules(
        mocks={
            'langbot.pkg.core.app': mock_app,
            'langbot.pkg.core.entities': mock_entities,
        },
        clear=clear,
    ):
        import langbot.pkg.api.http.controller.groups.user as _user_group  # noqa: E402, F401

        yield


@pytest.fixture
def fake_api_app():
    app = FakeApp()
    app.instance_config.data.update(
        {
            'api': {'port': 5300},
            'system': {'allow_modify_login_info': True},
        }
    )
    app.user_service = Mock()
    app.user_service.verify_jwt_token = AsyncMock(side_effect=ValueError('Invalid token'))
    app.user_service.get_user_by_email = AsyncMock(return_value=Mock())
    return app


@pytest.fixture
async def quart_test_client(fake_api_app, http_controller_cls):
    controller = http_controller_cls(fake_api_app)
    await controller.initialize()

    client = controller.quart_app.test_client()
    yield client


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
    """The RP ID and expected origin must come from server config, never the request.

    WebAuthn's anti-phishing guarantee depends on values the *server* chose. If
    the server trusts a JSON ``origin`` field, the ``Origin``/``Referer`` header,
    or the ``Host`` header, then a sibling host under the same registrable domain
    can obtain a valid assertion for a victim's credential.
    """

    @staticmethod
    def _set_webui_url(fake_api_app, url: str) -> None:
        config = getattr(fake_api_app.instance_config, 'data', None)
        if not isinstance(config, dict):
            config = {}
            fake_api_app.instance_config.data = config
        config.setdefault('api', {})['webui_url'] = url

    @pytest.mark.asyncio
    async def test_auth_options_ignores_client_supplied_origin_body(self, quart_test_client, fake_api_app):
        fake_api_app.user_service.generate_passkey_authentication_options = AsyncMock(
            return_value=({'challenge': 'test_chal', 'rpId': 'bot.langbot.app'}, 'token_cfg')
        )
        self._set_webui_url(fake_api_app, 'https://bot.langbot.app')

        response = await quart_test_client.post(
            '/api/v1/user/passkey/auth/options',
            json={'origin': 'https://proxy.attacker.test:8443'},
            headers={'Host': '127.0.0.1:5300'},
        )

        assert response.status_code == 200
        data = await response.get_json()
        assert data['code'] == 0
        fake_api_app.user_service.generate_passkey_authentication_options.assert_awaited_once_with(
            rp_id='bot.langbot.app',
            origin='https://bot.langbot.app',
            email=None,
        )

    @pytest.mark.asyncio
    async def test_auth_options_ignores_origin_header(self, quart_test_client, fake_api_app):
        fake_api_app.user_service.generate_passkey_authentication_options = AsyncMock(
            return_value=({'challenge': 'test_chal', 'rpId': 'bot.langbot.app'}, 'token_hdr')
        )
        self._set_webui_url(fake_api_app, 'https://bot.langbot.app')

        response = await quart_test_client.post(
            '/api/v1/user/passkey/auth/options',
            json={},
            headers={'Origin': 'https://evil.attacker.test'},
        )

        assert response.status_code == 200
        fake_api_app.user_service.generate_passkey_authentication_options.assert_awaited_once_with(
            rp_id='bot.langbot.app',
            origin='https://bot.langbot.app',
            email=None,
        )

    @pytest.mark.asyncio
    async def test_auth_options_ignores_referer_header(self, quart_test_client, fake_api_app):
        fake_api_app.user_service.generate_passkey_authentication_options = AsyncMock(
            return_value=({'challenge': 'test_chal', 'rpId': 'bot.langbot.app'}, 'token_ref')
        )
        self._set_webui_url(fake_api_app, 'https://bot.langbot.app')

        response = await quart_test_client.post(
            '/api/v1/user/passkey/auth/options',
            json={},
            headers={'Referer': 'https://evil.attacker.test:9000/login'},
        )

        assert response.status_code == 200
        fake_api_app.user_service.generate_passkey_authentication_options.assert_awaited_once_with(
            rp_id='bot.langbot.app',
            origin='https://bot.langbot.app',
            email=None,
        )

    @pytest.mark.asyncio
    async def test_auth_options_falls_back_to_webhook_prefix(self, quart_test_client, fake_api_app):
        fake_api_app.user_service.generate_passkey_authentication_options = AsyncMock(
            return_value=({'challenge': 'test_chal', 'rpId': 'bot.example.com'}, 'token_prefix')
        )
        config = getattr(fake_api_app.instance_config, 'data', None)
        if not isinstance(config, dict):
            config = {}
            fake_api_app.instance_config.data = config
        config['api'] = {'webui_url': '', 'webhook_prefix': 'https://bot.example.com'}

        response = await quart_test_client.post('/api/v1/user/passkey/auth/options', json={})

        assert response.status_code == 200
        fake_api_app.user_service.generate_passkey_authentication_options.assert_awaited_once_with(
            rp_id='bot.example.com',
            origin='https://bot.example.com',
            email=None,
        )
