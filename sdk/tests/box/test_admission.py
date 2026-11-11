"""Grant-enforced multi-Workspace admission tests for the Box Runtime."""

from __future__ import annotations

import asyncio
import datetime as dt
import logging
from unittest import mock

import pytest

from langbot_plugin.box.backend import BaseSandboxBackend
from langbot_plugin.box.errors import (
    BoxAdmissionError,
    BoxReadinessError,
)
from langbot_plugin.box.models import (
    BoxExecutionResult,
    BoxExecutionStatus,
    BoxHostMountMode,
    BoxManagedProcessSpec,
    BoxMountSpec,
    BoxNetworkMode,
    BoxSessionInfo,
    BoxSpec,
    SandboxAdmissionGrant,
    SandboxAdmissionRevocation,
)
from langbot_plugin.box.runtime import MAX_ADMITTED_READ_ONLY_MOUNTS, BoxRuntime
from langbot_plugin.box.tenancy import box_namespace, namespace_session_id
from langbot_plugin.entities.io.context import ActionContext


_UTC = dt.timezone.utc


class AdmissionBackend(BaseSandboxBackend):
    name = "nsjail"

    def __init__(self, logger: logging.Logger):
        super().__init__(logger)
        self.started_specs: list[BoxSpec] = []
        self.stopped_sessions: list[str] = []
        self.exec_calls = 0
        self.readiness = {
            "available": True,
            "cgroup_v2": True,
            "namespace_isolation": True,
            "mount_isolation": True,
            "network_isolation": True,
            "hard_workspace_quota": True,
            "hard_read_only_mount_quota": True,
            "bounded_ephemeral_storage": True,
            "inode_quota": True,
        }

    async def is_available(self) -> bool:
        return True

    async def get_readiness(self, *, workspace_path=None, strict=False) -> dict:
        return dict(self.readiness)

    async def start_session(self, spec: BoxSpec) -> BoxSessionInfo:
        self.started_specs.append(spec)
        now = dt.datetime.now(_UTC)
        return BoxSessionInfo(
            session_id=spec.session_id,
            backend_name=self.name,
            backend_session_id=f"sandbox-{len(self.started_specs)}",
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
        self.exec_calls += 1
        await asyncio.sleep(0)
        return BoxExecutionResult(
            session_id=session.session_id,
            backend_name=self.name,
            status=BoxExecutionStatus.COMPLETED,
            exit_code=0,
            stdout="ok",
            stderr="",
            duration_ms=1,
        )

    async def stop_session(self, session: BoxSessionInfo):
        self.stopped_sessions.append(session.session_id)


def _context(*, workspace: str = "workspace-a", generation: int = 1) -> ActionContext:
    return ActionContext(
        instance_uuid="instance-a",
        workspace_uuid=workspace,
        placement_generation=generation,
    )


def _grant(
    context: ActionContext,
    *,
    revision: int = 1,
    max_sessions: int = 1,
    max_managed_processes: int = 0,
    expires_in: float = 60,
) -> SandboxAdmissionGrant:
    return SandboxAdmissionGrant(
        instance_uuid=context.instance_uuid,
        workspace_uuid=context.workspace_uuid,
        execution_generation=context.placement_generation,
        entitlement_revision=revision,
        expires_at=dt.datetime.now(_UTC) + dt.timedelta(seconds=expires_in),
        max_sessions=max_sessions,
        max_managed_processes=max_managed_processes,
    )


def _runtime(
    tmp_path,
    *,
    readiness_cache_sec: int = 0,
    unsafe_soft_storage_limits: bool = False,
):
    logger = logging.getLogger("test.box.admission")
    backend = AdmissionBackend(logger)
    unsafe_value = "true" if unsafe_soft_storage_limits else ""
    with mock.patch(
        "os.getenv",
        side_effect=lambda name, default="": (
            unsafe_value
            if name == "LANGBOT_BOX_ALLOW_UNSAFE_SOFT_STORAGE_LIMITS"
            else default
        ),
    ):
        runtime = BoxRuntime(logger, backends=[backend])
    runtime.init(
        {
            "backend": "nsjail",
            "local": {
                "host_root": str(tmp_path / "box"),
                "allowed_mount_roots": [str(tmp_path / "box")],
            },
            "admission": {
                "required": True,
                "readiness_cache_sec": readiness_cache_sec,
            },
        }
    )
    return runtime, backend


def test_managed_read_only_mount_limit_is_256(tmp_path):
    runtime, _ = _runtime(tmp_path)
    assert MAX_ADMITTED_READ_ONLY_MOUNTS == 256
    with pytest.raises(BoxAdmissionError, match="at most 256"):
        runtime._normalize_admitted_extra_mounts(
            [mock.MagicMock() for _ in range(MAX_ADMITTED_READ_ONLY_MOUNTS + 1)]
        )


@pytest.mark.anyio
async def test_missing_and_zero_session_grants_fail_closed(tmp_path):
    runtime, backend = _runtime(tmp_path)
    context = _context()

    with pytest.raises(BoxAdmissionError, match="grant is missing"):
        await runtime.execute(BoxSpec(session_id="anything", cmd="true"), context)

    await runtime.upsert_sandbox_admission_grant(_grant(context, max_sessions=0))
    with pytest.raises(BoxAdmissionError, match="does not permit sessions"):
        await runtime.execute(BoxSpec(session_id="anything", cmd="true"), context)
    assert backend.started_specs == []


@pytest.mark.anyio
async def test_expired_grant_is_rejected_and_cleans_persistent_session(tmp_path):
    runtime, backend = _runtime(tmp_path)
    context = _context()
    await runtime.upsert_sandbox_admission_grant(_grant(context, expires_in=0.03))
    await runtime.execute(BoxSpec(session_id="first", cmd="true"), context)

    await asyncio.sleep(0.04)
    with pytest.raises(BoxAdmissionError, match="grant is missing"):
        await runtime.execute(BoxSpec(session_id="second", cmd="true"), context)
    await asyncio.sleep(0)

    assert runtime.get_sessions() == []
    assert len(backend.stopped_sessions) == 1


def test_admission_expiry_uses_bounded_heap_without_global_grant_scan(tmp_path):
    class NoGlobalItemsScan(dict):
        def items(self):
            raise AssertionError("admission reap scanned every Workspace grant")

        def values(self):
            raise AssertionError("admission reap scanned every Workspace grant")

    runtime, _ = _runtime(tmp_path)
    now = dt.datetime.now(_UTC)
    last_grant = None
    for index in range(1_000):
        context = _context(workspace=f"workspace-{index}")
        last_grant = _grant(context, expires_in=3_600)
        runtime._admission_grants[last_grant.workspace_key] = last_grant
        runtime._index_admission_expiry_locked(last_grant)

    expired_context = _context(workspace="expired-workspace")
    expired = _grant(expired_context, expires_in=-1)
    runtime._admission_grants[expired.workspace_key] = expired
    runtime._index_admission_expiry_locked(expired)
    runtime._admission_grants = NoGlobalItemsScan(runtime._admission_grants)

    assert runtime._reap_expired_admissions_locked(now) == []
    assert expired.workspace_key not in runtime._admission_grants
    assert len(runtime._admission_grants) == 1_000

    assert last_grant is not None
    runtime._admission_grants = {last_grant.workspace_key: last_grant}
    runtime._admission_expiry_heap = []
    for _ in range(3_000):
        runtime._index_admission_expiry_locked(last_grant)
    assert len(runtime._admission_expiry_heap) <= 1_026


@pytest.mark.anyio
async def test_concurrent_requests_create_one_global_persistent_offline_session(
    tmp_path,
):
    runtime, backend = _runtime(tmp_path)
    context = _context()
    await runtime.upsert_sandbox_admission_grant(_grant(context))

    results = await asyncio.gather(
        *(
            runtime.execute(
                BoxSpec(session_id=f"caller-{index}", cmd=f"echo {index}"),
                context,
            )
            for index in range(20)
        )
    )

    expected_session_id = namespace_session_id(context, "global")
    assert {result.session_id for result in results} == {expected_session_id}
    assert len(backend.started_specs) == 1
    effective_spec = backend.started_specs[0]
    assert effective_spec.session_id == expected_session_id
    assert effective_spec.persistent is True
    assert effective_spec.network is BoxNetworkMode.OFF
    assert effective_spec.extra_mounts == []
    assert effective_spec.host_path == str(
        tmp_path / "box" / "default" / "tenants" / box_namespace(context)
    )
    assert runtime.get_sessions()[0]["persistent"] is True


@pytest.mark.anyio
async def test_same_global_id_is_isolated_between_workspaces(tmp_path):
    runtime, backend = _runtime(tmp_path)
    first = _context(workspace="workspace-a")
    second = _context(workspace="workspace-b")
    await runtime.upsert_sandbox_admission_grant(_grant(first))
    await runtime.upsert_sandbox_admission_grant(_grant(second))

    first_result, second_result = await asyncio.gather(
        runtime.execute(BoxSpec(session_id="global", cmd="true"), first),
        runtime.execute(BoxSpec(session_id="global", cmd="true"), second),
    )

    assert first_result.session_id != second_result.session_id
    assert len(backend.started_specs) == 2
    assert backend.started_specs[0].host_path != backend.started_specs[1].host_path
    assert {spec.network for spec in backend.started_specs} == {BoxNetworkMode.OFF}


@pytest.mark.anyio
async def test_network_and_arbitrary_host_mount_requests_fail_closed(tmp_path):
    runtime, backend = _runtime(tmp_path)
    context = _context()
    await runtime.upsert_sandbox_admission_grant(_grant(context))

    with pytest.raises(BoxAdmissionError, match="network access is disabled"):
        await runtime.execute(
            BoxSpec(session_id="global", cmd="true", network=BoxNetworkMode.ON),
            context,
        )
    with pytest.raises(BoxAdmissionError, match="host_path is runtime-owned"):
        await runtime.execute(
            BoxSpec(session_id="global", cmd="true", host_path="/tmp/escape"),
            context,
        )
    assert backend.started_specs == []


@pytest.mark.anyio
async def test_managed_generic_read_only_mount_is_accepted(tmp_path):
    runtime, backend = _runtime(tmp_path)
    assert not hasattr(runtime, "skill_store")
    context = _context()
    package_root = tmp_path / "box" / "artifacts" / "demo"
    package_root.mkdir(parents=True)
    await runtime.upsert_sandbox_admission_grant(_grant(context))

    await runtime.execute(
        BoxSpec(
            session_id="caller-owned",
            cmd="python /workspace/.skills/demo/scripts/demo.py",
            extra_mounts=[
                BoxMountSpec(
                    host_path=str(package_root),
                    mount_path="/workspace/.skills/demo",
                    mode=BoxHostMountMode.READ_ONLY,
                )
            ],
        ),
        context,
    )

    effective = backend.started_specs[0]
    assert len(effective.extra_mounts) == 1
    mount = effective.extra_mounts[0]
    assert mount.host_path == str(package_root)
    assert mount.mount_path == "/workspace/.skills/demo"
    assert mount.mode.value == "ro"


@pytest.mark.anyio
async def test_managed_generic_mount_rejects_writable_or_disallowed_sources(tmp_path):
    runtime, backend = _runtime(tmp_path)
    context = _context(workspace="workspace-a")
    allowed_source = tmp_path / "box" / "artifacts" / "allowed"
    allowed_source.mkdir(parents=True)
    outside_source = tmp_path / "outside"
    outside_source.mkdir()
    await runtime.upsert_sandbox_admission_grant(_grant(context))

    with pytest.raises(BoxAdmissionError, match="must be read-only"):
        await runtime.execute(
            BoxSpec(
                session_id="global",
                cmd="true",
                extra_mounts=[
                    BoxMountSpec(
                        host_path=str(allowed_source),
                        mount_path="/workspace/artifact",
                        mode=BoxHostMountMode.READ_WRITE,
                    )
                ],
            ),
            context,
        )
    with pytest.raises(BoxAdmissionError, match="outside allowed_mount_roots"):
        await runtime.execute(
            BoxSpec(
                session_id="global",
                cmd="true",
                extra_mounts=[
                    BoxMountSpec(
                        host_path=str(outside_source),
                        mount_path="/workspace/artifact",
                        mode=BoxHostMountMode.READ_ONLY,
                    )
                ],
            ),
            context,
        )

    assert backend.started_specs == []


@pytest.mark.anyio
async def test_managed_process_is_denied_before_backend_process_start(tmp_path):
    runtime, _ = _runtime(tmp_path)
    context = _context()
    await runtime.upsert_sandbox_admission_grant(_grant(context))
    await runtime.create_session(BoxSpec(session_id="ignored", cmd=""), context)

    with pytest.raises(BoxAdmissionError, match="does not permit managed processes"):
        await runtime.start_managed_process(
            namespace_session_id(context, "global"),
            BoxManagedProcessSpec(command="python"),
            context,
        )


@pytest.mark.anyio
async def test_generation_advance_retires_old_session_and_rejects_old_context(
    tmp_path,
):
    runtime, backend = _runtime(tmp_path)
    old_context = _context(generation=1)
    new_context = _context(generation=2)
    await runtime.upsert_sandbox_admission_grant(_grant(old_context, revision=1))
    await runtime.execute(BoxSpec(session_id="old", cmd="true"), old_context)

    await runtime.upsert_sandbox_admission_grant(_grant(new_context, revision=1))
    with pytest.raises(BoxAdmissionError, match="another execution generation"):
        await runtime.execute(BoxSpec(session_id="old", cmd="true"), old_context)
    await runtime.execute(BoxSpec(session_id="new", cmd="true"), new_context)

    assert len(backend.started_specs) == 2
    assert backend.stopped_sessions == [namespace_session_id(old_context, "global")]
    assert runtime.get_sessions()[0]["session_id"] == namespace_session_id(
        new_context, "global"
    )


@pytest.mark.anyio
async def test_revocation_closes_session_and_tombstones_revision(tmp_path):
    runtime, backend = _runtime(tmp_path)
    context = _context()
    grant = _grant(context, revision=3)
    await runtime.upsert_sandbox_admission_grant(grant)
    await runtime.execute(BoxSpec(session_id="global", cmd="true"), context)

    await runtime.revoke_sandbox_admission_grant(
        SandboxAdmissionRevocation(
            instance_uuid=context.instance_uuid,
            workspace_uuid=context.workspace_uuid,
            entitlement_revision=3,
        )
    )

    assert runtime.get_sessions() == []
    assert backend.stopped_sessions == [namespace_session_id(context, "global")]
    with pytest.raises(BoxAdmissionError, match="revision was revoked"):
        await runtime.upsert_sandbox_admission_grant(grant)


@pytest.mark.anyio
async def test_same_entitlement_revision_cannot_change_limits(tmp_path):
    runtime, _ = _runtime(tmp_path)
    context = _context()
    await runtime.upsert_sandbox_admission_grant(
        _grant(context, revision=7, max_sessions=1)
    )
    with pytest.raises(BoxAdmissionError, match="without a new entitlement revision"):
        await runtime.upsert_sandbox_admission_grant(
            _grant(context, revision=7, max_sessions=0)
        )


@pytest.mark.anyio
async def test_admission_fence_records_are_bounded_without_blocking_renewal(tmp_path):
    runtime, _ = _runtime(tmp_path)
    runtime.max_admission_records = 1
    first = _context(workspace="workspace-a")
    second = _context(workspace="workspace-b")

    await runtime.upsert_sandbox_admission_grant(_grant(first, revision=1))
    await runtime.upsert_sandbox_admission_grant(_grant(first, revision=2))

    with pytest.raises(BoxAdmissionError, match="record capacity reached"):
        await runtime.upsert_sandbox_admission_grant(_grant(second, revision=1))

    status = await runtime.get_status()
    assert status["limits"]["max_admission_records"] == 1


@pytest.mark.anyio
async def test_admission_revocation_cannot_bypass_fence_record_capacity(tmp_path):
    runtime, _ = _runtime(tmp_path)
    runtime.max_admission_records = 1
    first = _context(workspace="workspace-a")
    second = _context(workspace="workspace-b")

    await runtime.upsert_sandbox_admission_grant(_grant(first, revision=1))

    with pytest.raises(BoxAdmissionError, match="record capacity reached"):
        await runtime.revoke_sandbox_admission_grant(
            SandboxAdmissionRevocation(
                instance_uuid=second.instance_uuid,
                workspace_uuid=second.workspace_uuid,
                entitlement_revision=1,
            )
        )


@pytest.mark.anyio
async def test_same_revision_shorter_replica_renewal_is_idempotent(tmp_path):
    runtime, _ = _runtime(tmp_path)
    context = _context()
    longer = _grant(context, revision=9, expires_in=240)
    shorter = _grant(context, revision=9, expires_in=120)

    first = await runtime.upsert_sandbox_admission_grant(longer)
    second = await runtime.upsert_sandbox_admission_grant(shorter)

    assert second == first


@pytest.mark.anyio
async def test_strict_readiness_blocks_execution_when_cgroup_is_unavailable(
    tmp_path,
):
    runtime, backend = _runtime(tmp_path)
    context = _context()
    await runtime.upsert_sandbox_admission_grant(_grant(context))
    backend.readiness["cgroup_v2"] = False

    readiness = await runtime.get_readiness(force=True)
    assert readiness["ready"] is False
    assert readiness["checks"]["cgroup_v2"] is False
    with pytest.raises(BoxReadinessError, match="cgroup_v2"):
        await runtime.execute(BoxSpec(session_id="global", cmd="true"), context)


@pytest.mark.anyio
@pytest.mark.parametrize(
    "capability",
    [
        "hard_workspace_quota",
        "hard_read_only_mount_quota",
        "bounded_ephemeral_storage",
        "inode_quota",
    ],
)
async def test_managed_readiness_fails_closed_without_hard_storage_capability(
    tmp_path, capability
):
    runtime, backend = _runtime(tmp_path)
    context = _context()
    await runtime.upsert_sandbox_admission_grant(_grant(context))
    backend.readiness[capability] = False

    readiness = await runtime.get_readiness(force=True)

    assert readiness["ready"] is False
    assert readiness["checks"][capability] is False
    with pytest.raises(BoxReadinessError, match=capability):
        await runtime.execute(BoxSpec(session_id="global", cmd="true"), context)


@pytest.mark.anyio
async def test_explicit_nonproduction_override_only_relaxes_storage_checks(tmp_path):
    runtime, backend = _runtime(tmp_path, unsafe_soft_storage_limits=True)
    for capability in (
        "hard_workspace_quota",
        "hard_read_only_mount_quota",
        "bounded_ephemeral_storage",
        "inode_quota",
    ):
        backend.readiness[capability] = False

    readiness = await runtime.get_readiness(force=True)

    assert readiness["ready"] is True, [
        name for name, passed in readiness["checks"].items() if not passed
    ]
    assert readiness["unsafe_soft_storage_limits"] is True
    backend.readiness["cgroup_v2"] = False
    readiness = await runtime.get_readiness(force=True)
    assert readiness["ready"] is False
    assert readiness["checks"]["cgroup_v2"] is False


def test_admission_enforcement_cannot_be_disabled_in_process(tmp_path):
    runtime, _ = _runtime(tmp_path)

    runtime.init({"admission": {"required": False}})

    assert runtime.admission_required is True
    assert "cannot be disabled" in str(runtime._admission_config_error)


def test_grant_requires_timezone_and_rejects_boolean_limits():
    context = _context()
    payload = _grant(context).model_dump()
    payload["expires_at"] = dt.datetime.now()
    with pytest.raises(ValueError, match="timezone"):
        SandboxAdmissionGrant.model_validate(payload)

    payload["expires_at"] = dt.datetime.now(_UTC) + dt.timedelta(seconds=60)
    payload["max_sessions"] = True
    with pytest.raises(ValueError, match="integer"):
        SandboxAdmissionGrant.model_validate(payload)

    payload = _grant(context).model_dump()
    payload["plan"] = "pro"
    with pytest.raises(ValueError, match="Extra inputs"):
        SandboxAdmissionGrant.model_validate(payload)
