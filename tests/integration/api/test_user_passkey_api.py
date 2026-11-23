"""
Integration smoke tests for Passkey API endpoints.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from langbot.pkg.utils import constants
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
async def api_controller(fake_api_app, http_controller_cls):
    controller = http_controller_cls(fake_api_app)
    await controller.initialize()
    return controller


@pytest.fixture
def quart_test_client(api_controller):
    return api_controller.quart_app.test_client()


# Use request-shaped but inert credentials: the edition check must stop these
# requests before any WebAuthn service operation, even for a valid session.
_VERIFY_PAYLOAD = {'challenge_token': 'fixture-challenge', 'credential': {'id': 'fixture-credential'}}
_PASSKEY_ROUTES = (
    ('POST', '/passkey/auth/options', False, {}, 'generate_passkey_authentication_options'),
    ('POST', '/passkey/auth/verify', False, _VERIFY_PAYLOAD, 'verify_passkey_authentication'),
    ('POST', '/passkey/register/options', True, {}, 'generate_passkey_registration_options'),
    ('POST', '/passkey/register/verify', True, _VERIFY_PAYLOAD, 'verify_and_save_passkey_registration'),
    ('GET', '/passkeys', True, None, 'get_user_passkeys'),
    ('PATCH', '/passkey/<passkey_uuid>', True, {'name': 'fixture name'}, 'rename_user_passkey'),
    ('DELETE', '/passkey/<passkey_uuid>', True, None, 'delete_user_passkey'),
)
_USER_API_PREFIX = '/api/v1/user'


def test_all_registered_passkey_routes_have_a_cloud_contract_case(api_controller):
    registered_routes = {
        (method, rule.rule.removeprefix(_USER_API_PREFIX))
        for rule in api_controller.quart_app.url_map.iter_rules()
        if rule.rule.startswith(f'{_USER_API_PREFIX}/passkey')
        for method in rule.methods - {'HEAD', 'OPTIONS'}
    }
    assert registered_routes == {(method, path) for method, path, *_ in _PASSKEY_ROUTES}


@pytest.mark.asyncio
@pytest.mark.parametrize(
    'edition,deployment_mode',
    [
        pytest.param('cloud', 'oss', id='cloud-edition'),
        pytest.param('community', 'cloud', id='cloud-deployment'),
    ],
)
@pytest.mark.parametrize(
    'method,path,authenticated,payload',
    [pytest.param(*case[:-1], id=f'{case[0]} {case[1]}') for case in _PASSKEY_ROUTES],
)
async def test_cloud_refuses_passkey_routes_before_service_dispatch(
    quart_test_client,
    fake_api_app,
    monkeypatch,
    edition,
    deployment_mode,
    method,
    path,
    authenticated,
    payload,
):
    monkeypatch.setattr(constants, 'edition', edition)
    fake_api_app.deployment = SimpleNamespace(mode=deployment_mode, multi_workspace_enabled=False)
    user_service = fake_api_app.user_service
    user_service.get_authenticated_account = AsyncMock(
        return_value=SimpleNamespace(uuid='fixture-account', user='test@example.local')
    )
    for *_, service_method in _PASSKEY_ROUTES:
        setattr(user_service, service_method, AsyncMock())

    request_kwargs = {}
    if payload is not None:
        request_kwargs['json'] = payload
    if authenticated:
        request_kwargs['headers'] = {'Authorization': 'Bearer fixture-account-token'}

    response = await quart_test_client.open(
        f'{_USER_API_PREFIX}{path.replace("<passkey_uuid>", "fixture-passkey")}', method=method, **request_kwargs
    )

    assert response.status_code == 403
    assert (await response.get_json())['code'] == 'edition_unsupported'
    if authenticated:
        user_service.get_authenticated_account.assert_awaited_once_with('fixture-account-token')
    else:
        user_service.get_authenticated_account.assert_not_called()
    for *_, service_method in _PASSKEY_ROUTES:
        getattr(user_service, service_method).assert_not_called()


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
