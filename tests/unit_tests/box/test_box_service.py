from __future__ import annotations

import asyncio
import datetime as dt
import os
import tempfile
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

    async def stop_managed_process(self, session_id: str, process_id: str = 'default'):
        await self._runtime.stop_managed_process(session_id, process_id)

    async def get_session(self, session_id: str):
        return self._runtime.get_session(session_id)

    async def init(self, config: dict) -> None:
        self._runtime.init(config)


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
    allowed_mount_roots: list[str] | None = None,
    profile: str = 'default',
    host_root: str = '',
    workspace_quota_mb: int | None = None,
    enabled: bool = True,
    force_box_session_id_template: str = '',
):
    box_config = {
        'enabled': enabled,
        'backend': 'local',
        'runtime': {'endpoint': ''},
        'local': {
            'profile': profile,
            'host_root': host_root,
            'allowed_mount_roots': allowed_mount_roots or [],
            'default_workspace': '',
        },
        'e2b': {'api_key': '', 'api_url': '', 'template': ''},
    }
    if workspace_quota_mb is not None:
        box_config['local']['workspace_quota_mb'] = workspace_quota_mb

    return SimpleNamespace(
        logger=logger,
        instance_config=SimpleNamespace(
            data={
                'box': box_config,
                'system': {'limitation': {'force_box_session_id_template': force_box_session_id_template}},
            }
        ),
    )


def test_resolve_box_session_id_reads_current_runner_config():
    query = make_query(101)
    query.pipeline_config = {
        'ai': {
            'runner': {'id': 'plugin:langbot/local-agent/default'},
            'runner_config': {
                'plugin:langbot/local-agent/default': {
                    'box-session-id-template': 'bot-{launcher_id}-{sender_id}',
                },
            },
        },
    }
    service = BoxService(make_app(Mock()), client=Mock(spec=BoxRuntimeClient))

    assert service.resolve_box_session_id(query) == 'bot-test_user-test_user'


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


class TestSharesFilesystemWithBox:
    """``shares_filesystem_with_box`` must reflect the real LangBot<->Box
    filesystem topology, which is derived from the connector transport:

    - stdio (local child process) → shared filesystem → True
    - WebSocket (Docker / sidecar / --standalone-box / remote) → separated → False

    This drives whether LangBot validates Box-reported skill paths locally.
    Getting it wrong silently drops every skill in separated deployments.
    """

    def test_true_for_stdio_connector(self, monkeypatch: pytest.MonkeyPatch):
        # Non-Docker Unix, no endpoint, not standalone → stdio transport.
        monkeypatch.setattr('langbot.pkg.utils.platform.get_platform', lambda: 'linux')
        monkeypatch.setattr('langbot.pkg.utils.platform.standalone_box', False)

        service = BoxService(make_app(Mock()))

        assert service._runtime_connector is not None
        assert service._runtime_connector.uses_websocket() is False
        assert service.shares_filesystem_with_box is True

    def test_false_for_websocket_connector_via_endpoint(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setattr('langbot.pkg.utils.platform.get_platform', lambda: 'linux')
        monkeypatch.setattr('langbot.pkg.utils.platform.standalone_box', False)
        app = make_app(Mock())
        app.instance_config.data['box']['runtime']['endpoint'] = 'ws://pod-x-box:5410'

        service = BoxService(app)

        assert service._runtime_connector is not None
        assert service._runtime_connector.uses_websocket() is True
        assert service.shares_filesystem_with_box is False

    def test_false_for_websocket_connector_in_docker(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setattr('langbot.pkg.utils.platform.get_platform', lambda: 'docker')
        monkeypatch.setattr('langbot.pkg.utils.platform.standalone_box', False)

        service = BoxService(make_app(Mock()))

        assert service.shares_filesystem_with_box is False

    def test_false_when_client_injected_without_connector(self):
        # Injected client (no connector) → unknown topology → conservative False
        # so LangBot never wrongly drops Box-reported skills.
        service = BoxService(make_app(Mock()), client=Mock(spec=BoxRuntimeClient))

        assert service._runtime_connector is None
        assert service.shares_filesystem_with_box is False

    def test_explicit_override_wins(self):
        service = BoxService(make_app(Mock()), client=Mock(spec=BoxRuntimeClient))

        service._shares_filesystem_with_box_override = True
        assert service.shares_filesystem_with_box is True

        service._shares_filesystem_with_box_override = False
        assert service.shares_filesystem_with_box is False


def test_separated_box_runtime_does_not_create_default_workspace_in_langbot(tmp_path):
    logger = Mock()
    runtime = BoxRuntime(logger=logger, backends=[FakeBackend(logger)], session_ttl_sec=300)
    host_root = tmp_path / 'box'
    service = BoxService(make_app(logger, host_root=str(host_root)), client=_InProcessBoxRuntimeClient(logger, runtime))
    service._shares_filesystem_with_box_override = False

    service._ensure_default_workspace()

    assert not (host_root / 'default').exists()


def test_separated_box_runtime_allows_box_owned_missing_host_path(tmp_path):
    logger = Mock()
    runtime = BoxRuntime(logger=logger, backends=[FakeBackend(logger)], session_ttl_sec=300)
    host_root = tmp_path / 'box'
    service = BoxService(make_app(logger, host_root=str(host_root)), client=_InProcessBoxRuntimeClient(logger, runtime))
    service._shares_filesystem_with_box_override = False

    spec = service.build_spec({'cmd': 'echo hi', 'session_id': 'missing-host-path'})

    assert spec.host_path == str(host_root / 'default')
    assert not (host_root / 'default').exists()


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
async def test_box_service_session_id_uses_query_attributes_without_variables():
    logger = Mock()
    backend = FakeBackend(logger)
    runtime = BoxRuntime(logger=logger, backends=[backend], session_ttl_sec=300)
    service = BoxService(make_app(logger), client=_InProcessBoxRuntimeClient(logger, runtime))
    await service.initialize()

    query = pipeline_query.Query.model_construct(query_id=7, launcher_type='group', launcher_id='room-1')
    result = await service.execute_tool({'command': 'pwd'}, query)

    assert result['session_id'] == 'group_room-1'
    assert result['ok'] is True
    assert backend.start_calls == ['group_room-1']


@pytest.mark.asyncio
async def test_box_service_session_id_falls_back_to_query_id_for_synthetic_queries():
    logger = Mock()
    backend = FakeBackend(logger)
    runtime = BoxRuntime(logger=logger, backends=[backend], session_ttl_sec=300)
    service = BoxService(make_app(logger), client=_InProcessBoxRuntimeClient(logger, runtime))
    await service.initialize()

    query = pipeline_query.Query.model_construct(query_id=7)
    result = await service.execute_tool({'command': 'pwd'}, query)

    assert result['session_id'] == 'query_7'
    assert result['ok'] is True
    assert backend.start_calls == ['query_7']


@pytest.mark.asyncio
async def test_box_service_forced_global_scope_overrides_pipeline_template():
    """SaaS guard: a non-empty ``force_box_session_id_template`` pins every
    query to one shared sandbox regardless of the pipeline's own scope."""
    logger = Mock()
    backend = FakeBackend(logger)
    runtime = BoxRuntime(logger=logger, backends=[backend], session_ttl_sec=300)
    service = BoxService(
        make_app(logger, force_box_session_id_template='{global}'),
        client=_InProcessBoxRuntimeClient(logger, runtime),
    )
    await service.initialize()

    # Two distinct callers that would otherwise get separate sandboxes.
    q1 = pipeline_query.Query.model_construct(query_id=1, launcher_type='group', launcher_id='room-1')
    q2 = pipeline_query.Query.model_construct(query_id=2, launcher_type='person', launcher_id='alice')

    r1 = await service.execute_tool({'command': 'pwd'}, q1)
    r2 = await service.execute_tool({'command': 'pwd'}, q2)

    assert r1['session_id'] == 'global'
    assert r2['session_id'] == 'global'
    # Only one sandbox was ever started — the shared global one.
    assert backend.start_calls == ['global']


def test_box_service_forced_template_ignores_pipeline_config():
    """The forced template wins even when the pipeline explicitly sets a
    per-user scope — proving the override is not bypassable via pipeline config."""
    logger = Mock()
    service = BoxService(
        make_app(logger, force_box_session_id_template='{global}'),
        client=Mock(spec=BoxRuntimeClient),
    )
    query = pipeline_query.Query.model_construct(
        query_id=7,
        launcher_type='person',
        launcher_id='test_user',
        sender_id='test_user',
        pipeline_config={
            'ai': {'local-agent': {'box-session-id-template': '{launcher_type}_{launcher_id}_{sender_id}'}}
        },
    )

    assert service.resolve_box_session_id(query) == 'global'


def test_box_service_empty_forced_template_respects_pipeline_config():
    """An empty/whitespace forced template is a no-op: the pipeline's own
    scope template is honoured (default non-SaaS behaviour)."""
    logger = Mock()
    service = BoxService(
        make_app(logger, force_box_session_id_template='   '),
        client=Mock(spec=BoxRuntimeClient),
    )
    query = pipeline_query.Query.model_construct(
        query_id=7,
        launcher_type='group',
        launcher_id='room-1',
        pipeline_config={'ai': {'local-agent': {'box-session-id-template': '{launcher_type}_{launcher_id}'}}},
    )

    assert service.resolve_box_session_id(query) == 'group_room-1'


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
async def test_box_service_uses_default_workspace_when_host_path_omitted(tmp_path):
    logger = Mock()
    backend = FakeBackend(logger)
    runtime = BoxRuntime(logger=logger, backends=[backend], session_ttl_sec=300)
    host_dir = tmp_path / 'default-workspace'
    host_dir.mkdir()
    app = make_app(logger, [str(tmp_path)])
    app.instance_config.data['box']['local']['default_workspace'] = str(host_dir)
    service = BoxService(app, client=_InProcessBoxRuntimeClient(logger, runtime))
    await service.initialize()

    result = await service.execute_tool({'command': 'pwd'}, make_query(15))

    assert result['ok'] is True
    assert backend.start_calls == ['person_test_user']
    assert backend.exec_calls == [('person_test_user', 'pwd')]
    assert backend.start_specs[0].host_path == os.path.realpath(host_dir)


@pytest.mark.asyncio
async def test_box_service_creates_default_workspace_on_initialize(tmp_path):
    logger = Mock()
    backend = FakeBackend(logger)
    runtime = BoxRuntime(logger=logger, backends=[backend], session_ttl_sec=300)
    allowed_root = tmp_path / 'allowed-root'
    allowed_root.mkdir()
    default_workspace = allowed_root / 'default-workspace'
    app = make_app(logger, [str(allowed_root)])
    app.instance_config.data['box']['local']['default_workspace'] = str(default_workspace)
    service = BoxService(app, client=_InProcessBoxRuntimeClient(logger, runtime))
    service._shares_filesystem_with_box_override = True

    await service.initialize()

    assert default_workspace.is_dir()


@pytest.mark.asyncio
async def test_box_service_derives_workspace_and_allowed_root_from_host_root(tmp_path):
    logger = Mock()
    backend = FakeBackend(logger)
    runtime = BoxRuntime(logger=logger, backends=[backend], session_ttl_sec=300)
    shared_root = tmp_path / 'shared-box-root'
    app = make_app(logger, host_root=str(shared_root))
    service = BoxService(app, client=_InProcessBoxRuntimeClient(logger, runtime))
    service._shares_filesystem_with_box_override = True

    await service.initialize()

    assert service.host_root == os.path.realpath(shared_root)
    assert service.default_workspace == os.path.realpath(shared_root / 'default')
    assert service.allowed_mount_roots == [os.path.realpath(shared_root)]
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


class TestGetSystemGuidance:
    """``get_system_guidance`` must ALWAYS advertise the per-query outbox path
    when given a ``query_id`` — even with no inbound attachment — so files the
    agent generates (QR codes, charts, rendered docs) are actually delivered.

    The wrapper collects the outbox on every turn regardless of inbound files;
    before this, the agent was only told the outbox path inside the
    inbound-attachment note, so pure-generation turns produced files that were
    silently dropped.
    """

    def _service(self, logger=None):
        logger = logger or Mock()
        runtime = BoxRuntime(logger=logger, backends=[FakeBackend(logger)], session_ttl_sec=300)
        return BoxService(make_app(logger), client=_InProcessBoxRuntimeClient(logger, runtime))

    def test_guidance_includes_outbox_when_query_id_given(self):
        service = self._service()
        guidance = service.get_system_guidance(42)
        assert f'{service.OUTBOX_MOUNT_DIR}/42' in guidance
        assert 'delivered to the user automatically' in guidance

    def test_guidance_omits_outbox_without_query_id(self):
        service = self._service()
        guidance = service.get_system_guidance()
        assert service.OUTBOX_MOUNT_DIR not in guidance
        # core exec guidance is still present
        assert 'exec tool' in guidance

    def test_guidance_outbox_independent_of_inbound_attachments(self):
        # A bare query_id (the pure-generation case) still gets the outbox note.
        service = self._service()
        assert f'{service.OUTBOX_MOUNT_DIR}/0' in service.get_system_guidance(0)


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
    profile = BUILTIN_PROFILES['default']
    assert spec.network == BoxNetworkMode.OFF
    assert spec.image == profile.image
    assert spec.timeout_sec == profile.timeout_sec


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
    app.instance_config.data['box']['local']['default_workspace'] = str(host_dir)
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
    app.instance_config.data['box']['local']['default_workspace'] = str(host_dir)
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
    app.instance_config.data['box']['local']['default_workspace'] = str(host_dir)
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


class TestBoxDisabledByConfig:
    """``box.enabled = false`` must keep the BoxService usable as a status
    surface but skip every connection attempt and report unavailable."""

    @pytest.mark.asyncio
    async def test_initialize_skips_connector_when_disabled(self):
        logger = Mock()
        app = make_app(logger, enabled=False)
        client = Mock(spec=BoxRuntimeClient)
        client.initialize = AsyncMock()
        service = BoxService(app, client=client)

        await service.initialize()

        # The client must not be touched; we did not even open a connection.
        client.initialize.assert_not_awaited()
        assert service.enabled is False
        assert service.available is False
        # The reason is captured so the dashboard / UI can show it.
        assert 'disabled' in service._connector_error.lower()

    @pytest.mark.asyncio
    async def test_get_status_reports_disabled(self):
        logger = Mock()
        service = BoxService(make_app(logger, enabled=False), client=Mock(spec=BoxRuntimeClient))
        await service.initialize()

        status = await service.get_status()

        assert status['available'] is False
        assert status['enabled'] is False
        assert 'disabled' in status['connector_error'].lower()

    @pytest.mark.asyncio
    async def test_get_status_distinguishes_enabled_but_unavailable(self):
        logger = Mock()
        client = Mock(spec=BoxRuntimeClient)
        client.initialize = AsyncMock(side_effect=RuntimeError('docker daemon not running'))
        service = BoxService(make_app(logger, enabled=True), client=client)

        await service.initialize()

        status = await service.get_status()
        assert status['available'] is False
        assert status['enabled'] is True
        assert 'docker daemon' in status['connector_error']

    @pytest.mark.asyncio
    async def test_get_status_downgrades_available_when_backend_dead(self):
        """The connector can be healthy while the runtime reports no usable
        backend (operator selected nsjail but binary missing, Docker daemon
        crashed after handshake, ...). The top-level ``available`` must
        reflect the combined state so the dashboard / useBoxStatus hook /
        skill_service gate stay consistent with the native-tool gate."""
        logger = Mock()
        client = Mock(spec=BoxRuntimeClient)
        client.initialize = AsyncMock()
        client.get_status = AsyncMock(
            return_value={
                'backend': {'name': 'nsjail', 'available': False},
                'active_sessions': 0,
            }
        )
        service = BoxService(make_app(logger, enabled=True), client=client)
        await service.initialize()

        status = await service.get_status()
        assert status['available'] is False
        assert status['enabled'] is True
        # The detailed backend object is preserved for the dialog
        assert status['backend'] == {'name': 'nsjail', 'available': False}
        assert 'nsjail' in status['connector_error']

    @pytest.mark.asyncio
    async def test_get_status_keeps_available_true_when_backend_ok(self):
        logger = Mock()
        client = Mock(spec=BoxRuntimeClient)
        client.initialize = AsyncMock()
        client.get_status = AsyncMock(
            return_value={
                'backend': {'name': 'docker', 'available': True},
                'active_sessions': 2,
            }
        )
        service = BoxService(make_app(logger, enabled=True), client=client)
        await service.initialize()

        status = await service.get_status()
        assert status['available'] is True
        assert status['backend'] == {'name': 'docker', 'available': True}
        # No spurious connector_error overlay when everything is healthy
        assert 'connector_error' not in status or not status['connector_error']

    @pytest.mark.asyncio
    async def test_disconnect_callback_is_no_op_when_disabled(self):
        logger = Mock()
        service = BoxService(make_app(logger, enabled=False), client=Mock(spec=BoxRuntimeClient))

        # Should be safe to fire; must not flip reconnect state on a disabled
        # service. If it tried to schedule a reconnect, the test would hang.
        await service._on_runtime_disconnect(connector=Mock())

        assert service._reconnecting is False


class TestBuildSkillExtraMounts:
    """Robustness of skill mount construction against a stale skill cache.

    The three sandbox backends behave inconsistently when a skill's
    package_root no longer exists on disk (nsjail aborts the whole sandbox
    start, Docker silently auto-creates a root-owned empty directory, E2B
    silently skips). Mount construction must filter these out up front so
    the backend never sees a bad mount.
    """

    def _make_service(self, logger, skills, *, shares_filesystem=True):
        app = make_app(logger)
        app.skill_mgr = SimpleNamespace(skills=skills)
        client = Mock(spec=BoxRuntimeClient)
        service = BoxService(app, client=client)
        # Tests construct BoxService with an injected client (no connector), so
        # set the topology explicitly. Most cases exercise the shared-fs (local
        # stdio) path where local package_root validation applies.
        service._shares_filesystem_with_box_override = shares_filesystem
        return service

    def test_skips_skill_with_missing_package_root(self):
        logger = Mock()
        with tempfile.TemporaryDirectory() as live_dir:
            skills = {
                'alive': {'name': 'alive', 'package_root': live_dir},
                'ghost': {'name': 'ghost', 'package_root': '/nonexistent/path/should/never/exist'},
            }
            service = self._make_service(logger, skills)
            query = make_query()

            mounts = service.build_skill_extra_mounts(query)

            assert mounts == [
                {
                    'host_path': live_dir,
                    'mount_path': '/workspace/.skills/alive',
                    'mode': 'rw',
                }
            ]
            # Warning logged so operators can see what was dropped
            assert any(
                'ghost' in str(call.args[0]) and 'package_root missing' in str(call.args[0])
                for call in logger.warning.call_args_list
            )

    def test_trusts_box_paths_when_filesystem_not_shared(self):
        """In separated deployments (Docker Compose, k8s sidecar,
        --standalone-box, remote endpoint) the Box runtime owns its own
        filesystem. package_root values it reports are NOT resolvable on the
        LangBot side, so LangBot must trust them rather than dropping every
        skill via a local isdir() check."""
        logger = Mock()
        skills = {
            'a': {'name': 'a', 'package_root': '/box/skills/a'},
            'b': {'name': 'b', 'package_root': '/box/skills/b'},
        }
        service = self._make_service(logger, skills, shares_filesystem=False)

        mounts = service.build_skill_extra_mounts(make_query())

        assert mounts == [
            {'host_path': '/box/skills/a', 'mount_path': '/workspace/.skills/a', 'mode': 'rw'},
            {'host_path': '/box/skills/b', 'mount_path': '/workspace/.skills/b', 'mode': 'rw'},
        ]
        # No skill is dropped, so no "missing" warning should be logged.
        assert not any('package_root missing' in str(call.args[0]) for call in logger.warning.call_args_list)

    def test_skips_skill_with_empty_package_root(self):
        logger = Mock()
        skills = {
            'no_root': {'name': 'no_root', 'package_root': ''},
            'whitespace': {'name': 'whitespace', 'package_root': '   '},
        }
        service = self._make_service(logger, skills)

        assert service.build_skill_extra_mounts(make_query()) == []

    def test_empty_package_root_skipped_even_when_not_shared(self):
        """An empty package_root is always invalid regardless of topology."""
        logger = Mock()
        skills = {'no_root': {'name': 'no_root', 'package_root': ''}}
        service = self._make_service(logger, skills, shares_filesystem=False)

        assert service.build_skill_extra_mounts(make_query()) == []

    def test_returns_empty_when_no_skill_manager(self):
        logger = Mock()
        app = make_app(logger)
        # no skill_mgr attribute
        service = BoxService(app, client=Mock(spec=BoxRuntimeClient))

        assert service.build_skill_extra_mounts(make_query()) == []


# ── Attachment passthrough (inbound / outbound) ─────────────────────────────


class TestAttachmentHelpers:
    def test_sanitize_attachment_name_strips_traversal(self):
        assert BoxService._sanitize_attachment_name('../../etc/passwd', 'fb') == 'passwd'
        assert BoxService._sanitize_attachment_name('/a/b/c.png', 'fb') == 'c.png'
        assert BoxService._sanitize_attachment_name('a b c.txt', 'fb') == 'a_b_c.txt'
        assert BoxService._sanitize_attachment_name('', 'fallback.bin') == 'fallback.bin'
        assert BoxService._sanitize_attachment_name('...', 'fb.bin') == 'fb.bin'
        # weird unicode / shell chars dropped, but keeps a usable name
        out = BoxService._sanitize_attachment_name('rm -rf $(x).png', 'fb')
        assert '/' not in out and '$' not in out and out.endswith('.png')

    def test_classify_outbound_entries_by_extension(self):
        entries = [
            {'name': 'chart.png', 'b64': 'AAA'},
            {'name': 'clip.mp3', 'b64': 'BBB'},
            {'name': 'report.pdf', 'b64': 'CCC'},
            {'name': 'sub/dir/photo.JPG', 'b64': 'DDD'},
            {'name': 'noext', 'b64': 'EEE'},
            {'name': 'skip', 'b64': ''},  # dropped (no payload)
        ]
        out = BoxService._classify_outbound_entries(entries)
        by_name = {a['name']: a for a in out}
        assert by_name['chart.png']['type'] == 'Image'
        assert by_name['chart.png']['base64'].startswith('data:image/png;base64,')
        assert by_name['clip.mp3']['type'] == 'Voice'
        assert by_name['clip.mp3']['base64'].startswith('data:audio/mp3;base64,')
        assert by_name['report.pdf']['type'] == 'File'
        assert by_name['report.pdf']['base64'] == 'CCC'  # raw b64, no data: prefix
        # nested path collapses to basename, case-insensitive ext
        assert by_name['photo.JPG']['type'] == 'Image'
        assert by_name['noext']['type'] == 'File'
        assert 'skip' not in by_name

    @pytest.mark.asyncio
    async def test_component_to_bytes_from_data_uri(self):
        import base64

        raw = b'hello-bytes'
        data_uri = 'data:text/plain;base64,' + base64.b64encode(raw).decode()
        component = SimpleNamespace(base64=data_uri, url=None, path=None)
        result = await BoxService._component_to_bytes(component)
        assert result is not None
        data, mime = result
        assert data == raw
        assert mime == 'text/plain'

    @pytest.mark.asyncio
    async def test_component_to_bytes_returns_none_when_empty(self):
        component = SimpleNamespace(base64=None, url=None, path=None)
        assert await BoxService._component_to_bytes(component) is None


class TestInboundOutboundRoundTrip:
    def _service(self) -> BoxService:
        service = BoxService(make_app(Mock()), client=Mock(spec=BoxRuntimeClient))
        service._available = True
        return service

    @pytest.mark.asyncio
    async def test_materialize_inbound_writes_and_describes(self):
        import base64

        import langbot_plugin.api.entities.builtin.platform.message as platform_message

        service = self._service()

        img_bytes = b'\x89PNG\r\n\x1a\n fake png'
        img_b64 = 'data:image/png;base64,' + base64.b64encode(img_bytes).decode()

        query = make_query()
        query.message_chain = platform_message.MessageChain(
            [
                platform_message.Plain(text='please resize this'),
                platform_message.Image(base64=img_b64),
            ]
        )

        # Mock the sandbox write path: echo back the written paths.
        async def fake_execute_tool(parameters, q):
            assert '/workspace/inbox/' in parameters['command']
            return {
                'ok': True,
                'stdout': '["/workspace/inbox/42/image_1.png"]',
                'stderr': '',
            }

        service.execute_tool = AsyncMock(side_effect=fake_execute_tool)

        descriptors = await service.materialize_inbound_attachments(query)
        assert len(descriptors) == 1
        d = descriptors[0]
        assert d['type'] == 'Image'
        assert d['path'] == '/workspace/inbox/42/image_1.png'
        assert d['size'] == len(img_bytes)

    @pytest.mark.asyncio
    async def test_materialize_inbound_noop_without_attachments(self):
        import langbot_plugin.api.entities.builtin.platform.message as platform_message

        service = self._service()
        query = make_query()
        query.message_chain = platform_message.MessageChain([platform_message.Plain(text='just text')])
        service.execute_tool = AsyncMock()
        assert await service.materialize_inbound_attachments(query) == []
        service.execute_tool.assert_not_called()

    @pytest.mark.asyncio
    async def test_collect_outbound_reads_and_clears(self):
        service = self._service()
        query = make_query()

        calls = []

        async def fake_execute_tool(parameters, q):
            calls.append(parameters['command'])
            if 'os.walk' in parameters['command']:
                return {
                    'ok': True,
                    'stdout': '[{"name": "out.png", "b64": "QUJD"}]',
                    'stderr': '',
                }
            # the rm -rf cleanup call
            return {'ok': True, 'stdout': '', 'stderr': ''}

        service.execute_tool = AsyncMock(side_effect=fake_execute_tool)

        attachments = await service.collect_outbound_attachments(query)
        assert len(attachments) == 1
        assert attachments[0]['type'] == 'Image'
        assert attachments[0]['name'] == 'out.png'
        # cleanup (rm -rf) must have been issued after a successful collection
        assert any('rm -rf' in c for c in calls)

    @pytest.mark.asyncio
    async def test_collect_outbound_empty_still_clears(self):
        # An empty collection MUST still clear the per-query outbox, so a later
        # turn reusing the same query_id (the counter resets across restarts)
        # cannot inherit stale files left from a prior run.
        service = self._service()
        query = make_query()

        calls = []

        async def fake_execute_tool(parameters, q):
            calls.append(parameters['command'])
            if 'os.walk' in parameters['command']:
                return {'ok': True, 'stdout': '[]', 'stderr': ''}
            return {'ok': True, 'stdout': '', 'stderr': ''}

        service.execute_tool = AsyncMock(side_effect=fake_execute_tool)
        assert await service.collect_outbound_attachments(query) == []
        # cleanup (rm -rf) is issued unconditionally now
        assert any('rm -rf' in c for c in calls)

    @pytest.mark.asyncio
    async def test_passthrough_noop_when_unavailable(self):
        service = BoxService(make_app(Mock()), client=Mock(spec=BoxRuntimeClient))
        service._available = False
        query = make_query()
        assert await service.materialize_inbound_attachments(query) == []
        assert await service.collect_outbound_attachments(query) == []


class TestAttachmentHostPath:
    """Direct host-filesystem transfer path (bind-mounted workspace).

    When ``default_workspace`` is a real local dir, inbound/outbound bypass the
    exec channel entirely (no ARG_MAX / stdout-truncation limits) and read/write
    the bind-mounted host dir directly.
    """

    def _service_with_workspace(self, tmp_path):
        ws = str(tmp_path / 'box' / 'default')
        os.makedirs(ws, exist_ok=True)
        app = make_app(Mock(), allowed_mount_roots=[str(tmp_path)], host_root=str(tmp_path / 'box'))
        service = BoxService(app, client=Mock(spec=BoxRuntimeClient))
        service._available = True
        # Force the default_workspace to our tmp dir so _host_query_dir resolves.
        service.default_workspace = ws
        return service, ws

    @pytest.mark.asyncio
    async def test_inbound_writes_to_host_no_exec(self, tmp_path):
        import base64

        import langbot_plugin.api.entities.builtin.platform.message as platform_message

        service, ws = self._service_with_workspace(tmp_path)
        # Big payload that would blow ARG_MAX on the exec path:
        big = b'\x89PNG\r\n\x1a\n' + b'x' * (300 * 1024)
        b64 = 'data:image/png;base64,' + base64.b64encode(big).decode()
        query = make_query()
        query.message_chain = platform_message.MessageChain([platform_message.Image(base64=b64)])
        # execute_tool must NOT be called on the host path.
        service.execute_tool = AsyncMock(side_effect=AssertionError('exec must not be used on host path'))

        descriptors = await service.materialize_inbound_attachments(query)
        assert len(descriptors) == 1
        d = descriptors[0]
        assert d['type'] == 'Image'
        assert d['size'] == len(big)
        # File actually landed on the host workspace.
        host_file = os.path.join(ws, 'inbox', str(query.query_id), d['name'])
        assert os.path.isfile(host_file)
        assert open(host_file, 'rb').read() == big

    @pytest.mark.asyncio
    async def test_inbound_host_clears_stale_query_dir(self, tmp_path):
        import base64

        import langbot_plugin.api.entities.builtin.platform.message as platform_message

        service, ws = self._service_with_workspace(tmp_path)
        # Seed a stale file under the same query_id (simulates webchat id reuse).
        stale_dir = os.path.join(ws, 'inbox', '42')
        os.makedirs(stale_dir, exist_ok=True)
        open(os.path.join(stale_dir, 'image_1.png'), 'wb').write(b'STALE-OLD-IMAGE')

        new = b'\x89PNG\r\n\x1a\n NEW'
        b64 = 'data:image/png;base64,' + base64.b64encode(new).decode()
        query = make_query(query_id=42)
        query.message_chain = platform_message.MessageChain([platform_message.Image(base64=b64)])
        service.execute_tool = AsyncMock()
        descriptors = await service.materialize_inbound_attachments(query)
        # The new write recreated the dir; the stale file is gone, new bytes present.
        host_file = os.path.join(stale_dir, descriptors[0]['name'])
        assert open(host_file, 'rb').read() == new
        # No leftover content from the stale image.
        assert b'STALE-OLD-IMAGE' not in open(host_file, 'rb').read()

    @pytest.mark.asyncio
    async def test_outbound_reads_host_and_clears(self, tmp_path):
        service, ws = self._service_with_workspace(tmp_path)
        query = make_query()
        outbox = os.path.join(ws, 'outbox', str(query.query_id))
        os.makedirs(outbox, exist_ok=True)
        # A large file that would be truncated on the exec/stdout path:
        big_png = b'\x89PNG\r\n\x1a\n' + b'y' * (400 * 1024)
        open(os.path.join(outbox, 'result.png'), 'wb').write(big_png)
        open(os.path.join(outbox, 'notes.txt'), 'wb').write(b'hello')

        service.execute_tool = AsyncMock(side_effect=AssertionError('exec must not be used on host path'))
        attachments = await service.collect_outbound_attachments(query)
        by_name = {a['name']: a for a in attachments}
        assert by_name['result.png']['type'] == 'Image'
        assert by_name['notes.txt']['type'] == 'File'
        # Full image survived (no truncation).
        import base64

        raw = base64.b64decode(by_name['result.png']['base64'].split(',', 1)[-1])
        assert raw == big_png
        # Outbox cleared after collection.
        assert os.listdir(outbox) == []

    @pytest.mark.asyncio
    async def test_outbound_empty_clears_stale_host_dir(self, tmp_path):
        # Reusing a query_id (counter resets on restart) must not re-send files
        # a previous run left in the outbox: an empty collection still clears it.
        service, ws = self._service_with_workspace(tmp_path)
        query = make_query()
        outbox = os.path.join(ws, 'outbox', str(query.query_id))
        os.makedirs(outbox, exist_ok=True)
        # Stale file from a prior turn; the agent produced nothing this turn —
        # but _read_outbox_host would still pick it up, so collection must drop
        # it and then wipe the dir. Simulate "nothing produced this turn" by
        # treating any present file as stale and asserting it is not re-sent
        # across a second, genuinely-empty collection.
        open(os.path.join(outbox, 'stale.png'), 'wb').write(b'\x89PNG\r\n\x1a\n old')
        service.execute_tool = AsyncMock(side_effect=AssertionError('exec must not be used on host path'))

        # First collection drains + clears the dir.
        first = await service.collect_outbound_attachments(query)
        assert {a['name'] for a in first} == {'stale.png'}
        assert os.listdir(outbox) == []

        # Second collection (no new files) returns nothing and leaves a clean dir.
        second = await service.collect_outbound_attachments(query)
        assert second == []
        assert os.listdir(outbox) == []

    @pytest.mark.asyncio
    async def test_purge_attachment_dirs_wipes_host_owned_leftovers_on_init(self, tmp_path):
        # Leftover inbox/outbox dirs from a previous process (same reset
        # query_id counter) must be removed at startup. Host-owned files are
        # cleared without any sandbox exec.
        service, ws = self._service_with_workspace(tmp_path)
        for sub in ('inbox', 'outbox'):
            d = os.path.join(ws, sub, '0')
            os.makedirs(d, exist_ok=True)
            open(os.path.join(d, 'leftover.bin'), 'wb').write(b'from a previous process')
        service.execute_tool = AsyncMock(side_effect=AssertionError('exec must not be used for host-owned files'))

        await service._purge_attachment_dirs()

        assert not os.path.exists(os.path.join(ws, 'inbox'))
        assert not os.path.exists(os.path.join(ws, 'outbox'))
        # The workspace root itself survives.
        assert os.path.isdir(ws)

    @pytest.mark.asyncio
    async def test_purge_attachment_dirs_falls_back_to_exec_for_root_owned(self, tmp_path, monkeypatch):
        # When the host delete cannot remove a dir (root-owned container output),
        # purge must fall back to deleting from inside the sandbox via exec.
        service, ws = self._service_with_workspace(tmp_path)
        outbox = os.path.join(ws, 'outbox')
        os.makedirs(os.path.join(outbox, '0'), exist_ok=True)

        # Simulate a host delete that cannot remove the root-owned outbox.
        import shutil as _shutil

        real_rmtree = _shutil.rmtree

        def fake_rmtree(path, *a, **k):
            if os.path.abspath(path) == os.path.abspath(outbox):
                return  # "permission denied" — silently leaves the dir
            return real_rmtree(path, *a, **k)

        monkeypatch.setattr(_shutil, 'rmtree', fake_rmtree)

        executed = {}
        spec_obj = object()
        service.build_spec = Mock(return_value=spec_obj)
        service.client.execute = AsyncMock(side_effect=lambda s: executed.setdefault('spec', s))

        await service._purge_attachment_dirs()

        # build_spec was asked to rm the surviving outbox via exec.
        cmd = service.build_spec.call_args.args[0]['cmd']
        assert 'rm -rf' in cmd and '/workspace/outbox' in cmd
        assert '/workspace/inbox' not in cmd  # inbox was host-deletable
        service.client.execute.assert_awaited_once_with(spec_obj)

    @pytest.mark.asyncio
    async def test_purge_attachment_dirs_noop_without_workspace(self):
        # No bind-mounted workspace (E2B / remote): purge is a safe no-op.
        service = BoxService(make_app(Mock()), client=Mock(spec=BoxRuntimeClient))
        service.default_workspace = None
        # Must not raise.
        await service._purge_attachment_dirs()
