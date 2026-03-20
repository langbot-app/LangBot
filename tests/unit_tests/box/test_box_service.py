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
    BUILTIN_PROFILES,
    BoxExecutionResult,
    BoxExecutionStatus,
    BoxHostMountMode,
    BoxNetworkMode,
    BoxProfile,
    BoxSessionInfo,
    BoxSpec,
)
from langbot.pkg.box.runtime import BoxRuntime
from langbot.pkg.box.service import BoxService

_UTC = dt.timezone.utc


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
    return pipeline_query.Query.model_construct(query_id=query_id)


def make_app(logger: Mock, allowed_host_mount_roots: list[str] | None = None, profile: str = 'default'):
    return SimpleNamespace(
        logger=logger,
        instance_config=SimpleNamespace(
            data={
                'box': {
                    'profile': profile,
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


@pytest.mark.asyncio
async def test_truncate_short_output_unchanged():
    logger = Mock()
    backend = FakeBackendWithOutput(logger, stdout='hello world')
    runtime = BoxRuntime(logger=logger, backends=[backend], session_ttl_sec=300)
    service = BoxService(make_app(logger), runtime=runtime, output_limit_chars=100)
    await service.initialize()

    result = await service.execute_sandbox_tool({'cmd': 'echo hello'}, make_query(20))

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
    service = BoxService(make_app(logger), runtime=runtime, output_limit_chars=limit)
    await service.initialize()

    result = await service.execute_sandbox_tool({'cmd': 'cat big'}, make_query(21))

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
    service = BoxService(make_app(logger), runtime=runtime, output_limit_chars=200)
    await service.initialize()

    result = await service.execute_sandbox_tool({'cmd': 'echo a'}, make_query(22))

    assert result['stdout'] == exact_output
    assert result['stdout_truncated'] is False


@pytest.mark.asyncio
async def test_truncate_stderr_independently():
    logger = Mock()
    backend = FakeBackendWithOutput(logger, stdout='short', stderr='E' * 300)
    runtime = BoxRuntime(logger=logger, backends=[backend], session_ttl_sec=300)
    service = BoxService(make_app(logger), runtime=runtime, output_limit_chars=100)
    await service.initialize()

    result = await service.execute_sandbox_tool({'cmd': 'fail'}, make_query(23))

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
    service = BoxService(make_app(logger), runtime=runtime)
    await service.initialize()

    result = await service.execute_sandbox_tool({'cmd': 'echo hi'}, make_query(30))

    assert result['ok'] is True
    spec = backend.start_specs[0]
    assert spec.network == BoxNetworkMode.OFF
    assert spec.image == 'python:3.11-slim'
    assert spec.timeout_sec == 30


@pytest.mark.asyncio
async def test_profile_unlocked_field_can_be_overridden():
    """Tool call can override unlocked profile fields."""
    logger = Mock()
    backend = FakeBackend(logger)
    runtime = BoxRuntime(logger=logger, backends=[backend], session_ttl_sec=300)
    service = BoxService(make_app(logger), runtime=runtime)
    await service.initialize()

    result = await service.execute_sandbox_tool(
        {'cmd': 'echo hi', 'timeout_sec': 60, 'network': 'on'},
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
    service = BoxService(make_app(logger, profile='offline_readonly'), runtime=runtime)
    await service.initialize()

    result = await service.execute_sandbox_tool(
        {'cmd': 'echo hi', 'network': 'on', 'host_path_mode': 'rw'},
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
    service = BoxService(make_app(logger), runtime=runtime)
    await service.initialize()

    result = await service.execute_sandbox_tool(
        {'cmd': 'echo hi', 'timeout_sec': 999},
        make_query(33),
    )

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
    service = BoxService(make_app(logger), runtime=runtime)
    await service.initialize()

    await service.execute_sandbox_tool(
        {'cmd': 'echo hi', 'timeout_sec': timeout_value},
        make_query(34),
    )

    spec = backend.start_specs[0]
    assert spec.timeout_sec == 120


def test_unknown_profile_raises_error():
    """Config referencing a non-existent profile name raises immediately."""
    logger = Mock()
    with pytest.raises(BoxValidationError, match='unknown box profile'):
        BoxService(make_app(logger, profile='nonexistent'))


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
    service = BoxService(make_app(logger), runtime=runtime)
    await service.initialize()

    await service.execute_sandbox_tool({'cmd': 'echo hi'}, make_query(40))

    spec = backend.start_specs[0]
    profile = BUILTIN_PROFILES['default']
    assert spec.cpus == profile.cpus
    assert spec.memory_mb == profile.memory_mb
    assert spec.pids_limit == profile.pids_limit
    assert spec.read_only_rootfs == profile.read_only_rootfs


@pytest.mark.asyncio
async def test_profile_offline_readonly_locks_read_only_rootfs():
    """offline_readonly locks read_only_rootfs so it cannot be overridden."""
    logger = Mock()
    backend = FakeBackend(logger)
    runtime = BoxRuntime(logger=logger, backends=[backend], session_ttl_sec=300)
    service = BoxService(make_app(logger, profile='offline_readonly'), runtime=runtime)
    await service.initialize()

    await service.execute_sandbox_tool(
        {'cmd': 'echo hi', 'read_only_rootfs': False},
        make_query(41),
    )

    spec = backend.start_specs[0]
    assert spec.read_only_rootfs is True


@pytest.mark.asyncio
async def test_profile_network_extended_has_relaxed_limits():
    """network_extended profile provides higher resource limits."""
    logger = Mock()
    backend = FakeBackend(logger)
    runtime = BoxRuntime(logger=logger, backends=[backend], session_ttl_sec=300)
    service = BoxService(make_app(logger, profile='network_extended'), runtime=runtime)
    await service.initialize()

    await service.execute_sandbox_tool({'cmd': 'echo hi'}, make_query(42))

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
    service = BoxService(make_app(logger), runtime=runtime)
    await service.initialize()

    with pytest.raises(Exception):
        await service.execute_sandbox_tool({'cmd': 'echo hello'}, make_query(50))

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
    service = BoxService(make_app(logger), runtime=runtime)
    await service.initialize()

    for i in range(60):
        with pytest.raises(Exception):
            await service.execute_sandbox_tool({'cmd': 'fail'}, make_query(100 + i))

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
    service = BoxService(make_app(logger), runtime=runtime)
    await service.initialize()

    status = await service.get_status()
    assert status['profile'] == 'default'
    assert status['backend']['name'] == 'fake'
    assert status['backend']['available'] is True
    assert status['active_sessions'] == 0
    assert status['recent_error_count'] == 0
