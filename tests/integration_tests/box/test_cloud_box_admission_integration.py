from __future__ import annotations

import asyncio
import datetime as dt
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

import langbot_plugin.api.entities.builtin.pipeline.query as pipeline_query
from langbot_plugin.box.backend import BaseSandboxBackend
from langbot_plugin.box.client import ActionRPCBoxClient
from langbot_plugin.box.errors import BoxAdmissionError
from langbot_plugin.box.models import (
    BoxExecutionResult,
    BoxExecutionStatus,
    BoxNetworkMode,
    BoxSessionInfo,
    BoxSpec,
)
from langbot_plugin.box.runtime import BoxRuntime
from langbot_plugin.box.server import BoxServerHandler
from langbot_plugin.runtime.io.handler import Handler

from langbot.pkg.api.http.context import ExecutionContext
from langbot.pkg.box.service import BoxService
from langbot.pkg.cloud.entitlements import (
    EntitlementResolver,
    EntitlementSnapshot,
    EntitlementUnavailableError,
)


pytestmark = pytest.mark.integration
_UTC = dt.timezone.utc


class _AdmissionBackend(BaseSandboxBackend):
    name = 'nsjail'

    def __init__(self, logger):
        super().__init__(logger)
        self.started_specs: list[BoxSpec] = []
        self.stopped_sessions: list[str] = []

    async def is_available(self) -> bool:
        return True

    async def get_readiness(self, *, workspace_path=None, strict=False) -> dict:
        return {
            'available': True,
            'cgroup_v2': True,
            'namespace_isolation': True,
            'mount_isolation': True,
            'network_isolation': True,
            'hard_workspace_quota': True,
            'hard_skill_storage_quota': True,
            'bounded_ephemeral_storage': True,
            'inode_quota': True,
        }

    async def start_session(self, spec: BoxSpec) -> BoxSessionInfo:
        self.started_specs.append(spec)
        now = dt.datetime.now(_UTC)
        return BoxSessionInfo(
            session_id=spec.session_id,
            backend_name=self.name,
            backend_session_id=f'jail-{len(self.started_specs)}',
            image=spec.image,
            network=spec.network,
            host_path=spec.host_path,
            host_path_mode=spec.host_path_mode,
            mount_path=spec.mount_path,
            persistent=spec.persistent,
            cpus=spec.cpus,
            memory_mb=spec.memory_mb,
            pids_limit=spec.pids_limit,
            read_only_rootfs=spec.read_only_rootfs,
            workspace_quota_mb=spec.workspace_quota_mb,
            created_at=now,
            last_used_at=now,
        )

    async def exec(self, session: BoxSessionInfo, spec: BoxSpec) -> BoxExecutionResult:
        await asyncio.sleep(0)
        return BoxExecutionResult(
            session_id=session.session_id,
            backend_name=self.name,
            status=BoxExecutionStatus.COMPLETED,
            exit_code=0,
            stdout=spec.cmd,
            stderr='',
            duration_ms=1,
        )

    async def stop_session(self, session: BoxSessionInfo):
        self.stopped_sessions.append(session.session_id)


class _QueueConnection:
    def __init__(self, rx: asyncio.Queue[str], tx: asyncio.Queue[str]):
        self._rx = rx
        self._tx = tx

    async def send(self, message: str) -> None:
        await self._tx.put(message)

    async def receive(self) -> str:
        return await self._rx.get()

    async def close(self) -> None:
        return None


async def _rpc_client(runtime: BoxRuntime):
    client_to_server: asyncio.Queue[str] = asyncio.Queue()
    server_to_client: asyncio.Queue[str] = asyncio.Queue()
    client_connection = _QueueConnection(server_to_client, client_to_server)
    server_connection = _QueueConnection(client_to_server, server_to_client)
    server_handler = BoxServerHandler(
        server_connection,
        runtime,
        host_control_authenticated=True,
        trusted_instance_uuid='instance-a',
    )
    server_task = asyncio.create_task(server_handler.run())
    client_handler = Handler(client_connection)
    client_task = asyncio.create_task(client_handler.run())
    client = ActionRPCBoxClient(logger=Mock())
    client.set_handler(client_handler)
    return client, server_task, client_task


class _Entitlements:
    def __init__(self):
        self.snapshots: dict[str, EntitlementSnapshot] = {}

    async def get_workspace_entitlement(self, workspace_uuid: str) -> EntitlementSnapshot:
        return self.snapshots[workspace_uuid]


def _snapshot(workspace_uuid: str, *, revision: int = 1, managed: bool = True) -> EntitlementSnapshot:
    return EntitlementSnapshot(
        instance_uuid='instance-a',
        workspace_uuid=workspace_uuid,
        entitlement_revision=revision,
        status='active',
        not_before=1,
        expires_at=4_000_000_000,
        features={'managed_sandbox': managed},
        limits={'managed_sandbox_sessions': 1 if managed else 0},
    )


def _context(workspace_uuid: str, *, revision: int = 1) -> ExecutionContext:
    return ExecutionContext(
        instance_uuid='instance-a',
        workspace_uuid=workspace_uuid,
        placement_generation=1,
        entitlement_revision=revision,
    )


def _query(context: ExecutionContext, query_id: int):
    query = pipeline_query.Query.model_construct(
        query_id=query_id,
        bot_uuid='bot-a',
        pipeline_uuid='pipeline-a',
        launcher_type='person',
        launcher_id=f'user-{query_id}',
        variables={},
    )
    object.__setattr__(query, 'instance_uuid', context.instance_uuid)
    object.__setattr__(query, 'workspace_uuid', context.workspace_uuid)
    object.__setattr__(query, 'placement_generation', context.placement_generation)
    object.__setattr__(query, '_execution_context', context)
    return query


async def _stack(tmp_path):
    shared_root = tmp_path / 'shared-box'
    workspace_root = shared_root / 'workspaces'
    workspace_root.mkdir(parents=True)
    box_config = {
        'enabled': True,
        'backend': 'nsjail',
        'runtime': {'endpoint': 'ws://langbot-box:5410'},
        'local': {
            'profile': 'default',
            'host_root': str(shared_root),
            'default_workspace': str(workspace_root),
            'allowed_mount_roots': [str(shared_root)],
        },
        'admission': {
            'required': True,
            'logical_session_id': 'global',
            'required_backend': 'nsjail',
            'max_sessions': 1,
            'max_managed_processes': 0,
            'max_grant_ttl_sec': 300,
            'max_timeout_sec': 60,
            'cpus': 0.5,
            'memory_mb': 256,
            'pids_limit': 64,
            'read_only_rootfs': True,
            'workspace_quota_mb': 32,
            'readiness_cache_sec': 0,
        },
    }
    logger = Mock()
    backend = _AdmissionBackend(logger)
    runtime = BoxRuntime(logger, backends=[backend])
    runtime.init(box_config)
    await runtime.initialize()
    client, server_task, client_task = await _rpc_client(runtime)

    entitlements = _Entitlements()
    workspace_service = SimpleNamespace(
        instance_uuid='instance-a',
        get_execution_binding=AsyncMock(
            side_effect=lambda workspace_uuid, expected_generation: SimpleNamespace(
                instance_uuid='instance-a',
                workspace_uuid=workspace_uuid,
                placement_generation=expected_generation,
            )
        ),
    )
    app = SimpleNamespace(
        logger=logger,
        deployment=SimpleNamespace(multi_workspace_enabled=True),
        entitlement_resolver=EntitlementResolver('instance-a', entitlements),
        workspace_service=workspace_service,
        instance_config=SimpleNamespace(data={'box': box_config, 'system': {'limitation': {}}}),
    )
    service = BoxService(app, client=client)
    await service.initialize()
    return service, runtime, backend, entitlements, server_task, client_task


@pytest.mark.asyncio
async def test_concurrent_first_use_creates_one_persistent_global_session(tmp_path):
    service, runtime, backend, entitlements, server_task, client_task = await _stack(tmp_path)
    context = _context('workspace-a')
    entitlements.snapshots[context.workspace_uuid] = _snapshot(context.workspace_uuid)
    try:
        first, second = await asyncio.gather(
            service.execute_tool({'command': 'echo first'}, _query(context, 1)),
            service.execute_tool({'command': 'echo second'}, _query(context, 2)),
        )

        assert first['session_id'] == 'global'
        assert second['session_id'] == 'global'
        assert len(backend.started_specs) == 1
        spec = backend.started_specs[0]
        assert spec.persistent is True
        assert spec.network == BoxNetworkMode.OFF
        assert spec.cpus == 0.5
        assert spec.memory_mb == 256
        assert spec.pids_limit == 64
        assert spec.workspace_quota_mb == 32
    finally:
        server_task.cancel()
        client_task.cancel()
        await runtime.shutdown()


@pytest.mark.asyncio
async def test_entitlement_loss_revokes_and_closes_existing_global_session(tmp_path):
    service, runtime, backend, entitlements, server_task, client_task = await _stack(tmp_path)
    context = _context('workspace-a')
    entitlements.snapshots[context.workspace_uuid] = _snapshot(context.workspace_uuid, revision=1)
    try:
        await service.execute_tool({'command': 'true'}, _query(context, 1))
        assert len(runtime.get_sessions()) == 1

        entitlements.snapshots[context.workspace_uuid] = _snapshot(
            context.workspace_uuid,
            revision=2,
            managed=False,
        )
        with pytest.raises(EntitlementUnavailableError):
            await service.execute_tool({'command': 'true'}, _query(context, 2))

        assert runtime.get_sessions() == []
        assert len(backend.stopped_sessions) == 1
    finally:
        server_task.cancel()
        client_task.cancel()
        await runtime.shutdown()


@pytest.mark.asyncio
async def test_two_workspaces_get_isolated_physical_sessions_and_paths(tmp_path):
    service, runtime, backend, entitlements, server_task, client_task = await _stack(tmp_path)
    first = _context('workspace-a')
    second = _context('workspace-b')
    entitlements.snapshots[first.workspace_uuid] = _snapshot(first.workspace_uuid)
    entitlements.snapshots[second.workspace_uuid] = _snapshot(second.workspace_uuid)
    try:
        result_a = await service.execute_tool({'command': 'tenant-a'}, _query(first, 1))
        result_b = await service.execute_tool({'command': 'tenant-b'}, _query(second, 2))

        assert result_a['session_id'] == result_b['session_id'] == 'global'
        assert len(backend.started_specs) == 2
        assert backend.started_specs[0].session_id != backend.started_specs[1].session_id
        assert backend.started_specs[0].host_path != backend.started_specs[1].host_path
        assert len(runtime.get_sessions()) == 2
    finally:
        server_task.cancel()
        client_task.cancel()
        await runtime.shutdown()


@pytest.mark.asyncio
async def test_cloud_skills_reject_host_paths_and_require_managed_entitlement(tmp_path):
    service, runtime, backend, entitlements, server_task, client_task = await _stack(tmp_path)
    first = _context('workspace-a')
    second = _context('workspace-b')
    ineligible = _context('workspace-free')
    entitlements.snapshots[first.workspace_uuid] = _snapshot(first.workspace_uuid)
    entitlements.snapshots[second.workspace_uuid] = _snapshot(second.workspace_uuid)
    entitlements.snapshots[ineligible.workspace_uuid] = _snapshot(
        ineligible.workspace_uuid,
        managed=False,
    )
    try:
        private = await service.create_skill(
            second,
            {
                'name': 'private',
                'instructions': 'workspace-b secret',
            },
        )
        own_skill = await service.create_skill(
            first,
            {
                'name': 'runner',
                'instructions': 'Run scripts/main.py',
            },
        )
        await service.write_skill_file(first, 'runner', 'scripts/main.py', "print('ok')")
        await service.write_skill_file(first, 'runner', 'requirements.txt', 'requests==2.32.0\n')
        refreshed_skill = await service.get_skill(first, 'runner')
        assert refreshed_skill is not None
        assert refreshed_skill['python_project'] is True
        await service.execute_tool(
            {
                'command': 'python /workspace/.skills/runner/scripts/main.py',
                'workdir': '/workspace/.skills/runner',
            },
            _query(first, 91),
            skill_name='runner',
        )

        mounted_spec = backend.started_specs[-1]
        assert len(mounted_spec.extra_mounts) == 1
        assert mounted_spec.extra_mounts[0].host_path == own_skill['package_root']
        assert mounted_spec.extra_mounts[0].mount_path == '/workspace/.skills/runner'
        assert mounted_spec.extra_mounts[0].mode.value == 'ro'

        with pytest.raises(BoxAdmissionError, match='Scanning arbitrary host'):
            await service.scan_skill_directory(first, private['package_root'])
        with pytest.raises(BoxAdmissionError, match='package_root is runtime-owned'):
            await service.create_skill(
                first,
                {
                    'name': 'stolen',
                    'package_root': private['package_root'],
                },
            )

        assert await service.get_skill(first, 'private') is None
        with pytest.raises(EntitlementUnavailableError):
            await service.list_skills(ineligible)
    finally:
        server_task.cancel()
        client_task.cancel()
        await runtime.shutdown()


@pytest.mark.asyncio
async def test_forged_plan_network_session_and_managed_process_never_reach_runtime(tmp_path):
    service, runtime, backend, entitlements, server_task, client_task = await _stack(tmp_path)
    context = _context('workspace-a')
    entitlements.snapshots[context.workspace_uuid] = _snapshot(context.workspace_uuid)
    query = _query(context, 1)
    try:
        with pytest.raises(BoxAdmissionError, match='host-controlled'):
            await service.execute_spec_payload(
                {'cmd': 'true', 'session_id': 'global', 'plan': 'pro'},
                query,
            )
        with pytest.raises(BoxAdmissionError, match='network access is disabled'):
            await service.execute_spec_payload(
                {'cmd': 'true', 'session_id': 'global', 'network': 'on'},
                query,
            )
        with pytest.raises(BoxAdmissionError, match='session_id is runtime-owned'):
            await service.execute_spec_payload(
                {'cmd': 'true', 'session_id': 'attacker'},
                query,
            )
        with pytest.raises(BoxAdmissionError, match='Managed processes are disabled'):
            await service.start_managed_process(
                context,
                'global',
                {'command': 'sleep', 'args': ['60']},
            )

        assert backend.started_specs == []
        assert runtime.get_sessions() == []
    finally:
        server_task.cancel()
        client_task.cancel()
        await runtime.shutdown()
