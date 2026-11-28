from __future__ import annotations

import asyncio
from contextlib import aclosing, asynccontextmanager
from contextvars import ContextVar
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from langbot.pkg.api.application.api import ApplicationAPI
from langbot.pkg.api.application.contracts import ApplicationAPIException, Input, Operation
from langbot.pkg.api.authz import Permission
from langbot.pkg.api.context import PrincipalContext, PrincipalType, RequestContext, WorkspaceContext
from langbot.pkg.i18n import language
from langbot.pkg.utils.bounded_executor import current_blocking_work_scope


class Empty(Input):
    pass


def context(workspace):
    return RequestContext(
        'instance-a',
        1,
        'request-a',
        'user-token',
        PrincipalContext(PrincipalType.ACCOUNT, account_uuid='account-a'),
        WorkspaceContext(workspace, 'membership-a', 'developer', frozenset({'resource.view'})),
    )


@pytest.fixture
def host(monkeypatch):
    tenant = ContextVar('test_stream_tenant', default=None)

    @asynccontextmanager
    async def tenant_scope(workspace):
        token = tenant.set(workspace)
        try:
            yield
        finally:
            tenant.reset(token)

    ap = SimpleNamespace(
        persistence_mgr=SimpleNamespace(tenant_scope=tenant_scope),
        tenant=tenant,
        workspace_service=SimpleNamespace(
            get_execution_binding=AsyncMock(return_value=SimpleNamespace(instance_uuid='instance-a'))
        ),
        logger=Mock(),
    )
    monkeypatch.setattr(
        'langbot.pkg.api.application.api.get_workspace_language',
        AsyncMock(side_effect=lambda ap, ws: 'zh_Hans' if ws == 'workspace-a' else 'ja_JP'),
    )
    return ap


def api(host, handler):
    return ApplicationAPI(
        host,
        operations=[Operation('test.stream', Permission.RESOURCE_VIEW, handler, Empty, dict[str, str], streaming=True)],
    )


def assert_consumer_unscoped(host):
    assert host.tenant.get() is None
    assert current_blocking_work_scope() is None
    assert language.get() == 'en_US'


@pytest.mark.asyncio
async def test_interleaved_streams_isolate_tenant_language_and_executor_scope(host):
    closed = set()

    async def handler(ap, ctx, payload):
        async def source():
            try:
                for _ in range(2):
                    assert host.tenant.get() == ctx.workspace_uuid
                    assert current_blocking_work_scope() == ctx.workspace_uuid
                    yield {'workspace': ctx.workspace_uuid, 'language': language.get()}
            finally:
                assert host.tenant.get() == ctx.workspace_uuid
                closed.add(ctx.workspace_uuid)

        return source()

    application = api(host, handler)
    first = application.stream('test.stream', context('workspace-a'), {})
    second = application.stream('test.stream', context('workspace-b'), {})
    async with aclosing(first), aclosing(second):
        for _ in range(2):
            assert await anext(first) == {'workspace': 'workspace-a', 'language': 'zh_Hans'}
            assert_consumer_unscoped(host)
            assert await anext(second) == {'workspace': 'workspace-b', 'language': 'ja_JP'}
            assert_consumer_unscoped(host)
    assert closed == {'workspace-a', 'workspace-b'}


@pytest.mark.asyncio
async def test_stream_can_be_closed_from_another_task_without_resetting_foreign_context(host):
    closed = asyncio.Event()

    async def handler(ap, ctx, payload):
        async def source():
            try:
                yield {'item': 'first'}
                await asyncio.Event().wait()
            finally:
                assert host.tenant.get() == ctx.workspace_uuid
                closed.set()

        return source()

    stream = api(host, handler).stream('test.stream', context('workspace-a'), {})
    assert await anext(stream) == {'item': 'first'}
    assert_consumer_unscoped(host)
    await asyncio.create_task(stream.aclose())
    assert closed.is_set()
    assert_consumer_unscoped(host)


@pytest.mark.asyncio
async def test_consumer_cancel_closes_source_and_restores_scopes(host):
    started, closed = asyncio.Event(), asyncio.Event()

    async def handler(ap, ctx, payload):
        async def source():
            try:
                started.set()
                await asyncio.Event().wait()
                yield {}
            finally:
                closed.set()

        return source()

    stream = api(host, handler).stream('test.stream', context('workspace-a'), {})
    consumer = asyncio.create_task(anext(stream))
    await asyncio.wait_for(started.wait(), 2)
    consumer.cancel()
    with pytest.raises(asyncio.CancelledError):
        await consumer
    assert closed.is_set()
    assert_consumer_unscoped(host)


@pytest.mark.asyncio
async def test_late_stream_failure_is_mapped_without_private_provider_text(host):
    closed = asyncio.Event()

    async def handler(ap, ctx, payload):
        async def source():
            try:
                yield {'item': 'first'}
                raise RuntimeError('private provider credential')
            finally:
                closed.set()

        return source()

    stream = api(host, handler).stream('test.stream', context('workspace-a'), {})
    async with aclosing(stream):
        assert await anext(stream) == {'item': 'first'}
        with pytest.raises(ApplicationAPIException) as exc:
            await anext(stream)
        assert exc.value.error.code == 'application_error'
        assert 'private' not in exc.value.error.message
    assert closed.is_set()
    assert_consumer_unscoped(host)
