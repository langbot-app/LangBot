from __future__ import annotations

import asyncio
import hashlib
import io
import os
import stat
import threading
import time
import zipfile
from types import SimpleNamespace
from unittest import mock

import pytest

from langbot_plugin.api.definition.components.manifest import ComponentManifest
from langbot_plugin.api.definition.plugin import NonePlugin

from langbot_plugin.entities.io.context import (
    InstallationBinding,
    PluginInstallationDesiredState,
    PluginExecutionMode,
    PluginWorkerPolicy,
    RuntimeIdentity,
)
from langbot_plugin.runtime.context import RuntimeContext
from langbot_plugin.runtime.plugin.artifact import PluginArtifactStore
from langbot_plugin.runtime.plugin.dependency_environment import (
    DependencyEnvironmentPreparationError,
    PluginDependencyEnvironment,
)
from langbot_plugin.runtime.plugin.mgr import PluginManager
from langbot_plugin.runtime.plugin import mgr as manager_module
from langbot_plugin.runtime.plugin import container as runtime_plugin_container


def _package(
    *,
    body: str = "VALUE = 1",
    requirements: str | None = None,
) -> bytes:
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w") as archive:
        archive.writestr(
            "manifest.yaml",
            """
kind: Plugin
metadata:
  author: tester
  name: demo
  version: 1.0.0
spec: {}
""",
        )
        archive.writestr("main.py", body)
        if requirements is not None:
            archive.writestr("requirements.txt", requirements)
    return output.getvalue()


def _binding(
    installation_uuid: str,
    digest: str,
    *,
    workspace_uuid: str,
    generation: int = 1,
    revision: int = 1,
) -> InstallationBinding:
    return InstallationBinding(
        instance_uuid="instance-1",
        workspace_uuid=workspace_uuid,
        placement_generation=generation,
        installation_uuid=installation_uuid,
        runtime_revision=revision,
        artifact_digest=digest,
    )


def _manager(tmp_path) -> tuple[RuntimeContext, PluginManager]:
    context = RuntimeContext()
    context.bind_runtime(
        RuntimeIdentity(instance_uuid="instance-1", runtime_id="runtime-1"),
        PluginWorkerPolicy(
            max_cpus=1.0,
            max_memory_mb=512,
            max_pids=128,
            max_open_files=256,
            max_file_size_mb=512,
            require_hard_limits=True,
        ),
        "shared",
    )
    manager = PluginManager(context)
    manager.artifact_store = PluginArtifactStore(tmp_path / "plugin-runtime")
    context.plugin_mgr = manager
    return context, manager


async def _prepare_environment(store, artifact, *, execution_mode=None):
    root = store.base_path / "test-shared-environment"
    site_packages = root / "site-packages"
    site_packages.mkdir(parents=True, exist_ok=True)
    return PluginDependencyEnvironment(
        digest="b" * 64,
        artifact_digest=artifact.digest,
        requirements_digest="c" * 64,
        runtime_fingerprint="d" * 64,
        root_path=root,
        site_packages_path=site_packages,
    )


def _initialized_container() -> runtime_plugin_container.PluginContainer:
    return runtime_plugin_container.PluginContainer(
        manifest=ComponentManifest(
            owner="tester/demo",
            rel_path="manifest.yaml",
            manifest={
                "apiVersion": "v1",
                "kind": "Plugin",
                "metadata": {
                    "author": "tester",
                    "name": "demo",
                    "version": "1.0.0",
                    "label": {"en_US": "demo"},
                },
                "spec": {},
                "execution": {"python": {"path": "main.py", "attr": "Plugin"}},
            },
        ),
        plugin_instance=NonePlugin(),
        enabled=True,
        priority=0,
        plugin_config={},
        status=runtime_plugin_container.RuntimeContainerStatus.INITIALIZED,
        components=[],
    )


async def _drain_plugin_tasks(manager: PluginManager) -> None:
    while True:
        tasks = tuple(task for task in manager.plugin_run_tasks if not task.done())
        if not tasks:
            await asyncio.sleep(0)
            tasks = tuple(task for task in manager.plugin_run_tasks if not task.done())
            if not tasks:
                return
        await asyncio.gather(*tasks, return_exceptions=True)


async def test_manager_indexes_same_artifact_installations_by_complete_binding(
    tmp_path,
):
    context, manager = _manager(tmp_path)
    package = _package()
    digest = hashlib.sha256(package).hexdigest()
    binding_a = _binding(
        "installation-a",
        digest,
        workspace_uuid="workspace-a",
    )
    binding_b = _binding(
        "installation-b",
        digest,
        workspace_uuid="workspace-b",
    )

    await manager.apply_plugin_installation(
        binding_a,
        artifact_package=package,
        enabled=False,
    )
    await manager.apply_plugin_installation(
        binding_b,
        artifact_package=package,
        enabled=False,
    )

    runtimes = manager.installation_runtimes
    assert set(runtimes) == {binding_a, binding_b}
    assert (
        runtimes[binding_a].artifact.code_path == runtimes[binding_b].artifact.code_path
    )
    assert runtimes[binding_a].paths.home_path != runtimes[binding_b].paths.home_path
    assert runtimes[binding_a].paths.tmp_path != runtimes[binding_b].paths.tmp_path
    assert runtimes[binding_a].paths.data_path != runtimes[binding_b].paths.data_path
    if os.name != "nt":
        assert stat.S_IMODE(runtimes[binding_a].paths.root_path.stat().st_mode) == 0o700
        assert stat.S_IMODE(runtimes[binding_b].paths.root_path.stat().st_mode) == 0o700
    assert context.is_current_installation_binding(binding_a)
    assert context.is_current_installation_binding(binding_b)


async def test_certified_same_digest_installations_share_one_pool_worker(
    tmp_path,
    monkeypatch,
):
    _, manager = _manager(tmp_path)
    package = _package()
    digest = hashlib.sha256(package).hexdigest()
    binding_a = _binding("installation-a", digest, workspace_uuid="workspace-a")
    binding_b = _binding("installation-b", digest, workspace_uuid="workspace-b")
    scheduled = []

    async def prepare(store, artifact, *, execution_mode=None):
        root = store.base_path / "shared-environment"
        site_packages = root / "site-packages"
        site_packages.mkdir(parents=True, exist_ok=True)
        return PluginDependencyEnvironment(
            digest="b" * 64,
            artifact_digest=artifact.digest,
            requirements_digest="c" * 64,
            runtime_fingerprint="d" * 64,
            root_path=root,
            site_packages_path=site_packages,
        )

    monkeypatch.setattr(
        manager.worker_launcher, "prepare_dependency_environment", prepare
    )
    monkeypatch.setattr(
        manager, "_schedule_shared_worker", lambda worker: scheduled.append(worker)
    )

    await manager.apply_plugin_installation(
        binding_a,
        artifact_package=package,
        execution_mode=PluginExecutionMode.SHARED_CERTIFIED,
    )
    await manager.apply_plugin_installation(
        binding_b,
        execution_mode=PluginExecutionMode.SHARED_CERTIFIED,
    )

    runtime_a = manager.installation_runtimes[binding_a]
    runtime_b = manager.installation_runtimes[binding_b]
    assert runtime_a.shared_worker is runtime_b.shared_worker
    assert set(runtime_a.shared_worker.slots) == {binding_a, binding_b}
    assert scheduled == [runtime_a.shared_worker]
    assert runtime_a.paths.home_path != runtime_b.paths.home_path


async def test_dedicated_mode_keeps_one_worker_per_installation(tmp_path, monkeypatch):
    _, manager = _manager(tmp_path)
    package = _package()
    digest = hashlib.sha256(package).hexdigest()
    binding_a = _binding("installation-a", digest, workspace_uuid="workspace-a")
    binding_b = _binding("installation-b", digest, workspace_uuid="workspace-b")
    scheduled = []
    monkeypatch.setattr(
        manager.worker_launcher,
        "prepare_dependency_environment",
        _prepare_environment,
    )
    monkeypatch.setattr(manager, "_schedule_installation_worker", scheduled.append)

    await manager.apply_plugin_installation(binding_a, artifact_package=package)
    await manager.apply_plugin_installation(binding_b)

    assert manager.installation_runtimes[binding_a].shared_worker is None
    assert manager.installation_runtimes[binding_b].shared_worker is None
    assert scheduled == [
        manager.installation_runtimes[binding_a],
        manager.installation_runtimes[binding_b],
    ]


async def test_shared_worker_first_attach_starts_last_detach_stops(
    tmp_path,
    monkeypatch,
):
    _, manager = _manager(tmp_path)
    package = _package()
    digest = hashlib.sha256(package).hexdigest()
    binding_a = _binding("installation-a", digest, workspace_uuid="workspace-a")
    binding_b = _binding("installation-b", digest, workspace_uuid="workspace-b")
    started = []
    stopped = []
    monkeypatch.setattr(
        manager.worker_launcher,
        "prepare_dependency_environment",
        _prepare_environment,
    )
    monkeypatch.setattr(manager, "_schedule_shared_worker", started.append)

    async def stop(worker):
        stopped.append(worker)

    monkeypatch.setattr(manager, "_stop_shared_worker", stop)

    await manager.apply_plugin_installation(
        binding_a,
        artifact_package=package,
        execution_mode=PluginExecutionMode.SHARED_CERTIFIED,
    )
    await manager.apply_plugin_installation(
        binding_b,
        execution_mode=PluginExecutionMode.SHARED_CERTIFIED,
    )
    worker = manager.installation_runtimes[binding_a].shared_worker

    await manager.remove_plugin_installation(binding_a)
    assert stopped == []
    assert set(worker.slots) == {binding_b}

    await manager.remove_plugin_installation(binding_b)
    assert started == [worker]
    assert stopped == [worker]
    assert digest not in manager.shared_workers


async def test_shared_revision_fence_detaches_only_stale_slot(tmp_path, monkeypatch):
    context, manager = _manager(tmp_path)
    package = _package()
    digest = hashlib.sha256(package).hexdigest()
    old_a = _binding("installation-a", digest, workspace_uuid="workspace-a")
    new_a = old_a.model_copy(update={"runtime_revision": 2})
    binding_b = _binding("installation-b", digest, workspace_uuid="workspace-b")
    monkeypatch.setattr(
        manager.worker_launcher,
        "prepare_dependency_environment",
        _prepare_environment,
    )
    monkeypatch.setattr(manager, "_schedule_shared_worker", lambda worker: None)
    monkeypatch.setattr(manager, "_schedule_shared_slot_attach", lambda runtime: None)

    await manager.apply_plugin_installation(
        old_a,
        artifact_package=package,
        execution_mode=PluginExecutionMode.SHARED_CERTIFIED,
    )
    await manager.apply_plugin_installation(
        binding_b,
        execution_mode=PluginExecutionMode.SHARED_CERTIFIED,
    )
    worker = manager.installation_runtimes[old_a].shared_worker
    await manager.apply_plugin_installation(
        new_a,
        execution_mode=PluginExecutionMode.SHARED_CERTIFIED,
    )

    assert old_a not in worker.slots
    assert set(worker.slots) == {new_a, binding_b}
    assert context.is_current_installation_binding(new_a)
    assert context.is_current_installation_binding(binding_b)


async def test_shared_config_update_does_not_restart_sibling_worker(
    tmp_path, monkeypatch
):
    _, manager = _manager(tmp_path)
    package = _package()
    digest = hashlib.sha256(package).hexdigest()
    binding_a = _binding("installation-a", digest, workspace_uuid="workspace-a")
    binding_b = _binding("installation-b", digest, workspace_uuid="workspace-b")
    monkeypatch.setattr(
        manager.worker_launcher,
        "prepare_dependency_environment",
        _prepare_environment,
    )
    monkeypatch.setattr(manager, "_schedule_shared_worker", lambda worker: None)
    attached = []
    monkeypatch.setattr(manager, "_schedule_shared_slot_attach", attached.append)

    await manager.apply_plugin_installation(
        binding_a,
        artifact_package=package,
        execution_mode=PluginExecutionMode.SHARED_CERTIFIED,
    )
    await manager.apply_plugin_installation(
        binding_b,
        execution_mode=PluginExecutionMode.SHARED_CERTIFIED,
    )
    worker = manager.installation_runtimes[binding_a].shared_worker
    worker.plugin_handler = mock.Mock()
    worker.ready_event.set()
    worker_task = asyncio.create_task(asyncio.Event().wait())
    worker.launch_task = worker_task

    await manager.apply_plugin_installation(
        binding_a,
        execution_mode=PluginExecutionMode.SHARED_CERTIFIED,
    )

    assert worker.launch_task is worker_task
    assert not worker_task.cancelled()
    assert manager.installation_runtimes[binding_b].shared_worker is worker
    await asyncio.sleep(0)
    assert attached == [manager.installation_runtimes[binding_a]]
    worker_task.cancel()
    await asyncio.gather(worker_task, return_exceptions=True)


@pytest.mark.parametrize("retry_operation", ["apply", "reconcile"])
async def test_failed_sole_shared_slot_retries_with_registered_handler(
    tmp_path,
    monkeypatch,
    retry_operation,
):
    context, manager = _manager(tmp_path)
    package = _package()
    digest = hashlib.sha256(package).hexdigest()
    binding = _binding("installation-a", digest, workspace_uuid="workspace-a")
    launches = []
    monkeypatch.setattr(
        manager.worker_launcher,
        "prepare_dependency_environment",
        _prepare_environment,
    )
    monkeypatch.setattr(manager, "_schedule_shared_worker", launches.append)
    await manager.apply_plugin_installation(
        binding,
        artifact_package=package,
        execution_mode=PluginExecutionMode.SHARED_CERTIFIED,
    )
    runtime = manager.installation_runtimes[binding]
    worker = runtime.shared_worker
    container = _initialized_container()
    attach_attempts = 0

    class Control:
        async def call_action(self, action, data, *, action_context):
            return {
                "enabled": True,
                "priority": 0,
                "plugin_config": {},
                "installation_uuid": action_context.installation_uuid,
            }

    class Handler:
        def set_shared_pool_bindings(self, shared_digest, bindings):
            pass

        async def initialize_plugin_slot(self, candidate, settings, *, timeout=15.0):
            nonlocal attach_attempts
            attach_attempts += 1
            if attach_attempts == 1:
                raise RuntimeError("transient slot failure")

        async def get_plugin_slot_container(self, candidate):
            return container.model_dump()

    context.control_handler = Control()
    handler = Handler()
    worker.pending_plugin_handler = handler
    capability = manager._issue_registration_capability(
        plugin_author="tester",
        plugin_name="demo",
        plugin_path=str(worker.artifact.code_path),
        binding=binding,
        shared_pool_digest=digest,
    )
    alt_handler = Handler()
    with pytest.raises(ValueError, match="registration transport changed"):
        await manager.register_plugin(
            alt_handler,
            container.model_dump(),
            registration_capability=capability,
        )
    assert manager.is_registration_capability_pending(capability)
    assert worker.pending_plugin_handler is handler
    await manager.register_plugin(
        handler,
        container.model_dump(),
        registration_capability=capability,
    )
    await _drain_plugin_tasks(manager)

    assert runtime.state == "failed"
    assert runtime.error_code == "slot_attach_failed"
    assert worker.plugin_handler is handler
    assert worker.transport_registered_event.is_set()
    assert not worker.ready_event.is_set()

    if retry_operation == "apply":
        result = await manager.apply_plugin_installation(
            binding,
            execution_mode=PluginExecutionMode.SHARED_CERTIFIED,
        )
        assert result["state"] == "starting"
    else:
        result = await manager.reconcile_plugin_installations(
            (
                PluginInstallationDesiredState(
                    binding=binding,
                    execution_mode=PluginExecutionMode.SHARED_CERTIFIED,
                ),
            )
        )
        assert result["applied"] == [binding.installation_uuid]

    await _drain_plugin_tasks(manager)

    assert attach_attempts == 2
    assert launches == [worker]
    assert worker.plugin_handler is handler
    assert worker.transport_registered_event.is_set()
    assert runtime.state == "running"
    assert runtime.plugin_container is not None
    assert runtime.ready_event.is_set()
    assert worker.ready_event.is_set()


async def test_shared_registration_does_not_wait_for_slot_lifecycle_lock(
    tmp_path,
    monkeypatch,
):
    context, manager = _manager(tmp_path)
    package = _package()
    digest = hashlib.sha256(package).hexdigest()
    binding = _binding("installation-lock", digest, workspace_uuid="workspace-lock")
    monkeypatch.setattr(
        manager.worker_launcher,
        "prepare_dependency_environment",
        _prepare_environment,
    )
    monkeypatch.setattr(manager, "_schedule_shared_worker", lambda worker: None)
    await manager.apply_plugin_installation(
        binding,
        artifact_package=package,
        execution_mode=PluginExecutionMode.SHARED_CERTIFIED,
    )
    runtime = manager.installation_runtimes[binding]
    worker = runtime.shared_worker
    assert worker is not None
    handler = mock.Mock()
    handler.set_shared_pool_bindings = mock.Mock()
    worker.registration_generation = 1
    handler.shared_registration_generation = 1
    worker.pending_plugin_handler = handler
    capability = manager._issue_registration_capability(
        plugin_author="tester",
        plugin_name="demo",
        plugin_path=str(worker.artifact.code_path),
        binding=binding,
        shared_pool_digest=digest,
    )

    await worker.lifecycle_lock.acquire()
    try:
        await asyncio.wait_for(
            manager.register_plugin(
                handler,
                _initialized_container().model_dump(),
                registration_capability=capability,
            ),
            timeout=0.1,
        )
    finally:
        worker.lifecycle_lock.release()

    assert worker.plugin_handler is handler
    assert worker.transport_registered_event.is_set()


async def test_shared_registration_rejects_last_slot_draining_race(
    tmp_path,
    monkeypatch,
):
    context, manager = _manager(tmp_path)
    package = _package()
    digest = hashlib.sha256(package).hexdigest()
    binding = _binding("installation-drain", digest, workspace_uuid="workspace-drain")
    monkeypatch.setattr(
        manager.worker_launcher,
        "prepare_dependency_environment",
        _prepare_environment,
    )
    monkeypatch.setattr(manager, "_schedule_shared_worker", lambda worker: None)
    await manager.apply_plugin_installation(
        binding,
        artifact_package=package,
        execution_mode=PluginExecutionMode.SHARED_CERTIFIED,
    )
    runtime = manager.installation_runtimes[binding]
    worker = runtime.shared_worker
    assert worker is not None
    handler = mock.Mock()
    handler.set_shared_pool_bindings = mock.Mock()
    worker.registration_generation = 7
    handler.shared_registration_generation = 7
    worker.pending_plugin_handler = handler
    capability = manager._issue_registration_capability(
        plugin_author="tester",
        plugin_name="demo",
        plugin_path=str(worker.artifact.code_path),
        binding=binding,
        shared_pool_digest=digest,
    )

    worker.draining = True
    worker.registration_generation += 1
    worker.slots.pop(binding)
    with pytest.raises(ValueError, match="registration generation changed"):
        await manager.register_plugin(
            handler,
            _initialized_container().model_dump(),
            registration_capability=capability,
        )

    assert worker.plugin_handler is None
    assert not worker.transport_registered_event.is_set()


async def test_failed_shared_slot_retry_keeps_healthy_sibling_and_worker(
    tmp_path,
    monkeypatch,
):
    context, manager = _manager(tmp_path)
    package = _package()
    digest = hashlib.sha256(package).hexdigest()
    binding_a = _binding("installation-a", digest, workspace_uuid="workspace-a")
    binding_b = _binding("installation-b", digest, workspace_uuid="workspace-b")
    launches = []
    monkeypatch.setattr(
        manager.worker_launcher,
        "prepare_dependency_environment",
        _prepare_environment,
    )
    monkeypatch.setattr(manager, "_schedule_shared_worker", launches.append)
    await manager.apply_plugin_installation(
        binding_a,
        artifact_package=package,
        execution_mode=PluginExecutionMode.SHARED_CERTIFIED,
    )
    await manager.apply_plugin_installation(
        binding_b,
        execution_mode=PluginExecutionMode.SHARED_CERTIFIED,
    )
    runtime_a = manager.installation_runtimes[binding_a]
    runtime_b = manager.installation_runtimes[binding_b]
    worker = runtime_a.shared_worker
    container = _initialized_container()
    failed_once = False

    class Control:
        async def call_action(self, action, data, *, action_context):
            return {
                "enabled": True,
                "priority": 0,
                "plugin_config": {},
                "installation_uuid": action_context.installation_uuid,
            }

    class Handler:
        def set_shared_pool_bindings(self, shared_digest, bindings):
            pass

        async def initialize_plugin_slot(self, candidate, settings, *, timeout=15.0):
            nonlocal failed_once
            if candidate == binding_b and not failed_once:
                failed_once = True
                raise RuntimeError("transient slot failure")

        async def get_plugin_slot_container(self, candidate):
            return container.model_dump()

    context.control_handler = Control()
    handler = Handler()
    worker.pending_plugin_handler = handler
    capability = manager._issue_registration_capability(
        plugin_author="tester",
        plugin_name="demo",
        plugin_path=str(worker.artifact.code_path),
        binding=binding_a,
        shared_pool_digest=digest,
    )
    await manager.register_plugin(
        handler,
        container.model_dump(),
        registration_capability=capability,
    )
    await _drain_plugin_tasks(manager)
    healthy_container = runtime_a.plugin_container

    assert runtime_a.state == "running"
    assert runtime_b.state == "failed"
    assert worker.ready_event.is_set()

    result = await manager.apply_plugin_installation(
        binding_b,
        execution_mode=PluginExecutionMode.SHARED_CERTIFIED,
    )
    assert result["state"] == "starting"
    await _drain_plugin_tasks(manager)

    assert launches == [worker]
    assert worker.plugin_handler is handler
    assert runtime_a.state == "running"
    assert runtime_a.plugin_container is healthy_container
    assert runtime_a.ready_event.is_set()
    assert runtime_b.state == "running"
    assert runtime_b.ready_event.is_set()
    assert worker.ready_event.is_set()


async def test_shared_slot_attach_is_joined_and_revalidated_after_settings_await(
    tmp_path,
    monkeypatch,
):
    context, manager = _manager(tmp_path)
    package = _package()
    digest = hashlib.sha256(package).hexdigest()
    binding_a = _binding("installation-a", digest, workspace_uuid="workspace-a")
    binding_b = _binding("installation-b", digest, workspace_uuid="workspace-b")
    monkeypatch.setattr(
        manager.worker_launcher,
        "prepare_dependency_environment",
        _prepare_environment,
    )
    monkeypatch.setattr(manager, "_schedule_shared_worker", lambda worker: None)
    await manager.apply_plugin_installation(
        binding_a,
        artifact_package=package,
        execution_mode=PluginExecutionMode.SHARED_CERTIFIED,
    )
    await manager.apply_plugin_installation(
        binding_b,
        execution_mode=PluginExecutionMode.SHARED_CERTIFIED,
    )
    worker = manager.installation_runtimes[binding_a].shared_worker
    settings_started = asyncio.Event()
    release_settings = asyncio.Event()
    initialized = []

    class Control:
        async def call_action(self, action, data, *, action_context):
            settings_started.set()
            await release_settings.wait()
            return {"plugin_config": {}}

    class Handler:
        async def initialize_plugin_slot(self, binding, settings, *, timeout=15.0):
            initialized.append(binding)

        def cancel_inflight_messages_for_context(self, binding):
            pass

        async def detach_plugin_slot(self, binding):
            pass

        def set_shared_pool_bindings(self, digest, bindings):
            pass

    context.control_handler = Control()
    worker.plugin_handler = Handler()
    worker.ready_event.set()

    manager._schedule_shared_slot_attach(manager.installation_runtimes[binding_a])
    await asyncio.wait_for(settings_started.wait(), timeout=1)
    remove_task = asyncio.create_task(manager.remove_plugin_installation(binding_a))
    await asyncio.sleep(0)
    release_settings.set()
    await remove_task

    assert initialized == []
    assert set(worker.slots) == {binding_b}
    assert not worker.attach_tasks


async def test_shared_worker_supervisor_survives_representative_detach(
    tmp_path,
    monkeypatch,
):
    _, manager = _manager(tmp_path)
    package = _package()
    digest = hashlib.sha256(package).hexdigest()
    binding_a = _binding("installation-a", digest, workspace_uuid="workspace-a")
    binding_b = _binding("installation-b", digest, workspace_uuid="workspace-b")
    monkeypatch.setattr(
        manager.worker_launcher,
        "prepare_dependency_environment",
        _prepare_environment,
    )
    supervisor_started = asyncio.Event()
    release_supervisor = asyncio.Event()

    async def supervise(worker):
        supervisor_started.set()
        await release_supervisor.wait()

    monkeypatch.setattr(manager, "_supervise_shared_worker", supervise)
    await manager.apply_plugin_installation(
        binding_a,
        artifact_package=package,
        execution_mode=PluginExecutionMode.SHARED_CERTIFIED,
    )
    await manager.apply_plugin_installation(
        binding_b,
        execution_mode=PluginExecutionMode.SHARED_CERTIFIED,
    )
    worker = manager.installation_runtimes[binding_a].shared_worker
    await asyncio.wait_for(supervisor_started.wait(), timeout=1)
    supervisor = worker.launch_task

    await manager.remove_plugin_installation(binding_a)

    assert worker.launch_task is supervisor
    assert not supervisor.done()
    assert set(worker.slots) == {binding_b}
    release_supervisor.set()
    await supervisor


async def test_shared_worker_registration_attaches_all_slots_with_exact_settings(
    tmp_path,
    monkeypatch,
):
    context, manager = _manager(tmp_path)
    package = _package()
    digest = hashlib.sha256(package).hexdigest()
    binding_a = _binding("installation-a", digest, workspace_uuid="workspace-a")
    binding_b = _binding("installation-b", digest, workspace_uuid="workspace-b")
    monkeypatch.setattr(
        manager.worker_launcher,
        "prepare_dependency_environment",
        _prepare_environment,
    )
    monkeypatch.setattr(manager, "_schedule_shared_worker", lambda worker: None)
    await manager.apply_plugin_installation(
        binding_a,
        artifact_package=package,
        execution_mode=PluginExecutionMode.SHARED_CERTIFIED,
    )
    await manager.apply_plugin_installation(
        binding_b,
        execution_mode=PluginExecutionMode.SHARED_CERTIFIED,
    )
    settings_calls = []

    class Control:
        async def call_action(self, action, data, *, action_context):
            settings_calls.append((action, data, action_context))
            return {
                "enabled": True,
                "priority": 0,
                "plugin_config": {"workspace": action_context.workspace_uuid},
                "installation_uuid": action_context.installation_uuid,
            }

    base_container = runtime_plugin_container.PluginContainer(
        manifest=ComponentManifest(
            owner="tester/demo",
            rel_path="manifest.yaml",
            manifest={
                "apiVersion": "v1",
                "kind": "Plugin",
                "metadata": {
                    "author": "tester",
                    "name": "demo",
                    "version": "1.0.0",
                    "label": {"en_US": "demo"},
                },
                "spec": {},
                "execution": {"python": {"path": "main.py", "attr": "Plugin"}},
            },
        ),
        plugin_instance=NonePlugin(),
        enabled=True,
        priority=0,
        plugin_config={},
        status=runtime_plugin_container.RuntimeContainerStatus.MOUNTED,
        components=[],
    )

    class Handler:
        debug_plugin = False
        attached = []

        def set_shared_pool_bindings(self, shared_digest, bindings):
            self.shared_digest = shared_digest
            self.bindings = set(bindings)

        async def initialize_plugin_slot(self, binding, settings, *, timeout=15.0):
            self.attached.append((binding, settings))

        async def get_plugin_slot_container(self, binding):
            return base_container.model_copy(
                update={
                    "status": runtime_plugin_container.RuntimeContainerStatus.INITIALIZED
                }
            ).model_dump()

    context.control_handler = Control()
    handler = Handler()
    worker = manager.installation_runtimes[binding_a].shared_worker
    worker.pending_plugin_handler = handler
    capability = manager._issue_registration_capability(
        plugin_author="tester",
        plugin_name="demo",
        plugin_path=str(worker.artifact.code_path),
        binding=binding_a,
        shared_pool_digest=digest,
    )

    await manager.register_plugin(
        handler,
        base_container.model_dump(),
        registration_capability=capability,
    )
    await asyncio.gather(
        *(task for task in manager.plugin_run_tasks if task is not worker.launch_task)
    )

    assert handler.bindings == {binding_a, binding_b}
    assert [call[2] for call in settings_calls] == [binding_a, binding_b]
    assert [item[1]["plugin_config"] for item in handler.attached] == [
        {"workspace": "workspace-a"},
        {"workspace": "workspace-b"},
    ]


async def test_shared_registration_waits_for_validated_slot_before_running(
    tmp_path,
    monkeypatch,
):
    context, manager = _manager(tmp_path)
    package = _package()
    digest = hashlib.sha256(package).hexdigest()
    binding = _binding("installation-a", digest, workspace_uuid="workspace-a")
    monkeypatch.setattr(
        manager.worker_launcher,
        "prepare_dependency_environment",
        _prepare_environment,
    )
    monkeypatch.setattr(manager, "_schedule_shared_worker", lambda worker: None)
    await manager.apply_plugin_installation(
        binding,
        artifact_package=package,
        execution_mode=PluginExecutionMode.SHARED_CERTIFIED,
    )
    runtime = manager.installation_runtimes[binding]
    worker = runtime.shared_worker
    validation_started = asyncio.Event()
    release_validation = asyncio.Event()

    class Control:
        async def call_action(self, action, data, *, action_context):
            return {"enabled": True, "priority": 0, "plugin_config": {}}

    base_container = runtime_plugin_container.PluginContainer(
        manifest=ComponentManifest(
            owner="tester/demo",
            rel_path="manifest.yaml",
            manifest={
                "apiVersion": "v1",
                "kind": "Plugin",
                "metadata": {
                    "author": "tester",
                    "name": "demo",
                    "version": "1.0.0",
                    "label": {"en_US": "demo"},
                },
                "spec": {},
                "execution": {"python": {"path": "main.py", "attr": "Plugin"}},
            },
        ),
        plugin_instance=NonePlugin(),
        enabled=True,
        priority=0,
        plugin_config={},
        status=runtime_plugin_container.RuntimeContainerStatus.INITIALIZED,
        components=[],
    )

    class Handler:
        debug_plugin = False

        def set_shared_pool_bindings(self, digest, bindings):
            pass

        async def initialize_plugin_slot(self, candidate, settings, *, timeout=15.0):
            pass

        async def get_plugin_slot_container(self, candidate):
            validation_started.set()
            await release_validation.wait()
            return base_container.model_dump()

    context.control_handler = Control()
    handler = Handler()
    worker.pending_plugin_handler = handler
    capability = manager._issue_registration_capability(
        plugin_author="tester",
        plugin_name="demo",
        plugin_path=str(worker.artifact.code_path),
        binding=binding,
        shared_pool_digest=digest,
    )
    registration = asyncio.create_task(
        manager.register_plugin(
            handler,
            base_container.model_dump(),
            registration_capability=capability,
        )
    )
    await asyncio.wait_for(validation_started.wait(), timeout=1)

    assert registration.done()
    assert registration.exception() is None
    assert runtime.state == "starting"
    assert runtime.plugin_container is None
    assert not runtime.ready_event.is_set()
    assert not worker.ready_event.is_set()

    release_validation.set()
    await registration
    await _drain_plugin_tasks(manager)
    assert runtime.state == "running"
    assert runtime.plugin_container is not None
    assert runtime.ready_event.is_set()
    assert worker.ready_event.is_set()


async def test_shared_registration_reports_mixed_slot_attach_results(
    tmp_path,
    monkeypatch,
):
    context, manager = _manager(tmp_path)
    package = _package()
    digest = hashlib.sha256(package).hexdigest()
    binding_a = _binding("installation-a", digest, workspace_uuid="workspace-a")
    binding_b = _binding("installation-b", digest, workspace_uuid="workspace-b")
    monkeypatch.setattr(
        manager.worker_launcher,
        "prepare_dependency_environment",
        _prepare_environment,
    )
    monkeypatch.setattr(manager, "_schedule_shared_worker", lambda worker: None)
    await manager.apply_plugin_installation(
        binding_a,
        artifact_package=package,
        execution_mode=PluginExecutionMode.SHARED_CERTIFIED,
    )
    await manager.apply_plugin_installation(
        binding_b,
        execution_mode=PluginExecutionMode.SHARED_CERTIFIED,
    )
    worker = manager.installation_runtimes[binding_a].shared_worker

    class Control:
        async def call_action(self, action, data, *, action_context):
            return {
                "enabled": True,
                "priority": 0,
                "plugin_config": {},
                "installation_uuid": action_context.installation_uuid,
            }

    base_container = runtime_plugin_container.PluginContainer(
        manifest=ComponentManifest(
            owner="tester/demo",
            rel_path="manifest.yaml",
            manifest={
                "apiVersion": "v1",
                "kind": "Plugin",
                "metadata": {
                    "author": "tester",
                    "name": "demo",
                    "version": "1.0.0",
                    "label": {"en_US": "demo"},
                },
                "spec": {},
                "execution": {"python": {"path": "main.py", "attr": "Plugin"}},
            },
        ),
        plugin_instance=NonePlugin(),
        enabled=True,
        priority=0,
        plugin_config={},
        status=runtime_plugin_container.RuntimeContainerStatus.INITIALIZED,
        components=[],
    )

    class Handler:
        debug_plugin = False

        def set_shared_pool_bindings(self, digest, bindings):
            pass

        async def initialize_plugin_slot(self, candidate, settings, *, timeout=15.0):
            if candidate == binding_b:
                raise RuntimeError("slot config rejected")

        async def get_plugin_slot_container(self, candidate):
            return base_container.model_dump()

    context.control_handler = Control()
    handler = Handler()
    worker.pending_plugin_handler = handler
    capability = manager._issue_registration_capability(
        plugin_author="tester",
        plugin_name="demo",
        plugin_path=str(worker.artifact.code_path),
        binding=binding_a,
        shared_pool_digest=digest,
    )

    await manager.register_plugin(
        handler,
        base_container.model_dump(),
        registration_capability=capability,
    )
    await _drain_plugin_tasks(manager)

    runtime_a = manager.installation_runtimes[binding_a]
    runtime_b = manager.installation_runtimes[binding_b]
    assert runtime_a.state == "running"
    assert runtime_a.plugin_container is not None
    assert runtime_a.ready_event.is_set()
    assert runtime_b.state == "failed"
    assert runtime_b.error_code == "slot_attach_failed"
    assert runtime_b.error_message == "slot config rejected"
    assert runtime_b.plugin_container is None
    assert not runtime_b.ready_event.is_set()
    assert manager._installation_state_result(runtime_b)["state"] == "failed"
    assert worker.ready_event.is_set()


async def test_shared_slot_uninitialized_container_is_failed(tmp_path, monkeypatch):
    context, manager = _manager(tmp_path)
    package = _package()
    digest = hashlib.sha256(package).hexdigest()
    binding = _binding("installation-a", digest, workspace_uuid="workspace-a")
    monkeypatch.setattr(
        manager.worker_launcher,
        "prepare_dependency_environment",
        _prepare_environment,
    )
    monkeypatch.setattr(manager, "_schedule_shared_worker", lambda worker: None)
    await manager.apply_plugin_installation(
        binding,
        artifact_package=package,
        execution_mode=PluginExecutionMode.SHARED_CERTIFIED,
    )
    runtime = manager.installation_runtimes[binding]
    worker = runtime.shared_worker

    class Control:
        async def call_action(self, action, data, *, action_context):
            return {"enabled": True, "priority": 0, "plugin_config": {}}

    container = runtime_plugin_container.PluginContainer(
        manifest=ComponentManifest(
            owner="tester/demo",
            rel_path="manifest.yaml",
            manifest={
                "apiVersion": "v1",
                "kind": "Plugin",
                "metadata": {
                    "author": "tester",
                    "name": "demo",
                    "version": "1.0.0",
                    "label": {"en_US": "demo"},
                },
                "spec": {},
                "execution": {"python": {"path": "main.py", "attr": "Plugin"}},
            },
        ),
        plugin_instance=NonePlugin(),
        enabled=True,
        priority=0,
        plugin_config={},
        status=runtime_plugin_container.RuntimeContainerStatus.UNMOUNTED,
        components=[],
    )

    class Handler:
        debug_plugin = False

        def set_shared_pool_bindings(self, digest, bindings):
            pass

        async def initialize_plugin_slot(self, candidate, settings, *, timeout=15.0):
            pass

        async def get_plugin_slot_container(self, candidate):
            return container.model_dump()

    context.control_handler = Control()
    handler = Handler()
    worker.pending_plugin_handler = handler
    capability = manager._issue_registration_capability(
        plugin_author="tester",
        plugin_name="demo",
        plugin_path=str(worker.artifact.code_path),
        binding=binding,
        shared_pool_digest=digest,
    )

    await manager.register_plugin(
        handler,
        container.model_dump(),
        registration_capability=capability,
    )
    await _drain_plugin_tasks(manager)

    assert runtime.state == "failed"
    assert runtime.error_code == "slot_attach_failed"
    assert runtime.error_message == "Shared plugin slot did not initialize"
    assert runtime.plugin_container is None
    assert not runtime.ready_event.is_set()
    assert not worker.ready_event.is_set()


async def test_cancelled_remove_finishes_worker_revoke_before_propagating(
    tmp_path,
):
    context, manager = _manager(tmp_path)
    package = _package()
    digest = hashlib.sha256(package).hexdigest()
    binding = _binding(
        "installation-a",
        digest,
        workspace_uuid="workspace-a",
    )
    await manager.apply_plugin_installation(
        binding,
        artifact_package=package,
        enabled=False,
    )
    runtime = manager.installation_runtimes[binding]
    shutdown_started = asyncio.Event()
    allow_shutdown = asyncio.Event()

    class Handler:
        stdio_process = None
        conn = None

        def cancel_inflight_messages(self):
            return None

        async def shutdown_plugin(self):
            shutdown_started.set()
            await allow_shutdown.wait()

        async def close(self):
            return None

    handler = Handler()
    runtime.plugin_handler = handler
    manager.plugin_handlers.append(handler)

    remove_task = asyncio.create_task(manager.remove_plugin_installation(binding))
    await asyncio.wait_for(shutdown_started.wait(), timeout=1)
    remove_task.cancel()
    await asyncio.sleep(0)
    remove_task.cancel()
    allow_shutdown.set()

    with pytest.raises(asyncio.CancelledError):
        await remove_task
    assert not context.is_current_installation_binding(binding)
    assert binding not in manager.installation_runtimes
    assert binding.installation_uuid not in manager._active_binding_by_uuid
    assert handler not in manager.plugin_handlers
    assert runtime.plugin_handler is None

    with pytest.raises(ValueError, match="stale"):
        await manager.reconcile_plugin_installations(
            (PluginInstallationDesiredState(binding=binding, enabled=False),)
        )


async def test_remove_finishes_state_cleanup_when_handler_close_fails(
    tmp_path,
):
    context, manager = _manager(tmp_path)
    package = _package()
    digest = hashlib.sha256(package).hexdigest()
    binding = _binding(
        "installation-a",
        digest,
        workspace_uuid="workspace-a",
    )
    await manager.apply_plugin_installation(
        binding,
        artifact_package=package,
        enabled=False,
    )
    runtime = manager.installation_runtimes[binding]

    class Handler:
        stdio_process = None
        conn = None

        def cancel_inflight_messages(self):
            return None

        async def shutdown_plugin(self):
            return None

        async def close(self):
            raise RuntimeError("close failed")

    handler = Handler()
    runtime.plugin_handler = handler
    manager.plugin_handlers.append(handler)

    result = await manager.remove_plugin_installation(binding)

    assert result["state"] == "removed"
    assert not context.is_current_installation_binding(binding)
    assert binding not in manager.installation_runtimes
    assert binding.installation_uuid not in manager._active_binding_by_uuid
    assert handler not in manager.plugin_handlers
    assert runtime.plugin_handler is None


async def test_desired_state_does_not_reject_on_aggregate_worker_capacity(
    tmp_path,
    monkeypatch,
):
    context, manager = _manager(tmp_path)
    context.worker_policy = context.worker_policy.model_copy(
        update={
            "max_workers": 1,
            "max_total_cpus": 1.0,
            "max_total_memory_mb": 512,
            "require_hard_limits": False,
        }
    )
    context.runtime_profile = "oss_dev"
    manager.configure_worker_runtime(context.worker_policy, "oss_dev")
    monkeypatch.setattr(manager, "_schedule_installation_worker", lambda _runtime: None)
    package = _package()
    digest = hashlib.sha256(package).hexdigest()
    first = _binding("installation-a", digest, workspace_uuid="workspace-a")
    second = _binding("installation-b", digest, workspace_uuid="workspace-b")

    started = await manager.apply_plugin_installation(
        first,
        artifact_package=package,
        enabled=True,
    )
    second_started = await manager.apply_plugin_installation(second, enabled=True)
    replacement = await manager.apply_plugin_installation(
        _binding(
            "installation-a",
            digest,
            workspace_uuid="workspace-a",
            revision=2,
        ),
        enabled=True,
    )

    assert started["state"] == "starting"
    assert second_started["state"] == "starting"
    assert replacement["state"] == "starting"

    reconciled = await manager.reconcile_plugin_installations(
        (
            PluginInstallationDesiredState(
                binding=first.model_copy(update={"runtime_revision": 2})
            ),
            PluginInstallationDesiredState(binding=second),
        )
    )
    assert reconciled["applied"] == ["installation-a", "installation-b"]


async def test_shared_worker_capacity_rejects_new_digest_but_reuses_existing(
    tmp_path,
    monkeypatch,
):
    context, manager = _manager(tmp_path)
    context.worker_policy = context.worker_policy.model_copy(update={"max_workers": 1})
    monkeypatch.setattr(manager, "_schedule_shared_worker", lambda _worker: None)

    package_a = _package(body="VALUE = 1")
    digest_a = hashlib.sha256(package_a).hexdigest()
    binding_a = _binding("installation-a", digest_a, workspace_uuid="workspace-a")
    await manager.apply_plugin_installation(
        binding_a,
        artifact_package=package_a,
        enabled=False,
        execution_mode=PluginExecutionMode.SHARED_CERTIFIED,
    )
    runtime_a = manager.installation_runtimes[binding_a]
    runtime_a.dependency_environment = await _prepare_environment(
        manager.dependency_environment_store,
        runtime_a.artifact,
    )
    manager._attach_shared_worker(runtime_a)

    binding_b = _binding("installation-b", digest_a, workspace_uuid="workspace-b")
    await manager.apply_plugin_installation(
        binding_b,
        enabled=False,
        execution_mode=PluginExecutionMode.SHARED_CERTIFIED,
    )
    runtime_b = manager.installation_runtimes[binding_b]
    runtime_b.dependency_environment = runtime_a.dependency_environment
    manager._attach_shared_worker(runtime_b)
    assert runtime_a.shared_worker is runtime_b.shared_worker

    package_c = _package(body="VALUE = 2")
    digest_c = hashlib.sha256(package_c).hexdigest()
    binding_c = _binding("installation-c", digest_c, workspace_uuid="workspace-c")
    await manager.apply_plugin_installation(
        binding_c,
        artifact_package=package_c,
        enabled=False,
        execution_mode=PluginExecutionMode.SHARED_CERTIFIED,
    )
    runtime_c = manager.installation_runtimes[binding_c]
    runtime_c.dependency_environment = await _prepare_environment(
        manager.dependency_environment_store,
        runtime_c.artifact,
    )
    with pytest.raises(RuntimeError, match="Shared plugin worker capacity reached"):
        manager._attach_shared_worker(runtime_c)


async def test_shared_worker_draining_reserves_capacity_and_same_digest_identity(
    tmp_path,
    monkeypatch,
):
    context, manager = _manager(tmp_path)
    context.worker_policy = context.worker_policy.model_copy(update={"max_workers": 1})
    monkeypatch.setattr(manager, "_schedule_shared_worker", lambda _worker: None)
    package = _package()
    digest = hashlib.sha256(package).hexdigest()
    binding = _binding("installation-a", digest, workspace_uuid="workspace-a")
    await manager.apply_plugin_installation(
        binding,
        artifact_package=package,
        enabled=False,
        execution_mode=PluginExecutionMode.SHARED_CERTIFIED,
    )
    runtime = manager.installation_runtimes[binding]
    runtime.dependency_environment = await _prepare_environment(
        manager.dependency_environment_store,
        runtime.artifact,
    )
    manager._attach_shared_worker(runtime)
    worker = runtime.shared_worker
    assert worker is not None
    cleanup_entered = asyncio.Event()
    release_cleanup = asyncio.Event()

    async def blocked_stop(candidate):
        assert candidate is worker
        cleanup_entered.set()
        await release_cleanup.wait()

    monkeypatch.setattr(manager, "_stop_shared_worker", blocked_stop)
    detach = asyncio.create_task(manager._detach_shared_worker_slot(runtime))
    await asyncio.wait_for(cleanup_entered.wait(), timeout=1)

    assert manager._shared_workers[digest] is worker
    same_digest = manager_module.PluginInstallationRuntime(
        binding=_binding("installation-b", digest, workspace_uuid="workspace-b"),
        artifact=runtime.artifact,
        paths=runtime.paths,
        enabled=False,
        dependency_environment=runtime.dependency_environment,
        execution_mode=PluginExecutionMode.SHARED_CERTIFIED,
    )
    manager._attach_shared_worker(same_digest)
    assert same_digest.shared_worker is worker

    other_package = _package(body="VALUE = 2")
    other_digest = hashlib.sha256(other_package).hexdigest()
    other_artifact = manager.artifact_store.install_package(other_package, other_digest)
    other_runtime = manager_module.PluginInstallationRuntime(
        binding=_binding(
            "installation-c",
            hashlib.sha256(other_package).hexdigest(),
            workspace_uuid="workspace-c",
        ),
        artifact=other_artifact,
        paths=manager.artifact_store.ensure_installation_paths(
            _binding("installation-c", other_digest, workspace_uuid="workspace-c")
        ),
        enabled=False,
        execution_mode=PluginExecutionMode.SHARED_CERTIFIED,
    )
    other_runtime.dependency_environment = await _prepare_environment(
        manager.dependency_environment_store,
        other_runtime.artifact,
    )
    with pytest.raises(RuntimeError, match="Shared plugin worker capacity reached"):
        manager._attach_shared_worker(other_runtime)

    worker.slots.pop(same_digest.binding, None)
    release_cleanup.set()
    await detach
    assert digest not in manager._shared_workers


async def test_installation_lifecycle_runs_dependency_preparation_concurrently_bounded(
    tmp_path,
    monkeypatch,
):
    context = RuntimeContext()
    context.bind_runtime(
        RuntimeIdentity(instance_uuid="instance-1", runtime_id="runtime-1"),
        PluginWorkerPolicy(
            max_cpus=1.0,
            max_memory_mb=512,
            max_pids=128,
            max_open_files=256,
            max_file_size_mb=512,
            max_concurrent_restarts=2,
            require_hard_limits=True,
        ),
        "shared",
    )
    manager = PluginManager(context)
    manager.artifact_store = PluginArtifactStore(tmp_path / "plugin-runtime")
    context.plugin_mgr = manager
    package = _package(requirements="third-party-demo==1.0.0\n")
    digest = hashlib.sha256(package).hexdigest()
    first = _binding("installation-a", digest, workspace_uuid="workspace-a")
    second = _binding("installation-b", digest, workspace_uuid="workspace-b")
    third = _binding("installation-c", digest, workspace_uuid="workspace-c")
    await manager.apply_plugin_installation(
        first,
        artifact_package=package,
        enabled=False,
    )
    await manager.apply_plugin_installation(second, enabled=False)
    await manager.apply_plugin_installation(third, enabled=False)

    first_prepare_started = asyncio.Event()
    release_prepare = asyncio.Event()
    active_prepares = 0
    max_active_prepares = 0

    async def prepare(store, artifact, *, execution_mode=None):
        nonlocal active_prepares, max_active_prepares
        active_prepares += 1
        max_active_prepares = max(max_active_prepares, active_prepares)
        first_prepare_started.set()
        try:
            await release_prepare.wait()
        finally:
            active_prepares -= 1
        root = store.base_path / "serialized-environment"
        site_packages = root / "site-packages"
        site_packages.mkdir(parents=True, exist_ok=True)
        return PluginDependencyEnvironment(
            digest="b" * 64,
            artifact_digest=artifact.digest,
            requirements_digest="c" * 64,
            runtime_fingerprint="d" * 64,
            root_path=root,
            site_packages_path=site_packages,
        )

    monkeypatch.setattr(
        manager.worker_launcher,
        "prepare_dependency_environment",
        prepare,
    )
    monkeypatch.setattr(manager, "_schedule_installation_worker", lambda _runtime: None)

    first_task = asyncio.create_task(
        manager.apply_plugin_installation(first, enabled=True)
    )
    await first_prepare_started.wait()
    second_task = asyncio.create_task(
        manager.apply_plugin_installation(second, enabled=True)
    )

    async def wait_for_two_prepares():
        while active_prepares < 2:
            await asyncio.sleep(0)

    await asyncio.wait_for(wait_for_two_prepares(), timeout=1)
    third_task = asyncio.create_task(
        manager.apply_plugin_installation(third, enabled=True)
    )
    await asyncio.sleep(0)

    assert active_prepares == 2
    assert not third_task.done()
    release_prepare.set()
    await asyncio.gather(first_task, second_task, third_task)
    assert max_active_prepares == 2


async def test_installation_lock_waiter_does_not_consume_lifecycle_capacity(
    tmp_path,
    monkeypatch,
):
    context = RuntimeContext()
    context.bind_runtime(
        RuntimeIdentity(instance_uuid="instance-1", runtime_id="runtime-1"),
        PluginWorkerPolicy(
            max_cpus=1.0,
            max_memory_mb=512,
            max_pids=128,
            max_open_files=256,
            max_file_size_mb=512,
            max_concurrent_restarts=2,
            require_hard_limits=True,
        ),
        "shared",
    )
    manager = PluginManager(context)
    manager.artifact_store = PluginArtifactStore(tmp_path / "plugin-runtime")
    context.plugin_mgr = manager
    package = _package()
    digest = hashlib.sha256(package).hexdigest()
    first = _binding("installation-a", digest, workspace_uuid="workspace-a")
    other = _binding("installation-b", digest, workspace_uuid="workspace-b")
    entered = asyncio.Event()
    other_entered = asyncio.Event()
    release = asyncio.Event()

    original = manager._apply_plugin_installation_locked

    async def blocked(binding, **kwargs):
        if binding.installation_uuid == "installation-a" and not entered.is_set():
            entered.set()
            await release.wait()
        elif binding.installation_uuid == "installation-b":
            other_entered.set()
        return await original(binding, **kwargs)

    monkeypatch.setattr(manager, "_apply_plugin_installation_locked", blocked)
    first_task = asyncio.create_task(
        manager.apply_plugin_installation(
            first,
            artifact_package=package,
            enabled=False,
        )
    )
    await entered.wait()
    waiter = asyncio.create_task(
        manager.apply_plugin_installation(first, enabled=False)
    )
    other_task = asyncio.create_task(
        manager.apply_plugin_installation(other, enabled=False)
    )

    await asyncio.wait_for(other_entered.wait(), timeout=1)
    release.set()
    await asyncio.gather(first_task, waiter, other_task)


async def test_installation_lock_entry_survives_waiter_handoff(tmp_path, monkeypatch):
    _, manager = _manager(tmp_path)
    package = _package()
    digest = hashlib.sha256(package).hexdigest()
    binding = _binding("installation-a", digest, workspace_uuid="workspace-a")
    entered = asyncio.Event()
    release = asyncio.Event()
    calls = 0

    original = manager._apply_plugin_installation_locked

    async def blocked(*args, **kwargs):
        nonlocal calls
        calls += 1
        if calls == 1:
            entered.set()
            await release.wait()
        return await original(*args, **kwargs)

    monkeypatch.setattr(manager, "_apply_plugin_installation_locked", blocked)
    first = asyncio.create_task(
        manager.apply_plugin_installation(
            binding,
            artifact_package=package,
            enabled=False,
        )
    )
    await entered.wait()
    second = asyncio.create_task(
        manager.apply_plugin_installation(binding, enabled=False)
    )
    await asyncio.sleep(0)

    assert calls == 1
    release.set()
    await asyncio.gather(first, second)

    assert calls == 2
    assert manager._installation_operation_locks == {}


async def test_reconcile_absent_removal_serializes_with_direct_apply_for_same_installation(
    tmp_path,
    monkeypatch,
):
    _, manager = _manager(tmp_path)
    package = _package()
    digest = hashlib.sha256(package).hexdigest()
    old_binding = _binding("installation-a", digest, workspace_uuid="workspace-a")
    new_binding = old_binding.model_copy(update={"runtime_revision": 2})
    await manager.apply_plugin_installation(
        old_binding,
        artifact_package=package,
        enabled=False,
    )
    revoke_started = asyncio.Event()
    release_revoke = asyncio.Event()
    original_revoke = manager._revoke_installation_runtime

    async def blocked_revoke(binding):
        revoke_started.set()
        await release_revoke.wait()
        await original_revoke(binding)

    monkeypatch.setattr(manager, "_revoke_installation_runtime", blocked_revoke)

    reconcile_task = asyncio.create_task(manager.reconcile_plugin_installations(()))
    await revoke_started.wait()
    direct_apply = asyncio.create_task(
        manager.apply_plugin_installation(new_binding, enabled=False)
    )
    await asyncio.sleep(0)

    assert not direct_apply.done()

    release_revoke.set()
    await reconcile_task
    result = await asyncio.wait_for(direct_apply, timeout=1)

    assert result["state"] == "disabled"
    assert manager._active_binding_by_uuid["installation-a"] == new_binding


async def test_reconcile_watermark_gc_does_not_delete_newer_direct_state(
    tmp_path,
    monkeypatch,
):
    context, manager = _manager(tmp_path)
    package = _package()
    digest = hashlib.sha256(package).hexdigest()
    old_binding = _binding("installation-a", digest, workspace_uuid="workspace-a")
    new_binding = old_binding.model_copy(update={"runtime_revision": 2})
    await manager.apply_plugin_installation(
        old_binding,
        artifact_package=package,
        enabled=False,
    )
    await manager.remove_plugin_installation(old_binding)
    gc_started = asyncio.Event()
    release_gc = asyncio.Event()
    original_gc = context.reconcile_installation_watermarks

    async def blocked_gc(authoritative_bindings):
        gc_started.set()
        await release_gc.wait()
        original_gc(authoritative_bindings)

    monkeypatch.setattr(
        manager, "_reconcile_installation_watermarks_locked", blocked_gc
    )

    reconcile_task = asyncio.create_task(manager.reconcile_plugin_installations(()))
    await gc_started.wait()
    direct_apply = asyncio.create_task(
        manager.apply_plugin_installation(new_binding, enabled=False)
    )
    await asyncio.sleep(0)

    assert not direct_apply.done()

    release_gc.set()
    await reconcile_task
    await asyncio.wait_for(direct_apply, timeout=1)

    assert context.is_current_installation_binding(new_binding)
    with pytest.raises(ValueError, match="stale"):
        await manager.apply_plugin_installation(old_binding, enabled=False)


def test_pending_registration_capability_uses_independent_policy_bound(tmp_path):
    context, manager = _manager(tmp_path)
    context.worker_policy = context.worker_policy.model_copy(
        update={
            "max_workers": 1,
            "max_total_cpus": 1.0,
            "max_total_memory_mb": 512,
            "max_pending_registrations": 2,
        }
    )
    binding = _binding("installation-a", "a" * 64, workspace_uuid="workspace-a")
    context.activate_installation_binding(binding)

    issued = [
        manager._issue_registration_capability(
            plugin_author="tester",
            plugin_name="demo",
            plugin_path="/verified/code",
            binding=binding,
        )
        for _ in range(2)
    ]

    assert len(issued) == 2
    with pytest.raises(RuntimeError, match="capacity reached"):
        manager._issue_registration_capability(
            plugin_author="tester",
            plugin_name="demo",
            plugin_path="/verified/code",
            binding=binding,
        )


async def test_authoritative_reconcile_reclaims_inactive_historical_watermarks(
    tmp_path,
):
    context, manager = _manager(tmp_path)
    context.worker_policy = context.worker_policy.model_copy(
        update={"max_installations": 1}
    )
    package = _package()
    digest = hashlib.sha256(package).hexdigest()
    removed_binding = _binding("installation-a", digest, workspace_uuid="workspace-a")
    next_binding = _binding("installation-b", digest, workspace_uuid="workspace-b")

    await manager.apply_plugin_installation(
        removed_binding,
        artifact_package=package,
        enabled=False,
    )
    await manager.remove_plugin_installation(removed_binding)
    with pytest.raises(ValueError, match="fence capacity"):
        await manager.apply_plugin_installation(next_binding, enabled=False)

    result = await manager.reconcile_plugin_installations(())

    assert result["applied"] == []
    await manager.apply_plugin_installation(next_binding, enabled=False)
    assert context.is_current_installation_binding(next_binding)


async def test_new_revision_revokes_old_binding_and_stale_reapply_fails(tmp_path):
    context, manager = _manager(tmp_path)
    package = _package()
    digest = hashlib.sha256(package).hexdigest()
    old_binding = _binding(
        "installation-a",
        digest,
        workspace_uuid="workspace-a",
        revision=1,
    )
    new_binding = old_binding.model_copy(update={"runtime_revision": 2})

    await manager.apply_plugin_installation(
        old_binding,
        artifact_package=package,
        enabled=False,
    )
    await manager.apply_plugin_installation(new_binding, enabled=False)

    assert old_binding not in manager.installation_runtimes
    assert new_binding in manager.installation_runtimes
    assert not context.is_current_installation_binding(old_binding)
    assert context.is_current_installation_binding(new_binding)
    with pytest.raises(ValueError, match="stale"):
        await manager.apply_plugin_installation(old_binding, enabled=False)

    await manager.remove_plugin_installation(new_binding)
    with pytest.raises(ValueError, match="stale"):
        await manager.apply_plugin_installation(new_binding, enabled=False)


async def test_reconcile_revokes_absent_or_old_workers_even_if_artifact_missing(
    tmp_path,
):
    context, manager = _manager(tmp_path)
    package = _package()
    digest = hashlib.sha256(package).hexdigest()
    old_binding = _binding(
        "installation-a",
        digest,
        workspace_uuid="workspace-a",
    )
    missing_binding = old_binding.model_copy(
        update={"runtime_revision": 2, "artifact_digest": "b" * 64}
    )
    await manager.apply_plugin_installation(
        old_binding,
        artifact_package=package,
        enabled=False,
    )

    result = await manager.reconcile_plugin_installations(
        (PluginInstallationDesiredState(binding=missing_binding),)
    )

    assert result["removed"] == ["installation-a"]
    assert result["missing_artifacts"] == ["installation-a"]
    assert old_binding not in manager.installation_runtimes
    assert context.is_current_installation_binding(missing_binding)
    assert not context.is_current_installation_binding(old_binding)


def test_registration_capability_is_one_use_and_bound_to_complete_tuple(tmp_path):
    context, manager = _manager(tmp_path)
    package = _package()
    digest = hashlib.sha256(package).hexdigest()
    binding = _binding(
        "installation-a",
        digest,
        workspace_uuid="workspace-a",
    )
    context.activate_installation_binding(binding)
    capability = manager._issue_registration_capability(
        plugin_author="tester",
        plugin_name="demo",
        plugin_path="/verified/code",
        binding=binding,
    )

    registration = manager._consume_registration_capability(
        capability,
        plugin_author="tester",
        plugin_name="demo",
    )

    assert registration.binding == binding
    with pytest.raises(ValueError, match="invalid or already used"):
        manager._consume_registration_capability(
            capability,
            plugin_author="tester",
            plugin_name="demo",
        )


async def test_shared_apply_prepares_dependency_environment_before_worker_launch(
    tmp_path,
    monkeypatch,
):
    _, manager = _manager(tmp_path)
    package = _package(requirements="third-party-demo==1.0.0\n")
    digest = hashlib.sha256(package).hexdigest()
    binding = _binding(
        "installation-a",
        digest,
        workspace_uuid="workspace-a",
    )
    order: list[str] = []

    async def prepare(store, artifact, *, execution_mode=None):
        order.append("prepare")
        root = store.base_path / "test-environment"
        site_packages = root / "site-packages"
        site_packages.mkdir(parents=True)
        return PluginDependencyEnvironment(
            digest="b" * 64,
            artifact_digest=artifact.digest,
            requirements_digest="c" * 64,
            runtime_fingerprint="d" * 64,
            root_path=root,
            site_packages_path=site_packages,
        )

    def schedule(runtime):
        assert runtime.dependency_environment is not None
        order.append("launch")

    monkeypatch.setattr(
        manager.worker_launcher,
        "prepare_dependency_environment",
        prepare,
    )
    monkeypatch.setattr(manager, "_schedule_installation_worker", schedule)

    result = await manager.apply_plugin_installation(
        binding,
        artifact_package=package,
        enabled=True,
    )

    assert order == ["prepare", "launch"]
    assert result["state"] == "starting"
    assert result["dependency_environment_digest"] == "b" * 64


async def test_shared_dependency_failure_is_explicit_and_same_revision_can_retry(
    tmp_path,
    monkeypatch,
):
    _, manager = _manager(tmp_path)
    package = _package(requirements="third-party-demo==1.0.0\n")
    digest = hashlib.sha256(package).hexdigest()
    binding = _binding(
        "installation-a",
        digest,
        workspace_uuid="workspace-a",
    )
    launch_count = 0

    async def fail_prepare(store, artifact, *, execution_mode=None):
        raise DependencyEnvironmentPreparationError("dependency download failed")

    def schedule(runtime):
        nonlocal launch_count
        launch_count += 1

    monkeypatch.setattr(
        manager.worker_launcher,
        "prepare_dependency_environment",
        fail_prepare,
    )
    monkeypatch.setattr(manager, "_schedule_installation_worker", schedule)

    failed = await manager.apply_plugin_installation(
        binding,
        artifact_package=package,
        enabled=True,
    )

    assert failed == {
        "installation_uuid": "installation-a",
        "state": "failed",
        "artifact_path": failed["artifact_path"],
        "error_code": "dependency_prepare_failed",
        "message": "dependency download failed",
    }
    assert launch_count == 0
    runtime = manager.installation_runtimes[binding]
    assert runtime.launch_task is None
    assert runtime.dependency_environment is None

    async def successful_prepare(store, artifact, *, execution_mode=None):
        root = store.base_path / "retry-environment"
        site_packages = root / "site-packages"
        site_packages.mkdir(parents=True)
        return PluginDependencyEnvironment(
            digest="e" * 64,
            artifact_digest=artifact.digest,
            requirements_digest="f" * 64,
            runtime_fingerprint="1" * 64,
            root_path=root,
            site_packages_path=site_packages,
        )

    monkeypatch.setattr(
        manager.worker_launcher,
        "prepare_dependency_environment",
        successful_prepare,
    )
    retried = await manager.apply_plugin_installation(binding, enabled=True)

    assert retried["state"] == "starting"
    assert retried["dependency_environment_digest"] == "e" * 64
    assert launch_count == 1


async def test_reconcile_reports_dependency_failure_without_worker_launch(
    tmp_path,
    monkeypatch,
):
    _, manager = _manager(tmp_path)
    package = _package(requirements="third-party-demo==1.0.0\n")
    digest = hashlib.sha256(package).hexdigest()
    binding = _binding(
        "installation-a",
        digest,
        workspace_uuid="workspace-a",
    )
    await manager.apply_plugin_installation(
        binding,
        artifact_package=package,
        enabled=False,
    )

    async def fail_prepare(store, artifact, *, execution_mode=None):
        raise DependencyEnvironmentPreparationError("dependency download failed")

    monkeypatch.setattr(
        manager.worker_launcher,
        "prepare_dependency_environment",
        fail_prepare,
    )

    result = await manager.reconcile_plugin_installations(
        (PluginInstallationDesiredState(binding=binding),)
    )

    assert result["failed_installations"] == [
        {
            "installation_uuid": "installation-a",
            "error_code": "dependency_prepare_failed",
            "message": "dependency download failed",
        }
    ]
    assert manager.installation_runtimes[binding].launch_task is None


async def test_reconcile_batch_failure_cancels_and_joins_sibling_mutations(
    tmp_path,
    monkeypatch,
):
    context = RuntimeContext()
    context.bind_runtime(
        RuntimeIdentity(instance_uuid="instance-1", runtime_id="runtime-1"),
        PluginWorkerPolicy(
            max_cpus=1.0,
            max_memory_mb=512,
            max_pids=128,
            max_open_files=256,
            max_file_size_mb=512,
            max_concurrent_restarts=2,
            require_hard_limits=True,
        ),
        "shared",
    )
    manager = PluginManager(context)
    manager.artifact_store = PluginArtifactStore(tmp_path / "plugin-runtime")
    context.plugin_mgr = manager
    package = _package()
    digest = hashlib.sha256(package).hexdigest()
    first = _binding("installation-a", digest, workspace_uuid="workspace-a")
    second = _binding("installation-b", digest, workspace_uuid="workspace-b")
    await manager.apply_plugin_installation(
        first,
        artifact_package=package,
        enabled=False,
    )
    await manager.apply_plugin_installation(second, enabled=False)
    sibling_started = asyncio.Event()
    sibling_cancelled = asyncio.Event()
    original_apply = manager._apply_plugin_installation_locked

    async def apply_or_fail(binding, **kwargs):
        if binding.installation_uuid == "installation-a":
            raise RuntimeError("forced partial failure")
        if binding.installation_uuid == "installation-b":
            sibling_started.set()
            try:
                await asyncio.Event().wait()
            except asyncio.CancelledError:
                sibling_cancelled.set()
                raise
        return await original_apply(binding, **kwargs)

    monkeypatch.setattr(manager, "_apply_plugin_installation_locked", apply_or_fail)

    with pytest.raises(RuntimeError, match="forced partial failure"):
        await manager.reconcile_plugin_installations(
            (
                PluginInstallationDesiredState(binding=first),
                PluginInstallationDesiredState(binding=second),
            )
        )

    assert sibling_started.is_set()
    assert sibling_cancelled.is_set()
    assert manager._installation_operation_locks == {}
    assert not manager._reconcile_operation_lock.locked()


async def test_oss_desired_state_prepares_environment_before_worker_launch(
    tmp_path,
    monkeypatch,
):
    context = RuntimeContext()
    context.bind_runtime(
        RuntimeIdentity(instance_uuid="instance-1", runtime_id="runtime-1"),
        PluginWorkerPolicy(
            max_cpus=1.0,
            max_memory_mb=512,
            max_pids=128,
            max_open_files=256,
            max_file_size_mb=512,
            require_hard_limits=False,
        ),
        "oss_dev",
    )
    manager = PluginManager(context)
    manager.artifact_store = PluginArtifactStore(tmp_path / "plugin-runtime")
    manager.configure_worker_runtime(context.worker_policy, "oss_dev")
    context.plugin_mgr = manager
    package = _package(requirements="third-party-demo==1.0.0\n")
    digest = hashlib.sha256(package).hexdigest()
    binding = _binding(
        "installation-a",
        digest,
        workspace_uuid="workspace-a",
    )
    order: list[str] = []

    async def prepare(store, artifact, *, execution_mode=None):
        order.append("prepare")
        root = store.base_path / "test-environment"
        site_packages = root / "site-packages"
        site_packages.mkdir(parents=True)
        return PluginDependencyEnvironment(
            digest="b" * 64,
            artifact_digest=artifact.digest,
            requirements_digest="c" * 64,
            runtime_fingerprint="d" * 64,
            root_path=root,
            site_packages_path=site_packages,
        )

    def schedule(runtime):
        assert runtime.dependency_environment is not None
        order.append("launch")

    monkeypatch.setattr(
        manager.worker_launcher,
        "prepare_dependency_environment",
        prepare,
    )
    monkeypatch.setattr(manager, "_schedule_installation_worker", schedule)

    result = await manager.apply_plugin_installation(
        binding,
        artifact_package=package,
        enabled=True,
    )

    assert result["state"] == "starting"
    assert result["dependency_environment_digest"] == "b" * 64
    assert order == ["prepare", "launch"]


async def test_installation_supervisor_restarts_crashed_enabled_worker(
    tmp_path,
    monkeypatch,
):
    _, manager = _manager(tmp_path)
    package = _package()
    digest = hashlib.sha256(package).hexdigest()
    binding = _binding(
        "installation-a",
        digest,
        workspace_uuid="workspace-a",
    )
    await manager.apply_plugin_installation(
        binding,
        artifact_package=package,
        enabled=False,
    )
    runtime = manager.installation_runtimes[binding]
    runtime.enabled = True
    second_generation_started = asyncio.Event()
    calls = 0

    async def launch(candidate):
        nonlocal calls
        assert candidate == binding
        calls += 1
        if calls == 1:
            raise RuntimeError("worker crashed")
        runtime.ready_event.set()
        second_generation_started.set()
        await asyncio.Event().wait()

    monkeypatch.setattr(manager, "launch_plugin_installation", launch)
    monkeypatch.setattr(
        "langbot_plugin.runtime.plugin.mgr._PLUGIN_RESTART_INITIAL_DELAY_SEC",
        0,
    )

    manager._schedule_installation_worker(runtime)
    first_supervisor = runtime.launch_task
    manager._schedule_installation_worker(runtime)
    assert runtime.launch_task is first_supervisor
    await asyncio.wait_for(second_generation_started.wait(), timeout=1)

    async def wait_for_launches_to_finish():
        while manager.restart_coordinator.snapshot()["active_launches"]:
            await asyncio.sleep(0)

    await asyncio.wait_for(wait_for_launches_to_finish(), timeout=1)

    assert calls == 2
    assert runtime.launch_task is not None
    assert runtime.launch_task in manager.plugin_run_tasks
    assert manager.restart_coordinator.snapshot()["active_launches"] == 0
    assert manager.restart_coordinator.snapshot()["restart_failures_total"] == 1

    await manager._stop_installation_worker(runtime)

    assert runtime.launch_task is None
    assert manager.plugin_run_tasks == []


async def test_installation_worker_ready_timeout_cancels_hung_process(
    tmp_path,
    monkeypatch,
):
    _, manager = _manager(tmp_path)
    package = _package()
    digest = hashlib.sha256(package).hexdigest()
    binding = _binding(
        "installation-a",
        digest,
        workspace_uuid="workspace-a",
    )
    await manager.apply_plugin_installation(
        binding,
        artifact_package=package,
        enabled=False,
    )
    runtime = manager.installation_runtimes[binding]
    runtime.enabled = True
    cancelled = asyncio.Event()

    async def launch(_candidate):
        try:
            await asyncio.Event().wait()
        finally:
            cancelled.set()

    monkeypatch.setattr(manager, "launch_plugin_installation", launch)
    monkeypatch.setattr(manager_module, "_PLUGIN_READY_TIMEOUT_SEC", 0.01)

    with pytest.raises(TimeoutError, match="did not become ready"):
        await manager._run_installation_worker_attempt(runtime, None)

    assert cancelled.is_set()


async def test_shared_connection_does_not_claim_registration_before_capability_validation(
    tmp_path,
    monkeypatch,
):
    _, manager = _manager(tmp_path)
    package = _package()
    digest = hashlib.sha256(package).hexdigest()
    binding = _binding("installation-a", digest, workspace_uuid="workspace-a")
    monkeypatch.setattr(
        manager.worker_launcher,
        "prepare_dependency_environment",
        _prepare_environment,
    )
    monkeypatch.setattr(manager, "_schedule_shared_worker", lambda _worker: None)
    await manager.apply_plugin_installation(
        binding,
        artifact_package=package,
        execution_mode=PluginExecutionMode.SHARED_CERTIFIED,
    )
    worker = manager.installation_runtimes[binding].shared_worker
    assert worker is not None

    class FakeConnection:
        async def close(self):
            return None

    class FakeHandler:
        async def run(self):
            await asyncio.Event().wait()

    handler = FakeHandler()
    callback_started = asyncio.Event()

    class CapturingController:
        process = None

        async def run(self, callback):
            task = asyncio.create_task(callback(FakeConnection()))
            callback_started.set()
            try:
                await task
            finally:
                if not task.done():
                    task.cancel()
                    await asyncio.gather(task, return_exceptions=True)

        async def close(self):
            return None

    monkeypatch.setattr(
        manager.worker_launcher,
        "create_shared_pool_controller",
        lambda _spec: CapturingController(),
    )
    monkeypatch.setattr(
        manager_module.runtime_plugin_handler_cls,
        "PluginConnectionHandler",
        lambda *args, **kwargs: handler,
    )

    launch = asyncio.create_task(manager._launch_shared_worker(worker))
    await asyncio.wait_for(callback_started.wait(), timeout=1)
    await asyncio.sleep(0)

    assert worker.plugin_handler is None
    assert worker.pending_plugin_handler is handler
    assert handler in manager.plugin_handlers

    launch.cancel()
    await asyncio.gather(launch, return_exceptions=True)


async def test_shared_registration_failure_does_not_clear_new_worker_handler(
    tmp_path,
    monkeypatch,
):
    _, manager = _manager(tmp_path)
    package = _package()
    digest = hashlib.sha256(package).hexdigest()
    binding = _binding("installation-a", digest, workspace_uuid="workspace-a")
    monkeypatch.setattr(
        manager.worker_launcher,
        "prepare_dependency_environment",
        _prepare_environment,
    )
    monkeypatch.setattr(manager, "_schedule_shared_worker", lambda _worker: None)
    await manager.apply_plugin_installation(
        binding,
        artifact_package=package,
        execution_mode=PluginExecutionMode.SHARED_CERTIFIED,
    )
    worker = manager.installation_runtimes[binding].shared_worker
    assert worker is not None

    class OldHandler:
        pass

    class NewHandler:
        pass

    old_handler = OldHandler()
    new_handler = NewHandler()
    worker.plugin_handler = new_handler
    manager.plugin_handlers.extend([old_handler, new_handler])

    await manager.remove_plugin_handler(old_handler)

    assert worker.plugin_handler is new_handler
    assert new_handler in manager.plugin_handlers


async def test_shared_worker_ready_timeout_cancels_hung_controller_and_records_failure(
    tmp_path,
    monkeypatch,
):
    _, manager = _manager(tmp_path)
    package = _package()
    digest = hashlib.sha256(package).hexdigest()
    binding = _binding("installation-a", digest, workspace_uuid="workspace-a")
    monkeypatch.setattr(
        manager.worker_launcher,
        "prepare_dependency_environment",
        _prepare_environment,
    )
    schedule_shared_worker = manager._schedule_shared_worker
    monkeypatch.setattr(manager, "_schedule_shared_worker", lambda _worker: None)
    await manager.apply_plugin_installation(
        binding,
        artifact_package=package,
        execution_mode=PluginExecutionMode.SHARED_CERTIFIED,
    )
    worker = manager.installation_runtimes[binding].shared_worker
    cancelled = asyncio.Event()
    closed = asyncio.Event()

    class NeverRegisterController:
        process = None

        async def run(self, _callback):
            try:
                await asyncio.Event().wait()
            finally:
                cancelled.set()

        async def close(self):
            closed.set()

    monkeypatch.setattr(
        manager.worker_launcher,
        "create_shared_pool_controller",
        lambda _spec: NeverRegisterController(),
    )
    monkeypatch.setattr(
        manager_module,
        "_SHARED_TRANSPORT_READY_TIMEOUT_SEC",
        0.01,
    )
    monkeypatch.setattr(manager_module, "_PLUGIN_RESTART_INITIAL_DELAY_SEC", 60.0)

    assert worker is not None
    schedule_shared_worker(worker)

    async def wait_for_failure():
        while manager.restart_coordinator.snapshot()["restart_failures_total"] < 1:
            await asyncio.sleep(0)

    await asyncio.wait_for(wait_for_failure(), timeout=1)

    assert cancelled.is_set()
    assert closed.is_set()
    assert worker.controller is None
    assert manager.restart_coordinator.snapshot()["active_launches"] == 0
    assert manager.installation_runtimes[binding].state == "failed"
    assert "did not register" in manager.installation_runtimes[binding].error_message
    await manager._stop_shared_worker(worker)


async def test_shared_watchdog_failure_cleans_attempt_and_counts_recovery(
    tmp_path, monkeypatch
):
    _, manager = _manager(tmp_path)
    package = _package()
    digest = hashlib.sha256(package).hexdigest()
    binding = _binding("installation-a", digest, workspace_uuid="workspace-a")
    monkeypatch.setattr(
        manager.worker_launcher, "prepare_dependency_environment", _prepare_environment
    )
    monkeypatch.setattr(manager, "_schedule_shared_worker", lambda _worker: None)
    await manager.apply_plugin_installation(
        binding,
        artifact_package=package,
        execution_mode=PluginExecutionMode.SHARED_CERTIFIED,
    )
    worker = manager.installation_runtimes[binding].shared_worker
    stopped = asyncio.Event()

    class FastWatchdog(manager_module.WorkerWatchdog):
        def __init__(self):
            super().__init__(timeout_seconds=0.01)

        async def watch(self, probe):
            await super().watch(probe, interval=0.001, probe_timeout=0.005)

    class Handler:
        async def call_action(self, *args, **kwargs):
            await asyncio.Event().wait()

    class Permit:
        is_half_open_probe = False

        def mark_ready(self):
            pass

    async def launch(candidate):
        candidate.plugin_handler = Handler()
        candidate.transport_registered_event.set()
        try:
            await asyncio.Event().wait()
        finally:
            candidate.plugin_handler = None
            stopped.set()

    monkeypatch.setattr(manager_module, "WorkerWatchdog", FastWatchdog)
    monkeypatch.setattr(manager, "_launch_shared_worker", launch)
    with pytest.raises(TimeoutError, match="worker unresponsive"):
        await asyncio.wait_for(manager._run_shared_worker_attempt(worker, Permit()), 2)
    assert stopped.is_set()
    assert worker.watchdog_restarts == 1
    assert worker.last_watchdog_restart_at is not None
    assert worker.plugin_handler is None
    assert binding in worker.slots


async def test_shared_transport_registration_survives_slow_slot_attach(
    tmp_path,
    monkeypatch,
):
    _, manager = _manager(tmp_path)
    package = _package()
    digest = hashlib.sha256(package).hexdigest()
    binding = _binding("installation-a", digest, workspace_uuid="workspace-a")
    monkeypatch.setattr(
        manager.worker_launcher,
        "prepare_dependency_environment",
        _prepare_environment,
    )
    monkeypatch.setattr(manager, "_schedule_shared_worker", lambda _worker: None)
    await manager.apply_plugin_installation(
        binding,
        artifact_package=package,
        execution_mode=PluginExecutionMode.SHARED_CERTIFIED,
    )
    worker = manager.installation_runtimes[binding].shared_worker
    assert worker is not None
    release_worker = asyncio.Event()
    permit_ready = asyncio.Event()

    class Permit:
        is_half_open_probe = False

        def mark_ready(self):
            permit_ready.set()

    async def launch(_worker):
        _worker.transport_registered_event.set()
        await release_worker.wait()

    monkeypatch.setattr(manager, "_launch_shared_worker", launch)
    monkeypatch.setattr(manager_module, "_PLUGIN_READY_TIMEOUT_SEC", 0.01)
    attempt = asyncio.create_task(manager._run_shared_worker_attempt(worker, Permit()))

    await asyncio.wait_for(permit_ready.wait(), timeout=1)
    await asyncio.sleep(0.02)
    assert not attempt.done()
    release_worker.set()
    worker.slots.clear()
    await attempt


async def test_shared_slot_attach_disables_inner_rpc_timeout(
    tmp_path,
    monkeypatch,
):
    context, manager = _manager(tmp_path)
    package = _package()
    digest = hashlib.sha256(package).hexdigest()
    binding = _binding("installation-a", digest, workspace_uuid="workspace-a")
    monkeypatch.setattr(
        manager.worker_launcher,
        "prepare_dependency_environment",
        _prepare_environment,
    )
    monkeypatch.setattr(manager, "_schedule_shared_worker", lambda _worker: None)
    await manager.apply_plugin_installation(
        binding,
        artifact_package=package,
        execution_mode=PluginExecutionMode.SHARED_CERTIFIED,
    )
    runtime = manager.installation_runtimes[binding]
    worker = runtime.shared_worker
    assert worker is not None
    container = _initialized_container()
    seen_timeout = object()

    class Control:
        async def call_action(self, action, data, *, action_context):
            return {
                "plugin_config": {},
                "installation_uuid": action_context.installation_uuid,
            }

    class Handler:
        async def initialize_plugin_slot(self, candidate, settings, *, timeout=15.0):
            nonlocal seen_timeout
            seen_timeout = timeout

        async def get_plugin_slot_container(self, candidate):
            return container.model_dump()

    context.control_handler = Control()
    handler = Handler()
    worker.plugin_handler = handler
    await manager._initialize_shared_slot(runtime, handler)

    assert seen_timeout is None
    assert runtime.state == "running"


async def test_hung_shared_slot_attach_times_out_and_unblocks_sibling_and_removal(
    tmp_path,
    monkeypatch,
):
    context, manager = _manager(tmp_path)
    package = _package()
    digest = hashlib.sha256(package).hexdigest()
    binding_a = _binding("installation-a", digest, workspace_uuid="workspace-a")
    binding_b = _binding("installation-b", digest, workspace_uuid="workspace-b")
    monkeypatch.setattr(
        manager.worker_launcher,
        "prepare_dependency_environment",
        _prepare_environment,
    )
    monkeypatch.setattr(manager, "_schedule_shared_worker", lambda _worker: None)
    await manager.apply_plugin_installation(
        binding_a,
        artifact_package=package,
        execution_mode=PluginExecutionMode.SHARED_CERTIFIED,
    )
    await manager.apply_plugin_installation(
        binding_b,
        execution_mode=PluginExecutionMode.SHARED_CERTIFIED,
    )
    worker = manager.installation_runtimes[binding_a].shared_worker
    assert worker is not None
    container = _initialized_container()
    first_cancelled = asyncio.Event()

    class Control:
        async def call_action(self, action, data, *, action_context):
            return {
                "plugin_config": {},
                "installation_uuid": action_context.installation_uuid,
            }

    class Handler:
        async def initialize_plugin_slot(self, candidate, settings, *, timeout=15.0):
            if candidate == binding_a:
                try:
                    await asyncio.Event().wait()
                finally:
                    first_cancelled.set()

        async def get_plugin_slot_container(self, candidate):
            return container.model_dump()

        def cancel_inflight_messages_for_context(self, candidate):
            pass

        async def detach_plugin_slot(self, candidate):
            pass

        def set_shared_pool_bindings(self, digest, bindings):
            pass

    context.control_handler = Control()
    handler = Handler()
    worker.plugin_handler = handler
    monkeypatch.setattr(manager_module, "_SHARED_SLOT_ATTACH_TIMEOUT_SEC", 0.01)
    task_a = manager._schedule_shared_slot_attach(
        manager.installation_runtimes[binding_a]
    )
    task_b = manager._schedule_shared_slot_attach(
        manager.installation_runtimes[binding_b]
    )
    assert task_a is not None
    assert task_b is not None

    await asyncio.wait_for(asyncio.gather(task_a, task_b, return_exceptions=True), 1)
    assert first_cancelled.is_set()
    assert manager.installation_runtimes[binding_a].state == "failed"
    assert manager.installation_runtimes[binding_b].state == "running"
    await asyncio.wait_for(manager.remove_plugin_installation(binding_a), 1)
    assert binding_a not in worker.slots
    assert binding_b in worker.slots


async def test_shared_worker_manager_restart_reattaches_every_current_slot(
    tmp_path,
    monkeypatch,
):
    _, manager = _manager(tmp_path)
    package = _package()
    digest = hashlib.sha256(package).hexdigest()
    binding_a = _binding("installation-a", digest, workspace_uuid="workspace-a")
    binding_b = _binding("installation-b", digest, workspace_uuid="workspace-b")
    monkeypatch.setattr(
        manager.worker_launcher,
        "prepare_dependency_environment",
        _prepare_environment,
    )
    monkeypatch.setattr(manager_module, "_PLUGIN_RESTART_INITIAL_DELAY_SEC", 0.0)
    launches = 0
    attached: list[tuple[int, InstallationBinding]] = []
    allow_first_crash = asyncio.Event()

    async def launch(worker):
        nonlocal launches
        launches += 1
        worker.ready_event.set()
        for runtime in tuple(worker.slots.values()):
            attached.append((launches, runtime.binding))
        if launches == 1:
            await allow_first_crash.wait()
            raise RuntimeError("simulated shared worker crash")
        manager._shutting_down = True

    monkeypatch.setattr(manager, "_launch_shared_worker", launch)

    await manager.apply_plugin_installation(
        binding_a,
        artifact_package=package,
        execution_mode=PluginExecutionMode.SHARED_CERTIFIED,
    )
    await manager.apply_plugin_installation(
        binding_b,
        execution_mode=PluginExecutionMode.SHARED_CERTIFIED,
    )
    allow_first_crash.set()
    worker = manager.installation_runtimes[binding_a].shared_worker
    assert worker is not None
    assert worker.launch_task is not None
    await asyncio.wait_for(worker.launch_task, timeout=1)

    assert launches == 2
    assert {
        binding.installation_uuid for attempt, binding in attached if attempt == 2
    } == {
        binding_a.installation_uuid,
        binding_b.installation_uuid,
    }
    assert manager.restart_coordinator.snapshot()["restart_failures_total"] == 1


async def test_first_installation_launches_are_globally_bounded(
    tmp_path,
    monkeypatch,
):
    context, manager = _manager(tmp_path)
    package = _package()
    digest = hashlib.sha256(package).hexdigest()
    first = _binding("installation-a", digest, workspace_uuid="workspace-a")
    second = _binding("installation-b", digest, workspace_uuid="workspace-b")
    await manager.apply_plugin_installation(
        first,
        artifact_package=package,
        enabled=False,
    )
    await manager.apply_plugin_installation(second, enabled=False)
    first_started = asyncio.Event()
    release_first = asyncio.Event()
    started: list[str] = []

    async def launch(candidate):
        started.append(candidate.installation_uuid)
        runtime = manager.installation_runtimes[candidate]
        runtime.ready_event.set()
        if candidate == first:
            first_started.set()
            await release_first.wait()
        runtime.enabled = False

    monkeypatch.setattr(manager, "launch_plugin_installation", launch)

    first_runtime = manager.installation_runtimes[first]
    second_runtime = manager.installation_runtimes[second]
    first_runtime.enabled = True
    second_runtime.enabled = True
    manager._schedule_installation_worker(first_runtime)
    await first_started.wait()
    manager._schedule_installation_worker(second_runtime)
    await asyncio.sleep(0)

    assert started == ["installation-a"]
    release_first.set()
    await asyncio.wait_for(second_runtime.launch_task, timeout=1)

    assert started == ["installation-a", "installation-b"]
    await manager._stop_installation_worker(first_runtime)
    await manager._stop_installation_worker(second_runtime)


async def test_unrelated_artifact_publications_do_not_block_each_other(
    tmp_path,
    monkeypatch,
):
    context, manager = _manager(tmp_path)
    first_package = _package(body="VALUE = 1")
    second_package = _package(body="VALUE = 2")
    first_digest = hashlib.sha256(first_package).hexdigest()
    second_digest = hashlib.sha256(second_package).hexdigest()
    first = _binding("installation-a", first_digest, workspace_uuid="workspace-a")
    second = _binding("installation-b", second_digest, workspace_uuid="workspace-b")
    install_started = threading.Event()
    release_install = threading.Event()
    original_install = manager.artifact_store.install_package

    def install_package(package, expected_digest):
        if expected_digest == first_digest:
            install_started.set()
            release_install.wait(timeout=5)
        return original_install(package, expected_digest)

    monkeypatch.setattr(manager.artifact_store, "install_package", install_package)

    first_task = asyncio.create_task(
        manager.apply_plugin_installation(
            first,
            artifact_package=first_package,
            enabled=False,
        )
    )

    async def wait_for_install_started():
        while not install_started.is_set():
            await asyncio.sleep(0)

    await asyncio.wait_for(wait_for_install_started(), timeout=1)
    second_task = asyncio.create_task(
        manager.apply_plugin_installation(
            second,
            artifact_package=second_package,
            enabled=False,
        )
    )

    second_result = await asyncio.wait_for(second_task, timeout=1)

    release_install.set()
    await asyncio.wait_for(first_task, timeout=1)
    assert second_result["state"] == "disabled"
    assert context.is_current_installation_binding(second)


async def test_identical_artifact_publication_is_deduped(
    tmp_path,
    monkeypatch,
):
    _, manager = _manager(tmp_path)
    package = _package()
    digest = hashlib.sha256(package).hexdigest()
    first = _binding("installation-a", digest, workspace_uuid="workspace-a")
    second = _binding("installation-b", digest, workspace_uuid="workspace-b")
    install_calls = 0
    original_install = manager.artifact_store.install_package

    def install_package(package, expected_digest):
        nonlocal install_calls
        install_calls += 1
        return original_install(package, expected_digest)

    monkeypatch.setattr(manager.artifact_store, "install_package", install_package)

    await asyncio.gather(
        manager.apply_plugin_installation(
            first,
            artifact_package=package,
            enabled=False,
        ),
        manager.apply_plugin_installation(
            second,
            artifact_package=package,
            enabled=False,
        ),
    )

    assert install_calls == 1


def test_runtime_health_reports_identity_free_installation_state_counts(tmp_path):
    context, manager = _manager(tmp_path)
    package = _package()
    digest = hashlib.sha256(package).hexdigest()

    for installation_uuid, state in (
        ("installation-running", "running"),
        ("installation-starting", "starting"),
        ("installation-failed", "failed"),
        ("installation-disabled", "disabled"),
    ):
        binding = _binding(installation_uuid, digest, workspace_uuid=installation_uuid)
        artifact = manager.artifact_store.install_package(package, digest)
        paths = manager.artifact_store.ensure_installation_paths(binding)
        manager._installations[binding] = manager_module.PluginInstallationRuntime(
            binding=binding,
            artifact=artifact,
            paths=paths,
            enabled=state != "disabled",
            state=state,
        )

    stats = context.get_runtime_resource_stats()

    assert stats["installation_states"] == {
        "running": 1,
        "starting": 1,
        "failed": 1,
        "disabled": 1,
        "other": 0,
    }
    assert "installation-running" not in str(stats)


def test_runtime_health_counts_unknown_installation_states(tmp_path):
    context, manager = _manager(tmp_path)
    package = _package()
    digest = hashlib.sha256(package).hexdigest()
    binding = _binding("installation-quarantined", digest, workspace_uuid="workspace-a")
    artifact = manager.artifact_store.install_package(package, digest)
    paths = manager.artifact_store.ensure_installation_paths(binding)
    manager._installations[binding] = manager_module.PluginInstallationRuntime(
        binding=binding,
        artifact=artifact,
        paths=paths,
        enabled=True,
        state="quarantined",
    )

    stats = context.get_runtime_resource_stats()

    assert stats["installation_states"]["other"] == 1
    assert stats["installation_states"]["running"] == 0


def test_runtime_health_reports_shared_pool_and_mode_split(tmp_path):
    context, manager = _manager(tmp_path)
    package = _package()
    digest = hashlib.sha256(package).hexdigest()

    for index, execution_mode in enumerate(
        (PluginExecutionMode.SHARED_CERTIFIED, PluginExecutionMode.DEDICATED)
    ):
        binding = _binding(
            f"installation-{index}", digest, workspace_uuid="workspace-a"
        )
        artifact = manager.artifact_store.install_package(package, digest)
        paths = manager.artifact_store.ensure_installation_paths(binding)
        manager._installations[binding] = manager_module.PluginInstallationRuntime(
            binding=binding,
            artifact=artifact,
            paths=paths,
            enabled=True,
            state="running",
            execution_mode=execution_mode,
        )

    worker = manager_module.SharedPluginWorkerRuntime(
        artifact=next(iter(manager._installations.values())).artifact,
        dependency_environment=None,
        paths=manager.artifact_store.ensure_shared_worker_paths(digest),
    )
    worker.ready_event.set()
    worker.draining = True
    worker.slots[next(iter(manager._installations))] = next(
        iter(manager._installations.values())
    )
    manager._shared_workers[digest] = worker
    manager.ops_metrics.shared_slot_attach_total = 3
    manager.ops_metrics.shared_capacity_rejections_total = 2

    stats = context.get_runtime_resource_stats()

    assert stats["installations_by_mode"] == {
        "shared-runtime-v1": 1,
        "dedicated": 1,
    }
    assert stats["shared_pool"]["workers"] == 1
    assert stats["shared_pool"]["ready"] == 1
    assert stats["shared_pool"]["draining"] == 1
    assert stats["shared_pool"]["slots"] == 1
    assert stats["shared_pool"]["capacity"] == 16
    assert stats["shared_pool"]["slot_attach_total"] == 3
    assert stats["shared_pool"]["capacity_rejections_total"] == 2


def test_runtime_health_prunes_expired_registrations_before_counting(tmp_path):
    context, manager = _manager(tmp_path)
    manager._pending_registrations["expired"] = (
        manager_module._PendingPluginRegistration(
            plugin_author="tester",
            plugin_name="demo",
            plugin_path="/tmp/demo",
            binding=None,
            shared_pool_digest=None,
            expires_at=time.monotonic() - 1,
        )
    )
    manager._pending_registrations["live"] = manager_module._PendingPluginRegistration(
        plugin_author="tester",
        plugin_name="demo",
        plugin_path="/tmp/demo",
        binding=None,
        shared_pool_digest=None,
        expires_at=time.monotonic() + 60,
    )

    stats = context.get_runtime_resource_stats()

    assert stats["pending_registrations"] == 1
    assert "expired" not in manager._pending_registrations


def test_runtime_health_payload_carries_no_tenant_identity(tmp_path):
    context, manager = _manager(tmp_path)
    package = _package()
    digest = hashlib.sha256(package).hexdigest()
    binding = _binding(
        "installation-secret",
        digest,
        workspace_uuid="workspace-secret",
    )
    artifact = manager.artifact_store.install_package(package, digest)
    paths = manager.artifact_store.ensure_installation_paths(binding)
    manager._installations[binding] = manager_module.PluginInstallationRuntime(
        binding=binding,
        artifact=artifact,
        paths=paths,
        enabled=True,
        state="running",
    )
    manager.dependency_environment_store.metrics.dependency_cache_hits_total = 4

    stats = context.get_runtime_resource_stats()

    serialized = str(stats)
    assert "installation-secret" not in serialized
    assert "workspace-secret" not in serialized
    assert digest not in serialized
    assert stats["dependency_environment"]["cache_hits_total"] == 4
    assert stats["restart_backoff"] == {
        "shared_current_seconds": 0.0,
        "shared_total_seconds": 0.0,
        "dedicated_current_seconds": 0.0,
        "dedicated_total_seconds": 0.0,
    }


async def test_installation_launch_failure_is_recorded_locally(
    tmp_path,
    monkeypatch,
):
    _, manager = _manager(tmp_path)
    package = _package()
    digest = hashlib.sha256(package).hexdigest()
    binding = _binding("installation-a", digest, workspace_uuid="workspace-a")
    await manager.apply_plugin_installation(
        binding,
        artifact_package=package,
        enabled=False,
    )
    runtime = manager.installation_runtimes[binding]
    runtime.enabled = True

    async def launch(_candidate):
        raise RuntimeError("worker crashed before ready")

    monkeypatch.setattr(manager, "launch_plugin_installation", launch)
    permit = await manager.restart_coordinator.acquire(binding.installation_uuid)

    try:
        with pytest.raises(RuntimeError, match="worker crashed"):
            await manager._run_installation_worker_attempt(runtime, permit)
    finally:
        await permit.abandon()

    assert runtime.state == "failed"
    assert runtime.error_code == "worker_launch_failed"
    assert "worker crashed before ready" in str(runtime.error_message)


async def test_installation_supervisor_does_not_restart_fenced_worker(
    tmp_path,
    monkeypatch,
):
    context, manager = _manager(tmp_path)
    package = _package()
    digest = hashlib.sha256(package).hexdigest()
    binding = _binding(
        "installation-a",
        digest,
        workspace_uuid="workspace-a",
    )
    await manager.apply_plugin_installation(
        binding,
        artifact_package=package,
        enabled=False,
    )
    runtime = manager.installation_runtimes[binding]
    runtime.enabled = True
    calls = 0

    async def launch(candidate):
        nonlocal calls
        calls += 1
        context.deactivate_installation_binding(candidate)

    monkeypatch.setattr(manager, "launch_plugin_installation", launch)

    manager._schedule_installation_worker(runtime)
    task = runtime.launch_task
    assert task is not None
    await task
    await asyncio.sleep(0)

    assert calls == 1
    assert runtime.launch_task is None
    assert task not in manager.plugin_run_tasks


async def test_launch_installation_builds_private_scoped_handler(
    tmp_path,
    monkeypatch,
):
    _, manager = _manager(tmp_path)
    package = _package()
    digest = hashlib.sha256(package).hexdigest()
    binding = _binding(
        "installation-a",
        digest,
        workspace_uuid="workspace-a",
    )
    await manager.apply_plugin_installation(
        binding,
        artifact_package=package,
        enabled=False,
    )
    runtime = manager.installation_runtimes[binding]
    dependency_root = tmp_path / "dependency"
    dependency_site_packages = dependency_root / "site-packages"
    dependency_site_packages.mkdir(parents=True)
    runtime.dependency_environment = PluginDependencyEnvironment(
        digest="b" * 64,
        artifact_digest=digest,
        requirements_digest="c" * 64,
        runtime_fingerprint="d" * 64,
        root_path=dependency_root,
        site_packages_path=dependency_site_packages,
    )
    runtime.enabled = True
    connection = object()
    process = object()
    captured = {}

    class FakeController:
        def __init__(self):
            self.process = process

        async def run(self, callback):
            await callback(connection)

    class FakePluginHandler:
        def __init__(self, handler_connection, context, **kwargs):
            captured["handler_connection"] = handler_connection
            captured["handler_context"] = context
            captured["handler_kwargs"] = kwargs

    def create_controller(spec):
        captured["launch_spec"] = spec
        return FakeController()

    async def add_plugin_handler(handler):
        captured["handler"] = handler

    monkeypatch.setattr(
        manager.worker_launcher,
        "create_controller",
        create_controller,
    )
    monkeypatch.setattr(
        manager_module.runtime_plugin_handler_cls,
        "PluginConnectionHandler",
        FakePluginHandler,
    )
    monkeypatch.setattr(manager, "add_plugin_handler", add_plugin_handler)

    await manager.launch_plugin_installation(binding)

    assert captured["launch_spec"].binding == binding
    assert captured["launch_spec"].dependency_environment is (
        runtime.dependency_environment
    )
    assert captured["launch_spec"].runtime_ws_url == (
        f"ws://localhost:{manager.context.ws_debug_port}/plugin/ws"
    )
    assert captured["handler_connection"] is connection
    assert captured["handler_context"] is manager.context
    assert captured["handler_kwargs"]["stdio_process"] is process
    assert captured["handler_kwargs"]["file_storage_dir"] == str(
        runtime.paths.root_path / "rpc-transfer"
    )
    assert captured["handler_kwargs"]["max_file_bytes"] == 512 * 1024 * 1024
    assert runtime.plugin_handler is captured["handler"]
    assert manager._pending_registrations == {}


async def test_stop_installation_worker_reaps_handler_process_and_task(
    tmp_path,
):
    _, manager = _manager(tmp_path)
    package = _package()
    digest = hashlib.sha256(package).hexdigest()
    binding = _binding(
        "installation-a",
        digest,
        workspace_uuid="workspace-a",
    )
    await manager.apply_plugin_installation(
        binding,
        artifact_package=package,
        enabled=False,
    )
    runtime = manager.installation_runtimes[binding]

    class FakeProcess:
        def __init__(self):
            self.returncode = None
            self.terminated = False
            self.killed = False
            self.waited = False

        def terminate(self):
            self.terminated = True

        def kill(self):
            self.killed = True
            self.returncode = -9

        async def wait(self):
            self.waited = True
            self.returncode = 0
            return self.returncode

    process = FakeProcess()
    plugin_container = object()
    handler = SimpleNamespace(
        cancel_inflight_messages=mock.Mock(),
        shutdown_plugin=mock.AsyncMock(side_effect=RuntimeError("already exited")),
        conn=SimpleNamespace(close=mock.AsyncMock()),
        stdio_process=process,
    )
    runtime.plugin_handler = handler
    runtime.plugin_container = plugin_container
    manager.plugin_handlers.append(handler)
    manager._binding_by_container_id[id(plugin_container)] = binding
    launch_task = asyncio.create_task(asyncio.Event().wait())
    runtime.launch_task = launch_task

    await manager._stop_installation_worker(runtime)

    handler.cancel_inflight_messages.assert_called_once_with()
    handler.shutdown_plugin.assert_awaited_once_with()
    handler.conn.close.assert_awaited_once_with()
    assert process.terminated is False
    assert process.killed is False
    assert process.waited is True
    assert handler not in manager.plugin_handlers
    assert id(plugin_container) not in manager._binding_by_container_id
    assert launch_task.cancelled()
    assert runtime.plugin_handler is None
    assert runtime.plugin_container is None
    assert runtime.launch_task is None


async def test_stop_installation_worker_bounds_stuck_supervisor_cleanup(
    tmp_path,
    monkeypatch,
    caplog,
):
    _, manager = _manager(tmp_path)
    package = _package()
    digest = hashlib.sha256(package).hexdigest()
    binding = _binding(
        "installation-a",
        digest,
        workspace_uuid="workspace-a",
    )
    await manager.apply_plugin_installation(
        binding,
        artifact_package=package,
        enabled=False,
    )
    runtime = manager.installation_runtimes[binding]
    release = asyncio.Event()

    async def ignore_cancellation_until_released():
        while not release.is_set():
            try:
                await release.wait()
            except asyncio.CancelledError:
                continue

    launch_task = asyncio.create_task(ignore_cancellation_until_released())
    runtime.launch_task = launch_task
    monkeypatch.setattr(manager_module, "_PLUGIN_WORKER_STOP_TIMEOUT_SEC", 0.01)
    await asyncio.sleep(0)

    await manager._stop_installation_worker(runtime)

    assert runtime.launch_task is None
    assert not launch_task.done()
    assert "Plugin installation supervisor did not stop within" in caplog.text

    release.set()
    await launch_task


@pytest.mark.parametrize(
    "lifecycle_operation",
    ["remove", "reconcile", "shutdown"],
)
async def test_installation_lifecycle_routes_allow_graceful_worker_exit(
    tmp_path,
    lifecycle_operation,
):
    _, manager = _manager(tmp_path)
    package = _package()
    digest = hashlib.sha256(package).hexdigest()
    binding = _binding(
        "installation-a",
        digest,
        workspace_uuid="workspace-a",
    )
    await manager.apply_plugin_installation(
        binding,
        artifact_package=package,
        enabled=False,
    )
    runtime = manager.installation_runtimes[binding]
    events: list[str] = []

    class GracefulProcess:
        def __init__(self):
            self.returncode = None
            self.terminate_calls = 0
            self.kill_calls = 0

        def terminate(self):
            self.terminate_calls += 1

        def kill(self):
            self.kill_calls += 1

        async def wait(self):
            events.append("wait")
            self.returncode = 0
            return self.returncode

    process = GracefulProcess()

    async def shutdown_plugin():
        events.append("shutdown")

    async def close_connection():
        events.append("close")

    handler = SimpleNamespace(
        cancel_inflight_messages=lambda: events.append("cancel"),
        shutdown_plugin=shutdown_plugin,
        conn=SimpleNamespace(close=close_connection),
        stdio_process=process,
    )
    runtime.plugin_handler = handler
    manager.plugin_handlers.append(handler)

    if lifecycle_operation == "remove":
        await manager.remove_plugin_installation(binding)
    elif lifecycle_operation == "reconcile":
        await manager.reconcile_plugin_installations(())
    else:
        await manager.shutdown_all_plugins()

    assert events == ["cancel", "shutdown", "close", "wait"]
    assert process.terminate_calls == 0
    assert process.kill_calls == 0
    assert handler not in manager.plugin_handlers
    assert runtime.plugin_handler is None


async def test_launch_installation_fails_closed_without_current_ready_runtime(
    tmp_path,
):
    context, manager = _manager(tmp_path)
    package = _package()
    digest = hashlib.sha256(package).hexdigest()
    binding = _binding(
        "installation-a",
        digest,
        workspace_uuid="workspace-a",
    )
    await manager.apply_plugin_installation(
        binding,
        artifact_package=package,
        enabled=False,
    )
    runtime = manager.installation_runtimes[binding]

    await manager.launch_plugin_installation(binding)

    runtime.enabled = True
    with pytest.raises(ValueError, match="dependency environment"):
        await manager.launch_plugin_installation(binding)

    context.deactivate_installation_binding(binding)
    with pytest.raises(ValueError, match="no longer current"):
        await manager.launch_plugin_installation(binding)
