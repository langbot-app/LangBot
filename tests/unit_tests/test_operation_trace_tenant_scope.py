"""Regression tests for the operation-trace tenant scope.

Cloud runtime refuses every database call made without an explicit scope, and the
audit table is row-level-secured on the bound Workspace. The writer drains its
queue outside any request lifetime, so these tests drive the real service through
persistence doubles that enforce exactly that contract: without a bound scope the
call fails. A writer (or a retention pass) that forgets to bind a scope records
nothing, which is the defect pinned here.
"""

from __future__ import annotations

import asyncio
import contextlib
import contextvars
import datetime
import logging
import typing
from types import SimpleNamespace

import pytest
import sqlalchemy
from sqlalchemy.ext.asyncio import create_async_engine

from langbot.pkg.api.http.authz import WorkspaceRole
from langbot.pkg.api.http.context import PrincipalType
from langbot.pkg.entity.persistence.base import Base
from langbot.pkg.entity.persistence import metadata as metadata_module
from langbot.pkg.entity.persistence import operation_log as operation_log_module
from langbot.pkg.operation_trace import service as service_module
from langbot.pkg.persistence.tenant_uow import CrossScopeTransactionError, TenantScopeRequiredError

pytestmark = pytest.mark.asyncio


@pytest.fixture(autouse=True)
def _closed_gate(monkeypatch):
    """The gate latch is process-wide: start every test from a disabled instance."""

    monkeypatch.setattr(service_module, '_global_enabled', False)


TRACED_WORKSPACE = '00000000-0000-0000-0000-00000000000a'
IDLE_WORKSPACE = '00000000-0000-0000-0000-00000000000b'
MODEL = operation_log_module.WorkspaceOperationLog
LEVEL_KEY = service_module.OPERATION_LEVEL_KEY


class _CloudRuntimePersistence:
    """Persistence double mirroring the cloud-runtime scope contract."""

    def __init__(self, engine) -> None:
        self.engine = engine
        self._bound: contextvars.ContextVar[tuple[str, typing.Any] | None] = contextvars.ContextVar(
            'bound_workspace', default=None
        )

    def current_scope(self) -> str | None:
        bound = self._bound.get()
        if bound is None:
            return None
        workspace_uuid, owner_task = bound
        if owner_task is not asyncio.current_task():
            # The real manager refuses a boundary a child task inherited.
            raise CrossScopeTransactionError('scoped boundaries cannot be inherited by child tasks')
        return workspace_uuid

    @contextlib.asynccontextmanager
    async def tenant_scope(self, workspace_uuid: str):
        token = self._bound.set((workspace_uuid, asyncio.current_task()))
        try:
            yield self
        finally:
            self._bound.reset(token)

    async def execute_async(self, *args, **kwargs):
        if self.current_scope() is None:
            raise TenantScopeRequiredError('cloud persistence access requires an explicit Workspace scope')
        # The database carries the scope as an RLS setting, so a statement that
        # writes another Workspace's rows would be rejected as well.
        async with self.engine.connect() as connection:
            result = await connection.execute(*args, **kwargs)
            await connection.commit()
            return result


class _SingleDatabasePersistence:
    """Persistence double for the unscoped single-database deployment."""

    def __init__(self, engine) -> None:
        self.engine = engine

    async def execute_async(self, *args, **kwargs):
        async with self.engine.connect() as connection:
            result = await connection.execute(*args, **kwargs)
            await connection.commit()
            return result


@pytest.fixture
async def trace_env(tmp_path):
    """A real service against SQLite, with the enforcement double installed."""

    engine = create_async_engine(f'sqlite+aiosqlite:///{tmp_path / "trace-scope.db"}')
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    persistence = _CloudRuntimePersistence(engine)
    application = SimpleNamespace(
        persistence_mgr=persistence,
        logger=logging.getLogger('operation-trace-scope-test'),
        user_service=None,
        operation_trace_active=False,
    )
    try:
        yield service_module.WorkspaceSettingsService(application), application, engine
    finally:
        await engine.dispose()


async def _set_level(engine, workspace_uuid: str, level: int) -> None:
    async with engine.begin() as connection:
        await connection.execute(
            sqlalchemy.insert(metadata_module.WorkspaceMetadata).values(
                workspace_uuid=workspace_uuid,
                key=LEVEL_KEY,
                value=str(level),
            )
        )


async def _rows(engine) -> list:
    async with engine.begin() as connection:
        result = await connection.execute(sqlalchemy.select(MODEL))
    return list(result.all())


async def test_writer_binds_workspace_scope_when_recording(trace_env):
    """A queued trace is written by the background writer holding its own scope."""

    service, application, engine = trace_env
    rule = service_module.classify('POST', '/api/v1/pipelines')

    queued = await service.record(
        TRACED_WORKSPACE,
        rule=rule,
        level=service_module.OPERATION_LEVEL_MUTATION,
        http_method='POST',
        route='/api/v1/pipelines',
    )
    assert queued is True

    await service.flush_pending(timeout=5.0)

    rows = await _rows(engine)
    assert len(rows) == 1
    assert rows[0].workspace_uuid == TRACED_WORKSPACE
    assert service._write_failures == 0


async def test_retention_prune_binds_workspace_scope(trace_env):
    """The maintenance loop prunes without a request, so prune binds its own scope."""

    service, application, engine = trace_env
    stale = datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None) - datetime.timedelta(days=90)
    async with engine.begin() as connection:
        await connection.execute(
            sqlalchemy.insert(MODEL).values(
                workspace_uuid=TRACED_WORKSPACE,
                level=service_module.OPERATION_LEVEL_MUTATION,
                outcome='ok',
                created_at=stale,
            )
        )
    await _set_level(engine, TRACED_WORKSPACE, service_module.OPERATION_LEVEL_MUTATION)

    report = await service.prune(TRACED_WORKSPACE, retention_days=30)

    assert report['expired'] == 1
    assert await _rows(engine) == []


async def test_request_wrapper_records_after_the_handler_released_its_scope(trace_env):
    """The route wrapper traces outside the request scope and must still record.

    Level resolution and the queued write both happen after the handler released
    its tenant scope. Each of them has to bind the Workspace itself: an unscoped
    read reported level 0, so every request was dropped without a trace.
    """

    service, application, engine = trace_env
    await _set_level(engine, TRACED_WORKSPACE, service_module.OPERATION_LEVEL_MUTATION)
    context = SimpleNamespace(
        workspace_uuid=TRACED_WORKSPACE,
        workspace=SimpleNamespace(role=WorkspaceRole.OWNER.value),
        principal=SimpleNamespace(
            principal_type=PrincipalType.ACCOUNT,
            account_uuid=None,
            actor_account_uuid=None,
            api_key_uuid=None,
        ),
        auth_type='user_token',
        request_id='req-scope-test',
    )

    recorded = await service.record_request(
        context,
        method='POST',
        route=f'/api/v1/workspaces/{TRACED_WORKSPACE}/invitations',
        status_code=200,
    )

    assert recorded is True
    await service.flush_pending(timeout=5.0)
    rows = await _rows(engine)
    assert len(rows) == 1
    assert rows[0].action == 'member_invite'


async def test_writer_started_inside_a_request_scope_still_records(trace_env):
    """The writer outlives the request that first enqueued a trace.

    A task created while its caller held a Workspace boundary inherits it, and a
    child task may not use an inherited boundary. Starting the writer with the
    caller's context made it reject every later write instead of recording it.
    """

    service, application, engine = trace_env
    await _set_level(engine, TRACED_WORKSPACE, service_module.OPERATION_LEVEL_MUTATION)
    rule = service_module.classify('POST', '/api/v1/pipelines')

    async with application.persistence_mgr.tenant_scope(TRACED_WORKSPACE):
        queued = await service.record(
            TRACED_WORKSPACE,
            rule=rule,
            level=service_module.OPERATION_LEVEL_MUTATION,
            http_method='POST',
            route='/api/v1/pipelines',
        )
        assert queued is True
        await service.flush_pending(timeout=5.0)

    rows = await _rows(engine)
    assert len(rows) == 1
    assert service._write_failures == 0


async def test_prime_opens_gate_from_discovered_workspace_bindings(trace_env):
    """A restart resumes tracing: the gate opens from the Workspaces this instance owns."""

    service, application, engine = trace_env
    await _set_level(engine, IDLE_WORKSPACE, service_module.OPERATION_LEVEL_NONE)
    await _set_level(engine, TRACED_WORKSPACE, service_module.OPERATION_LEVEL_MUTATION)

    async def list_active_execution_bindings():
        return [
            SimpleNamespace(workspace_uuid=IDLE_WORKSPACE),
            SimpleNamespace(workspace_uuid=TRACED_WORKSPACE),
        ]

    application.workspace_service = SimpleNamespace(list_active_execution_bindings=list_active_execution_bindings)

    await service.prime_global_flag()

    assert application.operation_trace_active is True


async def test_prime_keeps_gate_closed_when_no_workspace_traces(trace_env):
    """A disabled instance still pays nothing on the request path."""

    service, application, engine = trace_env
    await _set_level(engine, IDLE_WORKSPACE, service_module.OPERATION_LEVEL_NONE)

    async def list_active_execution_bindings():
        return [SimpleNamespace(workspace_uuid=IDLE_WORKSPACE)]

    application.workspace_service = SimpleNamespace(list_active_execution_bindings=list_active_execution_bindings)

    await service.prime_global_flag()

    assert application.operation_trace_active is False


async def test_prime_falls_back_to_metadata_scan_without_discovery(tmp_path):
    """A single-database deployment without a Workspace directory still resumes."""

    engine = create_async_engine(f'sqlite+aiosqlite:///{tmp_path / "trace-single.db"}')
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    application = SimpleNamespace(
        persistence_mgr=_SingleDatabasePersistence(engine),
        logger=logging.getLogger('operation-trace-single-test'),
        user_service=None,
        operation_trace_active=False,
    )
    try:
        await _set_level(engine, TRACED_WORKSPACE, service_module.OPERATION_LEVEL_MUTATION)
        service = service_module.WorkspaceSettingsService(application)

        await service.prime_global_flag()

        assert application.operation_trace_active is True
    finally:
        await engine.dispose()
