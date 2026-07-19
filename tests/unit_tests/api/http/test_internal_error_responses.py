from __future__ import annotations

import contextlib
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
import quart

from langbot.pkg.api.http.controller import group
from langbot.pkg.api.http.controller.groups.webhooks import WebhookRouterGroup


pytestmark = pytest.mark.asyncio


class _FailingRouterGroup(group.RouterGroup):
    name = 'failing-test'
    path = '/failing-test'

    async def initialize(self) -> None:
        @self.route('', methods=['GET'], auth_type=group.AuthType.NONE)
        async def _():
            raise RuntimeError('database password=do-not-return')


class _AuthenticatedRouterGroup(group.RouterGroup):
    name = 'authenticated-test'
    path = '/authenticated-test'

    async def initialize(self) -> None:
        @self.route('', methods=['GET'], auth_type=group.AuthType.USER_TOKEN)
        async def _():
            return self.success()


class _InvalidAccountRouterGroup(group.RouterGroup):
    name = 'invalid-account-test'
    path = '/invalid-account-test'

    async def initialize(self) -> None:
        @self.route(
            '',
            methods=['GET'],
            auth_type=group.AuthType.ACCOUNT_TOKEN,
            permission='workspace.view',
        )
        async def _():
            return self.success()


async def test_unhandled_http_error_returns_generic_body_and_correlated_request_id():
    logger = Mock()
    application = SimpleNamespace(logger=logger)
    quart_app = quart.Quart(__name__)
    await _FailingRouterGroup(application, quart_app).initialize()

    response = await quart_app.test_client().get(
        '/failing-test',
        headers={'X-Request-Id': 'request-http-test'},
    )

    assert response.status_code == 500
    assert await response.get_json() == {
        'code': 'internal_error',
        'msg': 'Internal server error',
        'request_id': 'request-http-test',
    }
    assert response.headers['X-Request-Id'] == 'request-http-test'
    log_message = logger.error.call_args.args[0]
    assert 'request_id=request-http-test' in log_message
    assert 'database password=do-not-return' in log_message
    assert 'do-not-return' not in (await response.get_data(as_text=True))


async def test_public_webhook_error_uses_same_generic_error_contract():
    logger = Mock()
    application = SimpleNamespace(
        logger=logger,
        platform_mgr=SimpleNamespace(
            resolve_public_bot=AsyncMock(side_effect=RuntimeError('adapter credential=do-not-return'))
        ),
    )
    quart_app = quart.Quart(__name__)
    await WebhookRouterGroup(application, quart_app).initialize()

    response = await quart_app.test_client().post(
        '/bots/11111111-1111-4111-8111-111111111111',
        headers={'X-Request-Id': 'request-webhook-test'},
    )

    assert response.status_code == 500
    assert await response.get_json() == {
        'code': 'internal_error',
        'msg': 'Internal server error',
        'request_id': 'request-webhook-test',
    }
    assert response.headers['X-Request-Id'] == 'request-webhook-test'
    log_message = logger.error.call_args.args[0]
    assert 'request_id=request-webhook-test' in log_message
    assert 'adapter credential=do-not-return' in log_message
    assert 'do-not-return' not in (await response.get_data(as_text=True))


async def test_public_webhook_carries_scope_without_holding_database_session():
    class ScopeOnlyPersistenceManager:
        mode = SimpleNamespace(value='cloud_runtime')

        def __init__(self):
            self.active_workspace = None

        @contextlib.asynccontextmanager
        async def tenant_scope(self, workspace_uuid):
            self.active_workspace = workspace_uuid
            try:
                yield
            finally:
                self.active_workspace = None

        def current_session(self):
            return None

    persistence_mgr = ScopeOnlyPersistenceManager()
    workspace_uuid = '00000000-0000-0000-0000-00000000000a'
    bot_uuid = '11111111-1111-4111-8111-111111111111'

    class Adapter:
        async def handle_unified_webhook(self, **_kwargs):
            assert persistence_mgr.active_workspace == workspace_uuid
            assert persistence_mgr.current_session() is None
            return {'ok': True}

    async def get_execution_binding(resolved_workspace_uuid, expected_generation=None):
        assert resolved_workspace_uuid == workspace_uuid
        assert expected_generation == 4

    runtime_bot = SimpleNamespace(
        workspace_uuid=workspace_uuid,
        placement_generation=4,
        enable=True,
        adapter=Adapter(),
    )
    application = SimpleNamespace(
        logger=Mock(),
        persistence_mgr=persistence_mgr,
        platform_mgr=SimpleNamespace(resolve_public_bot=AsyncMock(return_value=runtime_bot)),
        workspace_service=SimpleNamespace(get_execution_binding=get_execution_binding),
    )
    quart_app = quart.Quart(__name__)
    await WebhookRouterGroup(application, quart_app).initialize()

    response = await quart_app.test_client().post(f'/bots/{bot_uuid}')

    assert response.status_code == 200
    assert await response.get_json() == {'ok': True}
    assert persistence_mgr.active_workspace is None


async def test_authentication_failure_does_not_return_internal_exception_text():
    logger = Mock()
    application = SimpleNamespace(
        logger=logger,
        user_service=SimpleNamespace(
            get_authenticated_account=AsyncMock(side_effect=RuntimeError('database password=do-not-return'))
        ),
    )
    quart_app = quart.Quart(__name__)
    await _AuthenticatedRouterGroup(application, quart_app).initialize()

    response = await quart_app.test_client().get(
        '/authenticated-test',
        headers={
            'Authorization': 'Bearer invalid',
            'X-Request-Id': 'request-auth-test',
        },
    )

    assert response.status_code == 401
    assert await response.get_json() == {
        'code': 'invalid_authentication',
        'msg': 'Invalid authentication credentials',
    }
    assert 'do-not-return' not in (await response.get_data(as_text=True))
    assert 'request_id=request-auth-test' in logger.warning.call_args.args[0]
    assert 'database password=do-not-return' in logger.warning.call_args.args[0]


async def test_account_token_route_cannot_declare_workspace_permission():
    application = SimpleNamespace(logger=Mock())
    quart_app = quart.Quart(__name__)

    with pytest.raises(ValueError, match='cannot declare Workspace permissions'):
        await _InvalidAccountRouterGroup(application, quart_app).initialize()
