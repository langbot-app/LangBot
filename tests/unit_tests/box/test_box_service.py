from __future__ import annotations

import asyncio
import datetime as dt
import os
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

import langbot_plugin.api.entities.builtin.pipeline.query as pipeline_query

from langbot_plugin.box.backend import BaseSandboxBackend
from langbot_plugin.box.client import BoxRuntimeClient, ActionRPCBoxClient
from langbot_plugin.box.errors import (
    BoxBackendUnavailableError,
    BoxSessionConflictError,
    BoxSessionNotFoundError,
    BoxValidationError,
)
from langbot_plugin.box.models import (
    BUILTIN_PROFILES,
    BoxExecutionResult,
    BoxExecutionStatus,
    BoxHostMountMode,
    BoxManagedProcessSpec,
    BoxNetworkMode,
    BoxSessionInfo,
    BoxSpec,
)
from langbot_plugin.box.runtime import BoxRuntime
from langbot.pkg.box.service import BoxService

_UTC = dt.timezone.utc


class _InProcessBoxRuntimeClient(BoxRuntimeClient):
    """Test-only client that wraps a BoxRuntime in-process (no HTTP)."""

    def __init__(self, logger, runtime=None):
        self._runtime = runtime or BoxRuntime(logger=logger)

    async def initialize(self):
        await self._runtime.initialize()

    async def init(self, config: dict):
        self._runtime.init(config)

    async def execute(self, spec):
        return await self._runtime.execute(spec)

    async def shutdown(self):
        await self._runtime.shutdown()

    async def get_status(self):
        return await self._runtime.get_status()

    async def get_sessions(self):
        return self._runtime.get_sessions()

    async def get_backend_info(self):
        return await self._runtime.get_backend_info()

    async def delete_session(self, session_id):
        await self._runtime.delete_session(session_id)

    async def create_session(self, spec):
        return await self._runtime.create_session(spec)

    async def start_managed_process(self, session_id: str, spec: BoxManagedProcessSpec):
        return await self._runtime.start_managed_process(session_id, spec)

    async def get_managed_process(self, session_id: str, process_id: str = 'default'):
        return self._runtime.get_managed_process(session_id, process_id)

    async def get_session(self, session_id: str):
        return self._runtime.get_session(session_id)


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
        now = dt.datetime.now(_UTC)
        return BoxSessionInfo(
            session_id=spec.session_id,
            backend_name=self.name,
            backend_session_id=f'backend-{spec.session_id}',
            image=spec.image,
            network=spec.network,
            host_path=spec.host_path,
            host_path_mode=spec.host_path_mode,
            mount_path=spec.mount_path,
            cpus=spec.cpus,
            memory_mb=spec.memory_mb,
            pids_limit=spec.pids_limit,
            read_only_rootfs=spec.read_only_rootfs,
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
    return pipeline_query.Query.model_construct(
        query_id=query_id,
        launcher_type='person',
        launcher_id='test_user',
        sender_id='test_user',
        variables={
            'launcher_type': 'person',
            'launcher_id': 'test_user',
            'sender_id': 'test_user',
            'query_id': str(query_id),
        },
    )


def make_app(
    logger: Mock,
    allowed_host_mount_roots: list[str] | None = None,
    profile: str = 'default',
    shared_host_root: str = '',
    workspace_quota_mb: int | None = None,
):
    box_config = {
        'profile': profile,
        'shared_host_root': shared_host_root,
        'allowed_host_mount_roots': allowed_host_mount_roots or [],
        'default_host_workspace': '',
    }
    if workspace_quota_mb is not None:
        box_config['workspace_quota_mb'] = workspace_quota_mb

    return SimpleNamespace(
        logger=logger,
        instance_config=SimpleNamespace(data={'box': box_config}),
    )


@pytest.mark.asyncio
async def test_box_service_without_explicit_client_initializes_internal_connector(monkeypatch: pytest.MonkeyPatch):
    connector = Mock()
    connector.client = Mock()
    connector.initialize = AsyncMock()

    monkeypatch.setattr('langbot.pkg.box.service.BoxRuntimeConnector', Mock(return_value=connector))

    service = BoxService(make_app(Mock()))
    await service.initialize()

    assert service.client is connector.client
    connector.initialize.assert_awaited_once()


@pytest.mark.asyncio
async def test_box_service_get_sessions_delegates_to_client():
    client = Mock()
    client.get_sessions = AsyncMock(return_value=[{'session_id': 'test-session'}])

    service = BoxService(make_app(Mock()), client=client)
    service._available = True

    sessions = await service.get_sessions()

    assert sessions == [{'session_id': 'test-session'}]
    client.get_sessions.assert_awaited_once()


def test_box_service_dispose_delegates_to_internal_connector(monkeypatch: pytest.MonkeyPatch):
    connector = Mock()
    connector.client = Mock()

    monkeypatch.setattr('langbot.pkg.box.service.BoxRuntimeConnector', Mock(return_value=connector))

    service = BoxService(make_app(Mock()))
    service.dispose()

    connector.dispose.assert_called_once()


@pytest.mark.asyncio
async def test_box_service_dispose_schedules_shutdown_on_event_loop(monkeypatch: pytest.MonkeyPatch):
    connector = Mock()
    connector.client = Mock()
    connector.dispose = Mock()

    monkeypatch.setattr('langbot.pkg.box.service.BoxRuntimeConnector', Mock(return_value=connector))

    app = make_app(Mock())
    loop = asyncio.get_running_loop()
    app.event_loop = loop

    service = BoxService(app)
    service.shutdown = AsyncMock()

    service.dispose()
    await asyncio.sleep(0)

    connector.dispose.assert_called_once()
    service.shutdown.assert_awaited_once()


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
    service = BoxService(make_app(logger), client=_InProcessBoxRuntimeClient(logger, runtime))
    await service.initialize()

    result = await service.execute_tool({'command': 'pwd'}, make_query(7))

    assert result['session_id'] == 'person_test_user'
    assert result['ok'] is True
    assert backend.start_calls == ['person_test_user']


@pytest.mark.asyncio
async def test_box_service_fails_closed_when_backend_unavailable():
    logger = Mock()
    backend = FakeBackend(logger, available=False)
    runtime = BoxRuntime(logger=logger, backends=[backend], session_ttl_sec=300)
    service = BoxService(make_app(logger), client=_InProcessBoxRuntimeClient(logger, runtime))
    await service.initialize()

    with pytest.raises(BoxBackendUnavailableError):
        await service.execute_tool({'command': 'echo hello'}, make_query(9))


@pytest.mark.asyncio
async def test_box_service_allows_host_mount_under_configured_root(tmp_path):
    logger = Mock()
    backend = FakeBackend(logger)
    runtime = BoxRuntime(logger=logger, backends=[backend], session_ttl_sec=300)
    host_dir = tmp_path / 'mounted-workspace'
    host_dir.mkdir()
    service = BoxService(make_app(logger, [str(tmp_path)]), client=_InProcessBoxRuntimeClient(logger, runtime))
    await service.initialize()

    result = await service.execute_spec_payload(
        {
            'cmd': 'pwd',
            'host_path': str(host_dir),
            'host_path_mode': BoxHostMountMode.READ_WRITE.value,
            'session_id': '11',
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
    service = BoxService(app, client=_InProcessBoxRuntimeClient(logger, runtime))
    await service.initialize()

    result = await service.execute_tool({'command': 'pwd'}, make_query(15))

    assert result['ok'] is True
    assert backend.start_calls == ['person_test_user']
    assert backend.exec_calls == [('person_test_user', 'pwd')]
    assert backend.start_specs[0].host_path == os.path.realpath(host_dir)


@pytest.mark.asyncio
async def test_box_service_creates_default_host_workspace_on_initialize(tmp_path):
    logger = Mock()
    backend = FakeBackend(logger)
    runtime = BoxRuntime(logger=logger, backends=[backend], session_ttl_sec=300)
    allowed_root = tmp_path / 'allowed-root'
    allowed_root.mkdir()
    default_host_workspace = allowed_root / 'default-workspace'
    app = make_app(logger, [str(allowed_root)])
    app.instance_config.data['box']['default_host_workspace'] = str(default_host_workspace)
    service = BoxService(app, client=_InProcessBoxRuntimeClient(logger, runtime))

    await service.initialize()

    assert default_host_workspace.is_dir()


@pytest.mark.asyncio
async def test_box_service_derives_workspace_and_allowed_root_from_shared_host_root(tmp_path):
    logger = Mock()
    backend = FakeBackend(logger)
    runtime = BoxRuntime(logger=logger, backends=[backend], session_ttl_sec=300)
    shared_root = tmp_path / 'shared-box-root'
    app = make_app(logger, shared_host_root=str(shared_root))
    service = BoxService(app, client=_InProcessBoxRuntimeClient(logger, runtime))

    await service.initialize()

    assert service.shared_host_root == os.path.realpath(shared_root)
    assert service.default_host_workspace == os.path.realpath(shared_root / 'default')
    assert service.allowed_host_mount_roots == [os.path.realpath(shared_root)]
    assert (shared_root / 'default').is_dir()


@pytest.mark.asyncio
async def test_box_service_rejects_host_mount_outside_allowed_roots(tmp_path):
    logger = Mock()
    backend = FakeBackend(logger)
    runtime = BoxRuntime(logger=logger, backends=[backend], session_ttl_sec=300)
    allowed_root = tmp_path / 'allowed'
    disallowed_root = tmp_path / 'disallowed'
    allowed_root.mkdir()
    disallowed_root.mkdir()
    service = BoxService(make_app(logger, [str(allowed_root)]), client=_InProcessBoxRuntimeClient(logger, runtime))
    await service.initialize()

    with pytest.raises(BoxValidationError):
        await service.execute_spec_payload(
            {
                'cmd': 'pwd',
                'host_path': str(disallowed_root),
                'session_id': '12',
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


@pytest.mark.asyncio
async def test_box_runtime_rejects_resource_limit_conflict_in_same_session():
    logger = Mock()
    backend = FakeBackend(logger)
    runtime = BoxRuntime(logger=logger, backends=[backend], session_ttl_sec=300)
    await runtime.initialize()

    first = BoxSpec.model_validate({'cmd': 'echo first', 'session_id': 'req-resource', 'cpus': 1.0})
    second = BoxSpec.model_validate({'cmd': 'echo second', 'session_id': 'req-resource', 'cpus': 2.0})

    await runtime.execute(first)

    with pytest.raises(BoxSessionConflictError):
        await runtime.execute(second)


# ── Truncation tests ──────────────────────────────────────────────────


class FakeBackendWithOutput(FakeBackend):
    """FakeBackend that returns configurable stdout/stderr."""

    def __init__(self, logger: Mock, stdout: str = '', stderr: str = ''):
        super().__init__(logger)
        self._stdout = stdout
        self._stderr = stderr

    async def exec(self, session: BoxSessionInfo, spec: BoxSpec) -> BoxExecutionResult:
        self.exec_calls.append((session.session_id, spec.cmd))
        return BoxExecutionResult(
            session_id=session.session_id,
            backend_name=self.name,
            status=BoxExecutionStatus.COMPLETED,
            exit_code=0,
            stdout=self._stdout,
            stderr=self._stderr,
            duration_ms=5,
        )


class FakeBackendWritingFiles(FakeBackend):
    """Fake backend that writes files into the mounted host workspace during exec."""

    def __init__(self, logger: Mock, files_to_write: list[tuple[str, int]]):
        super().__init__(logger)
        self._files_to_write = files_to_write

    async def exec(self, session: BoxSessionInfo, spec: BoxSpec) -> BoxExecutionResult:
        self.exec_calls.append((session.session_id, spec.cmd))
        if session.host_path:
            for relative_path, size in self._files_to_write:
                host_path = os.path.join(session.host_path, relative_path)
                os.makedirs(os.path.dirname(host_path), exist_ok=True)
                with open(host_path, 'wb') as f:
                    f.write(b'x' * size)
        return BoxExecutionResult(
            session_id=session.session_id,
            backend_name=self.name,
            status=BoxExecutionStatus.COMPLETED,
            exit_code=0,
            stdout='wrote files',
            stderr='',
            duration_ms=5,
        )


@pytest.mark.asyncio
async def test_truncate_short_output_unchanged():
    logger = Mock()
    backend = FakeBackendWithOutput(logger, stdout='hello world')
    runtime = BoxRuntime(logger=logger, backends=[backend], session_ttl_sec=300)
    service = BoxService(make_app(logger), client=_InProcessBoxRuntimeClient(logger, runtime), output_limit_chars=100)
    await service.initialize()

    result = await service.execute_tool({'command': 'echo hello'}, make_query(20))

    assert result['stdout'] == 'hello world'
    assert result['stdout_truncated'] is False


@pytest.mark.asyncio
async def test_truncate_preserves_head_and_tail():
    logger = Mock()
    # Build output: "AAAA...BBB..." where each section is identifiable
    head_marker = 'HEAD_START|'
    tail_marker = '|TAIL_END'
    filler = 'x' * 500
    big_output = f'{head_marker}{filler}{tail_marker}'

    backend = FakeBackendWithOutput(logger, stdout=big_output)
    runtime = BoxRuntime(logger=logger, backends=[backend], session_ttl_sec=300)
    limit = 100
    service = BoxService(make_app(logger), client=_InProcessBoxRuntimeClient(logger, runtime), output_limit_chars=limit)
    await service.initialize()

    result = await service.execute_tool({'command': 'cat big'}, make_query(21))

    assert result['stdout_truncated'] is True
    stdout = result['stdout']
    # Head part should contain the head marker
    assert stdout.startswith(head_marker)
    # Tail part should contain the tail marker
    assert stdout.endswith(tail_marker)
    # Should contain the truncation notice
    assert 'characters truncated' in stdout
    assert len(stdout) <= limit


@pytest.mark.asyncio
async def test_truncate_at_exact_limit_not_truncated():
    logger = Mock()
    exact_output = 'a' * 200
    backend = FakeBackendWithOutput(logger, stdout=exact_output)
    runtime = BoxRuntime(logger=logger, backends=[backend], session_ttl_sec=300)
    service = BoxService(make_app(logger), client=_InProcessBoxRuntimeClient(logger, runtime), output_limit_chars=200)
    await service.initialize()

    result = await service.execute_tool({'command': 'echo a'}, make_query(22))

    assert result['stdout'] == exact_output
    assert result['stdout_truncated'] is False


@pytest.mark.asyncio
async def test_truncate_stderr_independently():
    logger = Mock()
    backend = FakeBackendWithOutput(logger, stdout='short', stderr='E' * 300)
    runtime = BoxRuntime(logger=logger, backends=[backend], session_ttl_sec=300)
    service = BoxService(make_app(logger), client=_InProcessBoxRuntimeClient(logger, runtime), output_limit_chars=100)
    await service.initialize()

    result = await service.execute_tool({'command': 'fail'}, make_query(23))

    assert result['stdout_truncated'] is False
    assert result['stderr_truncated'] is True
    assert 'characters truncated' in result['stderr']
    assert len(result['stderr']) <= 100


# ── Profile tests ─────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_profile_default_provides_defaults():
    """When tool call omits network/image, profile defaults are used."""
    logger = Mock()
    backend = FakeBackend(logger)
    runtime = BoxRuntime(logger=logger, backends=[backend], session_ttl_sec=300)
    service = BoxService(make_app(logger), client=_InProcessBoxRuntimeClient(logger, runtime))
    await service.initialize()

    result = await service.execute_tool({'command': 'echo hi'}, make_query(30))

    assert result['ok'] is True
    spec = backend.start_specs[0]
    assert spec.network == BoxNetworkMode.OFF
    assert spec.image == 'rockchin/langbot-sandbox:latest'
    assert spec.timeout_sec == 30


@pytest.mark.asyncio
async def test_profile_unlocked_field_can_be_overridden():
    """Spec payload can override unlocked profile fields."""
    logger = Mock()
    backend = FakeBackend(logger)
    runtime = BoxRuntime(logger=logger, backends=[backend], session_ttl_sec=300)
    service = BoxService(make_app(logger), client=_InProcessBoxRuntimeClient(logger, runtime))
    await service.initialize()

    result = await service.execute_spec_payload(
        {'cmd': 'echo hi', 'timeout_sec': 60, 'network': 'on', 'session_id': '31'},
        make_query(31),
    )

    assert result['ok'] is True
    spec = backend.start_specs[0]
    assert spec.timeout_sec == 60
    assert spec.network == BoxNetworkMode.ON


@pytest.mark.asyncio
async def test_profile_locked_field_cannot_be_overridden():
    """offline_readonly profile locks network and host_path_mode."""
    logger = Mock()
    backend = FakeBackend(logger)
    runtime = BoxRuntime(logger=logger, backends=[backend], session_ttl_sec=300)
    service = BoxService(
        make_app(logger, profile='offline_readonly'), client=_InProcessBoxRuntimeClient(logger, runtime)
    )
    await service.initialize()

    result = await service.execute_spec_payload(
        {'cmd': 'echo hi', 'network': 'on', 'host_path_mode': 'rw', 'session_id': '32'},
        make_query(32),
    )

    assert result['ok'] is True
    spec = backend.start_specs[0]
    assert spec.network == BoxNetworkMode.OFF
    assert spec.host_path_mode == BoxHostMountMode.READ_ONLY


@pytest.mark.asyncio
async def test_profile_timeout_clamped_to_max():
    """timeout_sec exceeding max_timeout_sec is clamped."""
    logger = Mock()
    backend = FakeBackend(logger)
    runtime = BoxRuntime(logger=logger, backends=[backend], session_ttl_sec=300)
    service = BoxService(make_app(logger), client=_InProcessBoxRuntimeClient(logger, runtime))
    await service.initialize()

    result = await service.execute_tool({'command': 'echo hi', 'timeout_sec': 999}, make_query(33))

    assert result['ok'] is True
    spec = backend.start_specs[0]
    # default profile max_timeout_sec = 120
    assert spec.timeout_sec == 120


@pytest.mark.asyncio
@pytest.mark.parametrize('timeout_value', ['999', 999.0])
async def test_profile_timeout_clamped_for_coercible_inputs(timeout_value):
    logger = Mock()
    backend = FakeBackend(logger)
    runtime = BoxRuntime(logger=logger, backends=[backend], session_ttl_sec=300)
    service = BoxService(make_app(logger), client=_InProcessBoxRuntimeClient(logger, runtime))
    await service.initialize()

    await service.execute_tool({'command': 'echo hi', 'timeout_sec': timeout_value}, make_query(34))

    spec = backend.start_specs[0]
    assert spec.timeout_sec == 120


def test_unknown_profile_raises_error():
    """Config referencing a non-existent profile name raises immediately."""
    logger = Mock()
    runtime = BoxRuntime(logger=logger, backends=[FakeBackend(logger)], session_ttl_sec=300)
    with pytest.raises(BoxValidationError, match='unknown box profile'):
        BoxService(make_app(logger, profile='nonexistent'), client=_InProcessBoxRuntimeClient(logger, runtime))


def test_builtin_profiles_are_consistent():
    """Basic sanity check on all built-in profiles."""
    assert 'default' in BUILTIN_PROFILES
    assert 'offline_readonly' in BUILTIN_PROFILES
    assert 'network_basic' in BUILTIN_PROFILES
    assert 'network_extended' in BUILTIN_PROFILES

    offline = BUILTIN_PROFILES['offline_readonly']
    assert offline.network == BoxNetworkMode.OFF
    assert offline.host_path_mode == BoxHostMountMode.READ_ONLY
    assert 'network' in offline.locked
    assert 'host_path_mode' in offline.locked
    assert 'read_only_rootfs' in offline.locked
    assert offline.max_timeout_sec <= BUILTIN_PROFILES['default'].max_timeout_sec

    basic = BUILTIN_PROFILES['network_basic']
    assert basic.network == BoxNetworkMode.ON
    assert basic.read_only_rootfs is True

    extended = BUILTIN_PROFILES['network_extended']
    assert extended.network == BoxNetworkMode.ON
    assert extended.read_only_rootfs is False
    assert extended.cpus > BUILTIN_PROFILES['default'].cpus
    assert extended.memory_mb > BUILTIN_PROFILES['default'].memory_mb


@pytest.mark.asyncio
async def test_profile_default_applies_resource_limits():
    """Default profile resource limits are applied to BoxSpec."""
    logger = Mock()
    backend = FakeBackend(logger)
    runtime = BoxRuntime(logger=logger, backends=[backend], session_ttl_sec=300)
    service = BoxService(make_app(logger), client=_InProcessBoxRuntimeClient(logger, runtime))
    await service.initialize()

    await service.execute_tool({'command': 'echo hi'}, make_query(40))

    spec = backend.start_specs[0]
    profile = BUILTIN_PROFILES['default']
    assert spec.cpus == profile.cpus
    assert spec.memory_mb == profile.memory_mb
    assert spec.pids_limit == profile.pids_limit
    assert spec.read_only_rootfs == profile.read_only_rootfs
    assert spec.workspace_quota_mb == profile.workspace_quota_mb


@pytest.mark.asyncio
async def test_box_service_applies_workspace_quota_from_config(tmp_path):
    logger = Mock()
    backend = FakeBackend(logger)
    runtime = BoxRuntime(logger=logger, backends=[backend], session_ttl_sec=300)
    host_dir = tmp_path / 'default-workspace'
    host_dir.mkdir()
    app = make_app(logger, [str(tmp_path)], workspace_quota_mb=32)
    app.instance_config.data['box']['default_host_workspace'] = str(host_dir)
    service = BoxService(app, client=_InProcessBoxRuntimeClient(logger, runtime))

    await service.initialize()
    await service.execute_tool({'command': 'echo hi'}, make_query(43))

    assert backend.start_specs[0].workspace_quota_mb == 32


@pytest.mark.asyncio
async def test_box_service_rejects_execution_when_workspace_already_exceeds_quota(tmp_path):
    logger = Mock()
    backend = FakeBackend(logger)
    runtime = BoxRuntime(logger=logger, backends=[backend], session_ttl_sec=300)
    host_dir = tmp_path / 'quota-workspace'
    host_dir.mkdir()
    (host_dir / 'already-too-large.bin').write_bytes(b'x' * (2 * 1024 * 1024))
    app = make_app(logger, [str(tmp_path)], workspace_quota_mb=1)
    app.instance_config.data['box']['default_host_workspace'] = str(host_dir)
    service = BoxService(app, client=_InProcessBoxRuntimeClient(logger, runtime))

    await service.initialize()

    with pytest.raises(BoxValidationError, match='workspace quota exceeded before execution'):
        await service.execute_tool({'command': 'echo hi'}, make_query(44))

    assert backend.start_calls == []


@pytest.mark.asyncio
async def test_box_service_rejects_and_cleans_up_when_execution_exceeds_workspace_quota(tmp_path):
    logger = Mock()
    backend = FakeBackendWritingFiles(logger, files_to_write=[('output.bin', 2 * 1024 * 1024)])
    runtime = BoxRuntime(logger=logger, backends=[backend], session_ttl_sec=300)
    host_dir = tmp_path / 'quota-workspace-post'
    host_dir.mkdir()
    app = make_app(logger, [str(tmp_path)], workspace_quota_mb=1)
    app.instance_config.data['box']['default_host_workspace'] = str(host_dir)
    service = BoxService(app, client=_InProcessBoxRuntimeClient(logger, runtime))

    await service.initialize()

    with pytest.raises(BoxValidationError, match='workspace quota exceeded after execution'):
        await service.execute_tool({'command': 'generate-output'}, make_query(45))

    assert backend.start_calls == ['person_test_user']
    assert backend.stop_calls == ['person_test_user']


@pytest.mark.asyncio
async def test_profile_offline_readonly_locks_read_only_rootfs():
    """offline_readonly locks read_only_rootfs so it cannot be overridden."""
    logger = Mock()
    backend = FakeBackend(logger)
    runtime = BoxRuntime(logger=logger, backends=[backend], session_ttl_sec=300)
    service = BoxService(
        make_app(logger, profile='offline_readonly'), client=_InProcessBoxRuntimeClient(logger, runtime)
    )
    await service.initialize()

    await service.execute_spec_payload(
        {'cmd': 'echo hi', 'read_only_rootfs': False, 'session_id': '41'}, make_query(41)
    )

    spec = backend.start_specs[0]
    assert spec.read_only_rootfs is True


@pytest.mark.asyncio
async def test_profile_network_extended_has_relaxed_limits():
    """network_extended profile provides higher resource limits."""
    logger = Mock()
    backend = FakeBackend(logger)
    runtime = BoxRuntime(logger=logger, backends=[backend], session_ttl_sec=300)
    service = BoxService(
        make_app(logger, profile='network_extended'), client=_InProcessBoxRuntimeClient(logger, runtime)
    )
    await service.initialize()

    await service.execute_tool({'command': 'echo hi'}, make_query(42))

    spec = backend.start_specs[0]
    assert spec.network == BoxNetworkMode.ON
    assert spec.cpus == 2.0
    assert spec.memory_mb == 1024
    assert spec.read_only_rootfs is False


def test_box_spec_validates_resource_limits():
    """BoxSpec rejects invalid resource limit values."""
    with pytest.raises(Exception):
        BoxSpec.model_validate({'cmd': 'echo', 'session_id': 's1', 'cpus': 0})
    with pytest.raises(Exception):
        BoxSpec.model_validate({'cmd': 'echo', 'session_id': 's1', 'memory_mb': 10})
    with pytest.raises(Exception):
        BoxSpec.model_validate({'cmd': 'echo', 'session_id': 's1', 'pids_limit': 0})
    with pytest.raises(Exception):
        BoxSpec.model_validate({'cmd': 'echo', 'session_id': 's1', 'workspace_quota_mb': -1})


# ── Observability tests ───────────────────────────────────────────────


@pytest.mark.asyncio
async def test_runtime_get_status_reports_backend_and_sessions():
    logger = Mock()
    backend = FakeBackend(logger)
    runtime = BoxRuntime(logger=logger, backends=[backend], session_ttl_sec=300)
    await runtime.initialize()

    status = await runtime.get_status()
    assert status['backend']['name'] == 'fake'
    assert status['backend']['available'] is True
    assert status['active_sessions'] == 0

    await runtime.execute(BoxSpec.model_validate({'cmd': 'echo', 'session_id': 'obs-1'}))
    status = await runtime.get_status()
    assert status['active_sessions'] == 1


@pytest.mark.asyncio
async def test_runtime_get_sessions_returns_session_info():
    logger = Mock()
    backend = FakeBackend(logger)
    runtime = BoxRuntime(logger=logger, backends=[backend], session_ttl_sec=300)
    await runtime.initialize()

    await runtime.execute(BoxSpec.model_validate({'cmd': 'echo', 'session_id': 'obs-2'}))
    sessions = runtime.get_sessions()
    assert len(sessions) == 1
    assert sessions[0]['session_id'] == 'obs-2'
    assert sessions[0]['backend_name'] == 'fake'
    assert 'created_at' in sessions[0]
    assert 'last_used_at' in sessions[0]


@pytest.mark.asyncio
async def test_runtime_get_backend_info_when_no_backend():
    logger = Mock()
    backend = FakeBackend(logger, available=False)
    runtime = BoxRuntime(logger=logger, backends=[backend], session_ttl_sec=300)
    await runtime.initialize()

    info = await runtime.get_backend_info()
    assert info['name'] is None
    assert info['available'] is False


@pytest.mark.asyncio
async def test_service_records_errors_on_failure():
    logger = Mock()
    backend = FakeBackend(logger, available=False)
    runtime = BoxRuntime(logger=logger, backends=[backend], session_ttl_sec=300)
    service = BoxService(make_app(logger), client=_InProcessBoxRuntimeClient(logger, runtime))
    await service.initialize()

    with pytest.raises(Exception):
        await service.execute_tool({'command': 'echo hello'}, make_query(50))

    errors = service.get_recent_errors()
    assert len(errors) == 1
    assert errors[0]['type'] == 'BoxBackendUnavailableError'
    assert errors[0]['query_id'] == '50'
    assert 'timestamp' in errors[0]


@pytest.mark.asyncio
async def test_service_error_ring_buffer_capped():
    logger = Mock()
    backend = FakeBackend(logger, available=False)
    runtime = BoxRuntime(logger=logger, backends=[backend], session_ttl_sec=300)
    service = BoxService(make_app(logger), client=_InProcessBoxRuntimeClient(logger, runtime))
    await service.initialize()

    for i in range(60):
        with pytest.raises(Exception):
            await service.execute_tool({'command': 'fail'}, make_query(100 + i))

    errors = service.get_recent_errors()
    assert len(errors) == 50
    # Oldest should have been evicted, newest kept
    assert errors[0]['query_id'] == '110'
    assert errors[-1]['query_id'] == '159'


@pytest.mark.asyncio
async def test_service_get_status_aggregates_runtime_and_profile():
    logger = Mock()
    backend = FakeBackend(logger)
    runtime = BoxRuntime(logger=logger, backends=[backend], session_ttl_sec=300)
    service = BoxService(make_app(logger), client=_InProcessBoxRuntimeClient(logger, runtime))
    await service.initialize()

    status = await service.get_status()
    assert status['profile'] == 'default'
    assert status['backend']['name'] == 'fake'
    assert status['backend']['available'] is True
    assert status['active_sessions'] == 0
    assert status['recent_error_count'] == 0


# ── In-process RPC client/server tests ─────────────────────────────────


class _QueueConnection:
    """In-process Connection backed by asyncio Queues — no real IO."""

    def __init__(self, rx: asyncio.Queue[str], tx: asyncio.Queue[str]):
        self._rx = rx
        self._tx = tx

    async def send(self, message: str) -> None:
        await self._tx.put(message)

    async def receive(self) -> str:
        return await self._rx.get()

    async def close(self) -> None:
        pass


def _make_queue_connection_pair():
    """Return (client_conn, server_conn) linked by queues."""
    c2s: asyncio.Queue[str] = asyncio.Queue()
    s2c: asyncio.Queue[str] = asyncio.Queue()
    client_conn = _QueueConnection(rx=s2c, tx=c2s)
    server_conn = _QueueConnection(rx=c2s, tx=s2c)
    return client_conn, server_conn


async def _make_rpc_pair(runtime: BoxRuntime):
    """Create an in-process (ActionRPCBoxClient, server_task, client_task) connected via queues."""
    from langbot_plugin.box.server import BoxServerHandler
    from langbot_plugin.runtime.io.handler import Handler

    client_conn, server_conn = _make_queue_connection_pair()

    server_handler = BoxServerHandler(server_conn, runtime)
    server_task = asyncio.create_task(server_handler.run())

    client_handler = Handler.__new__(Handler)
    Handler.__init__(client_handler, client_conn)
    client_task = asyncio.create_task(client_handler.run())

    client = ActionRPCBoxClient(logger=Mock())
    client.set_handler(client_handler)

    return client, server_task, client_task


@pytest.mark.asyncio
async def test_rpc_client_execute():
    """ActionRPCBoxClient correctly calls server and parses result."""
    logger = Mock()
    backend = FakeBackend(logger)
    runtime = BoxRuntime(logger=logger, backends=[backend], session_ttl_sec=300)
    await runtime.initialize()

    client, server_task, client_task = await _make_rpc_pair(runtime)
    try:
        spec = BoxSpec.model_validate({'cmd': 'echo remote', 'session_id': 'r-1'})
        result = await client.execute(spec)

        assert result.session_id == 'r-1'
        assert result.status == BoxExecutionStatus.COMPLETED
        assert result.exit_code == 0
        assert result.stdout == 'executed: echo remote'
    finally:
        server_task.cancel()
        client_task.cancel()
        await runtime.shutdown()


@pytest.mark.asyncio
async def test_rpc_client_get_sessions():
    logger = Mock()
    backend = FakeBackend(logger)
    runtime = BoxRuntime(logger=logger, backends=[backend], session_ttl_sec=300)
    await runtime.initialize()

    client, server_task, client_task = await _make_rpc_pair(runtime)
    try:
        spec = BoxSpec.model_validate({'cmd': 'echo hi', 'session_id': 'r-2'})
        await client.execute(spec)

        sessions = await client.get_sessions()
        assert len(sessions) == 1
        assert sessions[0]['session_id'] == 'r-2'
    finally:
        server_task.cancel()
        client_task.cancel()
        await runtime.shutdown()


@pytest.mark.asyncio
async def test_rpc_client_get_status():
    logger = Mock()
    backend = FakeBackend(logger)
    runtime = BoxRuntime(logger=logger, backends=[backend], session_ttl_sec=300)
    await runtime.initialize()

    client, server_task, client_task = await _make_rpc_pair(runtime)
    try:
        status = await client.get_status()

        assert 'backend' in status
        assert 'active_sessions' in status
    finally:
        server_task.cancel()
        client_task.cancel()
        await runtime.shutdown()


@pytest.mark.asyncio
async def test_rpc_client_get_backend_info():
    logger = Mock()
    backend = FakeBackend(logger)
    runtime = BoxRuntime(logger=logger, backends=[backend], session_ttl_sec=300)
    await runtime.initialize()

    client, server_task, client_task = await _make_rpc_pair(runtime)
    try:
        info = await client.get_backend_info()

        assert info['name'] == 'fake'
        assert info['available'] is True
    finally:
        server_task.cancel()
        client_task.cancel()
        await runtime.shutdown()


# ── RPC-based delete/create/conflict tests ────────────────────────────


@pytest.mark.asyncio
async def test_rpc_client_delete_session():
    logger = Mock()
    backend = FakeBackend(logger)
    runtime = BoxRuntime(logger=logger, backends=[backend], session_ttl_sec=300)
    await runtime.initialize()

    client, server_task, client_task = await _make_rpc_pair(runtime)
    try:
        spec = BoxSpec.model_validate({'cmd': 'echo hi', 'session_id': 'r-del-1'})
        await client.execute(spec)

        await client.delete_session('r-del-1')

        sessions = await client.get_sessions()
        assert len(sessions) == 0
    finally:
        server_task.cancel()
        client_task.cancel()
        await runtime.shutdown()


@pytest.mark.asyncio
async def test_rpc_client_delete_session_raises_not_found():
    logger = Mock()
    backend = FakeBackend(logger)
    runtime = BoxRuntime(logger=logger, backends=[backend], session_ttl_sec=300)
    await runtime.initialize()

    client, server_task, client_task = await _make_rpc_pair(runtime)
    try:
        with pytest.raises(BoxSessionNotFoundError):
            await client.delete_session('nonexistent')
    finally:
        server_task.cancel()
        client_task.cancel()
        await runtime.shutdown()


@pytest.mark.asyncio
async def test_rpc_client_create_session():
    logger = Mock()
    backend = FakeBackend(logger)
    runtime = BoxRuntime(logger=logger, backends=[backend], session_ttl_sec=300)
    await runtime.initialize()

    client, server_task, client_task = await _make_rpc_pair(runtime)
    try:
        spec = BoxSpec.model_validate({'cmd': 'placeholder', 'session_id': 'r-create-1'})
        info = await client.create_session(spec)
        assert info['session_id'] == 'r-create-1'
        assert info['backend_name'] == 'fake'

        sessions = await client.get_sessions()
        assert len(sessions) == 1
    finally:
        server_task.cancel()
        client_task.cancel()
        await runtime.shutdown()


@pytest.mark.asyncio
async def test_rpc_client_exec_raises_conflict_error():
    logger = Mock()
    backend = FakeBackend(logger)
    runtime = BoxRuntime(logger=logger, backends=[backend], session_ttl_sec=300)
    await runtime.initialize()

    client, server_task, client_task = await _make_rpc_pair(runtime)
    try:
        spec1 = BoxSpec.model_validate({'cmd': 'echo first', 'session_id': 'r-conflict-1', 'network': 'off'})
        await client.execute(spec1)

        spec2 = BoxSpec.model_validate({'cmd': 'echo second', 'session_id': 'r-conflict-1', 'network': 'on'})
        with pytest.raises(BoxSessionConflictError):
            await client.execute(spec2)
    finally:
        server_task.cancel()
        client_task.cancel()
        await runtime.shutdown()


# ── BoxHostMountMode.NONE tests ─────────────────────────────────────


class TestBoxHostMountModeNone:
    def test_none_mode_is_valid_enum(self):
        assert BoxHostMountMode.NONE.value == 'none'

    def test_spec_with_none_mode_skips_workdir_check(self):
        """When host_path_mode is NONE, workdir validation is skipped."""
        spec = BoxSpec(
            session_id='test',
            cmd='echo hi',
            host_path='/home/user/data',
            host_path_mode=BoxHostMountMode.NONE,
            workdir='/opt/custom',  # Not under /workspace, should be allowed
        )
        assert spec.host_path_mode == BoxHostMountMode.NONE
        assert spec.workdir == '/opt/custom'

    def test_spec_with_rw_mode_requires_workspace_workdir(self):
        """When host_path_mode is RW, workdir must be under mount_path."""
        with pytest.raises(Exception):
            BoxSpec(
                session_id='test',
                cmd='echo hi',
                host_path='/home/user/data',
                host_path_mode=BoxHostMountMode.READ_WRITE,
                workdir='/opt/custom',
            )

    def test_spec_with_ro_mode_requires_workspace_workdir(self):
        """When host_path_mode is RO, workdir must be under mount_path."""
        with pytest.raises(Exception):
            BoxSpec(
                session_id='test',
                cmd='echo hi',
                host_path='/home/user/data',
                host_path_mode=BoxHostMountMode.READ_ONLY,
                workdir='/opt/custom',
            )

    def test_spec_with_custom_mount_path_allows_matching_workdir(self):
        spec = BoxSpec(
            session_id='test',
            cmd='echo hi',
            host_path='/home/user/data',
            host_path_mode=BoxHostMountMode.READ_WRITE,
            mount_path='/project',
            workdir='/project/src',
        )
        assert spec.mount_path == '/project'
        assert spec.workdir == '/project/src'

    def test_spec_with_custom_mount_path_rejects_outside_workdir(self):
        with pytest.raises(Exception):
            BoxSpec(
                session_id='test',
                cmd='echo hi',
                host_path='/home/user/data',
                host_path_mode=BoxHostMountMode.READ_WRITE,
                mount_path='/project',
                workdir='/workspace',
            )
