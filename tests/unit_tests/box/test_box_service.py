from __future__ import annotations

import datetime as dt
import os
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

import langbot_plugin.api.entities.builtin.pipeline.query as pipeline_query

from langbot.pkg.box.backend import BaseSandboxBackend
from langbot.pkg.box.errors import BoxBackendUnavailableError, BoxSessionConflictError, BoxValidationError
from langbot.pkg.box.models import (
    BoxExecutionResult,
    BoxExecutionStatus,
    BoxHostMountMode,
    BoxNetworkMode,
    BoxSessionInfo,
    BoxSpec,
)
from langbot.pkg.box.runtime import BoxRuntime
from langbot.pkg.box.service import BoxService


class FakeBackend(BaseSandboxBackend):
    def __init__(self, logger: Mock, available: bool = True):
        super().__init__(logger)
        self.name = 'fake'
        self.available = available
        self.start_calls: list[str] = []
        self.start_specs: list[BoxSpec] = []
        self.exec_calls: list[tuple[str, str]] = []
        self.stop_calls: list[str] = []

    async def is_available(self) -> bool:
        return self.available

    async def start_session(self, spec: BoxSpec) -> BoxSessionInfo:
        self.start_calls.append(spec.session_id)
        self.start_specs.append(spec)
        now = dt.datetime.now(dt.UTC)
        return BoxSessionInfo(
            session_id=spec.session_id,
            backend_name=self.name,
            backend_session_id=f'backend-{spec.session_id}',
            image=spec.image,
            network=spec.network,
            host_path=spec.host_path,
            host_path_mode=spec.host_path_mode,
            created_at=now,
            last_used_at=now,
        )

    async def exec(self, session: BoxSessionInfo, spec: BoxSpec) -> BoxExecutionResult:
        self.exec_calls.append((session.session_id, spec.cmd))
        return BoxExecutionResult(
            session_id=session.session_id,
            backend_name=self.name,
            status=BoxExecutionStatus.COMPLETED,
            exit_code=0,
            stdout=f'executed: {spec.cmd}',
            stderr='',
            duration_ms=12,
        )

    async def stop_session(self, session: BoxSessionInfo):
        self.stop_calls.append(session.session_id)


def make_query(query_id: int = 42) -> pipeline_query.Query:
    return pipeline_query.Query.model_construct(query_id=query_id)


def make_app(logger: Mock, allowed_host_mount_roots: list[str] | None = None):
    return SimpleNamespace(
        logger=logger,
        instance_config=SimpleNamespace(
            data={
                'box': {
                    'allowed_host_mount_roots': allowed_host_mount_roots or [],
                    'default_host_workspace': '',
                }
            }
        ),
    )


@pytest.mark.asyncio
async def test_box_runtime_reuses_request_session():
    logger = Mock()
    backend = FakeBackend(logger)
    runtime = BoxRuntime(logger=logger, backends=[backend], session_ttl_sec=300)
    await runtime.initialize()

    first = BoxSpec.model_validate({'cmd': 'echo first', 'session_id': 'req-1'})
    second = BoxSpec.model_validate({'cmd': 'echo second', 'session_id': 'req-1'})

    await runtime.execute(first)
    await runtime.execute(second)

    assert backend.start_calls == ['req-1']
    assert backend.exec_calls == [('req-1', 'echo first'), ('req-1', 'echo second')]


@pytest.mark.asyncio
async def test_box_service_defaults_session_id_from_query():
    logger = Mock()
    backend = FakeBackend(logger)
    runtime = BoxRuntime(logger=logger, backends=[backend], session_ttl_sec=300)
    service = BoxService(make_app(logger), runtime=runtime)
    await service.initialize()

    result = await service.execute_sandbox_tool({'cmd': 'pwd', 'network': BoxNetworkMode.OFF.value}, make_query(7))

    assert result['session_id'] == '7'
    assert result['ok'] is True
    assert backend.start_calls == ['7']


@pytest.mark.asyncio
async def test_box_service_fails_closed_when_backend_unavailable():
    logger = Mock()
    backend = FakeBackend(logger, available=False)
    runtime = BoxRuntime(logger=logger, backends=[backend], session_ttl_sec=300)
    service = BoxService(make_app(logger), runtime=runtime)
    await service.initialize()

    with pytest.raises(BoxBackendUnavailableError):
        await service.execute_sandbox_tool({'cmd': 'echo hello'}, make_query(9))


@pytest.mark.asyncio
async def test_box_service_allows_host_mount_under_configured_root(tmp_path):
    logger = Mock()
    backend = FakeBackend(logger)
    runtime = BoxRuntime(logger=logger, backends=[backend], session_ttl_sec=300)
    host_dir = tmp_path / 'mounted-workspace'
    host_dir.mkdir()
    service = BoxService(make_app(logger, [str(tmp_path)]), runtime=runtime)
    await service.initialize()

    result = await service.execute_sandbox_tool(
        {
            'cmd': 'pwd',
            'host_path': str(host_dir),
            'host_path_mode': BoxHostMountMode.READ_WRITE.value,
        },
        make_query(11),
    )

    assert result['ok'] is True
    assert backend.start_calls == ['11']


@pytest.mark.asyncio
async def test_box_service_uses_default_host_workspace_when_host_path_omitted(tmp_path):
    logger = Mock()
    backend = FakeBackend(logger)
    runtime = BoxRuntime(logger=logger, backends=[backend], session_ttl_sec=300)
    host_dir = tmp_path / 'default-workspace'
    host_dir.mkdir()
    app = make_app(logger, [str(tmp_path)])
    app.instance_config.data['box']['default_host_workspace'] = str(host_dir)
    service = BoxService(app, runtime=runtime)
    await service.initialize()

    result = await service.execute_sandbox_tool({'cmd': 'pwd'}, make_query(15))

    assert result['ok'] is True
    assert backend.start_calls == ['15']
    assert backend.exec_calls == [('15', 'pwd')]
    assert backend.start_specs[0].host_path == os.path.realpath(host_dir)


@pytest.mark.asyncio
async def test_box_service_rejects_host_mount_outside_allowed_roots(tmp_path):
    logger = Mock()
    backend = FakeBackend(logger)
    runtime = BoxRuntime(logger=logger, backends=[backend], session_ttl_sec=300)
    allowed_root = tmp_path / 'allowed'
    disallowed_root = tmp_path / 'disallowed'
    allowed_root.mkdir()
    disallowed_root.mkdir()
    service = BoxService(make_app(logger, [str(allowed_root)]), runtime=runtime)
    await service.initialize()

    with pytest.raises(BoxValidationError):
        await service.execute_sandbox_tool(
            {
                'cmd': 'pwd',
                'host_path': str(disallowed_root),
            },
            make_query(12),
        )


@pytest.mark.asyncio
async def test_box_runtime_rejects_host_mount_conflict_in_same_session(tmp_path):
    logger = Mock()
    backend = FakeBackend(logger)
    runtime = BoxRuntime(logger=logger, backends=[backend], session_ttl_sec=300)
    await runtime.initialize()

    first_host_dir = tmp_path / 'first'
    second_host_dir = tmp_path / 'second'
    first_host_dir.mkdir()
    second_host_dir.mkdir()

    first = BoxSpec.model_validate(
        {
            'cmd': 'echo first',
            'session_id': 'req-mount',
            'host_path': os.path.realpath(first_host_dir),
        }
    )
    second = BoxSpec.model_validate(
        {
            'cmd': 'echo second',
            'session_id': 'req-mount',
            'host_path': os.path.realpath(second_host_dir),
        }
    )

    await runtime.execute(first)

    with pytest.raises(BoxSessionConflictError):
        await runtime.execute(second)
