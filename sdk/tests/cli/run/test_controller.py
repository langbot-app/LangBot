from __future__ import annotations

import asyncio
import contextlib
from typing import Any

import pytest

from langbot_plugin.api.definition.components.base import NoneComponent
from langbot_plugin.api.definition.components.runner.runner import Runner
from langbot_plugin.api.definition.components.common.event_listener import EventListener
from langbot_plugin.api.definition.components.manifest import ComponentManifest
from langbot_plugin.api.definition.components.tool.tool import Tool
from langbot_plugin.api.entities.builtin.runner.context import RunnerContext
from langbot_plugin.api.entities.builtin.runner.result import RunnerResult
from langbot_plugin.api.definition.plugin import BasePlugin, NonePlugin
from langbot_plugin.api.entities.builtin.provider import session as provider_session
from langbot_plugin.cli.run import controller as controller_module
from langbot_plugin.cli.run.controller import PluginRuntimeController
from langbot_plugin.api.proxies.langbot_api import LangBotAPIProxy
from langbot_plugin.entities.io.actions.enums import PluginToRuntimeAction
from langbot_plugin.entities.io.errors import ConnectionClosedError
from langbot_plugin.entities.io.context import InstallationBinding
from langbot_plugin.runtime.plugin.container import RuntimeContainerStatus


class DemoPlugin(BasePlugin):
    initialized = False

    async def initialize(self) -> None:
        self.initialized = True


class RevokeTrackingPlugin(BasePlugin):
    initialized = False
    fail_revoke = False

    def __init__(self) -> None:
        super().__init__()
        self.revoked: list[str] = []

    async def initialize(self) -> None:
        self.initialized = True

    async def on_installation_revoked(self, binding: InstallationBinding) -> None:
        self.revoked.append(binding.installation_uuid)
        if self.fail_revoke:
            raise RuntimeError("hook failure must not block revocation")


class DemoTool(Tool):
    initialized = False

    async def initialize(self) -> None:
        self.initialized = True

    async def call(
        self,
        params: dict[str, Any],
        session: provider_session.Session,
        query_id: int,
    ) -> str:
        return "ok"


class DemoEventListener(EventListener):
    initialized = False

    async def initialize(self) -> None:
        self.initialized = True


class DemoRunner(Runner):
    initialized = False

    @classmethod
    def get_config_schema(cls) -> list[dict[str, Any]]:
        return [{"type": "string", "name": "mode", "default": "chat"}]

    async def initialize(self) -> None:
        self.initialized = True

    async def run(self, ctx: RunnerContext):
        yield RunnerResult.run_completed(ctx.run_id)


def _manifest(kind: str, name: str, spec: dict | None = None) -> ComponentManifest:
    return ComponentManifest(
        owner="tester",
        rel_path=f"{name}.yaml",
        manifest={
            "apiVersion": "v1",
            "kind": kind,
            "metadata": {
                "name": name,
                "label": {"en_US": name.title()},
                "author": "tester",
                "version": "1.0.0",
            },
            "spec": spec or {},
            "execution": {
                "python": {"path": f"./{name}.py", "attr": name.title()},
                "sharedRuntime": "shared-runtime-v1",
                "componentModel": "stateless-v1",
            },
        },
    )


def _controller() -> PluginRuntimeController:
    return PluginRuntimeController(
        plugin_manifest=_manifest("Plugin", "demo"),
        component_manifests=[
            _manifest("Tool", "lookup"),
            _manifest("EventListener", "events"),
            _manifest("UnknownKind", "unknown"),
        ],
        stdio=True,
        ws_debug_url="ws://runtime/plugin/ws",
    )


class FakeConnection:
    def __init__(self):
        self.closed = False
        self.closed_event = asyncio.Event()

    async def send(self, message: str) -> None:
        pass

    async def receive(self) -> str:
        await asyncio.Future()

    async def close(self) -> None:
        self.closed = True
        self.closed_event.set()


class FakeHotReloader:
    instances: list["FakeHotReloader"] = []

    def __init__(self, watch_path, on_reload_callback):
        self.watch_path = watch_path
        self.on_reload_callback = on_reload_callback
        self.started = False
        self.stopped = False
        self.__class__.instances.append(self)

    def start(self):
        self.started = True

    def stop(self):
        self.stopped = True


def _fake_handler_class(*, run_forever: bool = False):
    instances = []

    class FakePluginRuntimeHandler:
        def __init__(self, connection, initialize_callback):
            self.connection = connection
            self.initialize_callback = initialize_callback
            self.disconnect_callback = None
            self.shutdown_callback = None
            self.plugin_container = None
            self.register_calls = []
            self.run_started = asyncio.Event()
            self.registered = asyncio.Event()
            self.cancelled = asyncio.Event()
            instances.append(self)

        def set_disconnect_callback(self, callback):
            self.disconnect_callback = callback

        async def run(self):
            self.run_started.set()
            if not run_forever:
                return

            try:
                await asyncio.Future()
            finally:
                self.cancelled.set()

        async def register_plugin(
            self,
            prod_mode: bool = False,
            registration_capability: str = "",
        ):
            self.register_calls.append((prod_mode, registration_capability))
            self.registered.set()
            return {"ok": True}

        async def get_plugin_container(self):
            return {
                "enabled": True,
                "priority": 7,
                "plugin_config": {"mode": "debug"},
            }

    FakePluginRuntimeHandler.instances = instances
    return FakePluginRuntimeHandler


def _install_stdio_controller(monkeypatch, *behaviors: str):
    controllers = []

    class FakeStdioServerController:
        def __init__(self):
            self.index = len(controllers)
            self.connection = FakeConnection()
            controllers.append(self)

        async def run(self, new_connection_callback):
            behavior = behaviors[self.index] if self.index < len(behaviors) else "wait"
            if behavior == "connect":
                await new_connection_callback(self.connection)
                return
            if behavior == "wait":
                await asyncio.Future()
                return
            raise AssertionError(f"Unknown fake controller behavior: {behavior}")

    monkeypatch.setattr(
        controller_module.stdio_controller_server,
        "StdioServerController",
        FakeStdioServerController,
    )
    return controllers


def _install_ws_failure_controller(monkeypatch, failure: Exception):
    controllers = []

    class FakeWebSocketClientController:
        def __init__(
            self, ws_url, make_connection_failed_callback, additional_headers=None
        ):
            self.ws_url = ws_url
            self.make_connection_failed_callback = make_connection_failed_callback
            self.additional_headers = additional_headers or {}
            controllers.append(self)

        async def run(self, new_connection_callback):
            await self.make_connection_failed_callback(self, failure)

    monkeypatch.setattr(
        controller_module.ws_controller_client,
        "WebSocketClientController",
        FakeWebSocketClientController,
    )
    return controllers


async def _wait_until(predicate, timeout: float = 1.0):
    deadline = asyncio.get_running_loop().time() + timeout
    while asyncio.get_running_loop().time() < deadline:
        if predicate():
            return
        await asyncio.sleep(0.01)
    raise AssertionError("Timed out waiting for predicate")


def _runner_controller() -> PluginRuntimeController:
    return PluginRuntimeController(
        plugin_manifest=_manifest("Plugin", "demo"),
        component_manifests=[
            _manifest("Runner", "runner", spec={"usages": ["agent"]}),
        ],
        stdio=True,
        ws_debug_url="ws://runtime/plugin/ws",
    )


def test_controller_builds_unmounted_placeholder_container():
    controller = _controller()

    assert controller._stdio is True
    assert controller.ws_debug_url == "ws://runtime/plugin/ws"
    assert controller.plugin_container.status is RuntimeContainerStatus.UNMOUNTED
    assert isinstance(controller.plugin_container.plugin_instance, NonePlugin)
    assert [
        component.manifest.kind for component in controller.plugin_container.components
    ] == [
        "Tool",
        "EventListener",
        "UnknownKind",
    ]
    assert all(
        isinstance(component.component_instance, NoneComponent)
        for component in controller.plugin_container.components
    )


@pytest.mark.asyncio
async def test_initialize_creates_plugin_and_supported_component_instances(monkeypatch):
    controller = _controller()
    controller.handler = object()
    component_classes = {
        "Plugin": DemoPlugin,
        "Tool": DemoTool,
        "EventListener": DemoEventListener,
    }

    def fake_component_class(self: ComponentManifest):
        return component_classes[self.kind]

    monkeypatch.setattr(
        ComponentManifest,
        "get_python_component_class",
        fake_component_class,
    )

    await controller.initialize(
        {
            "enabled": False,
            "priority": 42,
            "plugin_config": {"token": "secret"},
        }
    )

    plugin = controller.plugin_container.plugin_instance
    assert isinstance(plugin, DemoPlugin)
    assert plugin.initialized is True
    assert plugin.config == {"token": "secret"}
    assert plugin.plugin_runtime_handler is controller.handler
    assert controller.plugin_container.enabled is False
    assert controller.plugin_container.priority == 42
    assert controller.plugin_container.status is RuntimeContainerStatus.INITIALIZED

    tool, event_listener, unknown = controller.plugin_container.components
    assert isinstance(tool.component_instance, DemoTool)
    assert tool.component_instance.initialized is True
    assert tool.component_instance.plugin is plugin
    assert isinstance(event_listener.component_instance, DemoEventListener)
    assert event_listener.component_instance.initialized is True
    assert event_listener.component_instance.plugin is plugin
    assert isinstance(unknown.component_instance, NoneComponent)


@pytest.mark.asyncio
async def test_shared_worker_reuses_single_instances_and_scopes_config_per_invocation(
    monkeypatch,
):
    controller = _controller()
    controller.handler = object()
    component_classes = {
        "Plugin": DemoPlugin,
        "Tool": DemoTool,
        "EventListener": DemoEventListener,
    }

    def fake_component_class(self: ComponentManifest):
        return component_classes[self.kind]

    monkeypatch.setattr(
        ComponentManifest,
        "get_python_component_class",
        fake_component_class,
    )

    digest = "a" * 64
    binding_a = InstallationBinding(
        instance_uuid="instance-1",
        workspace_uuid="workspace-a",
        placement_generation=1,
        installation_uuid="installation-a",
        runtime_revision=1,
        artifact_digest=digest,
    )
    binding_b = binding_a.model_copy(
        update={"workspace_uuid": "workspace-b", "installation_uuid": "installation-b"}
    )

    await controller.initialize_slot(
        binding_a,
        {"enabled": True, "priority": 1, "plugin_config": {"tenant": "a"}},
    )
    await controller.initialize_slot(
        binding_b,
        {"enabled": True, "priority": 2, "plugin_config": {"tenant": "b"}},
    )

    slot_a = controller.plugin_container_for_slot("installation-a")
    slot_b = controller.plugin_container_for_slot("installation-b")
    assert slot_a.plugin_container is slot_b.plugin_container
    assert slot_a.plugin_container is controller.plugin_container
    assert slot_a.plugin_config == {"tenant": "a"}
    assert slot_b.plugin_config == {"tenant": "b"}
    assert controller.plugin_container.plugin_instance.initialized is True

    await controller.detach_slot("installation-a")

    assert controller.plugin_container_for_slot("installation-a") is None
    assert controller.plugin_container_for_slot("installation-b") is slot_b


def _shared_slot_controller(monkeypatch, plugin_class):
    controller = _controller()
    controller.handler = object()
    component_classes = {
        "Plugin": plugin_class,
        "Tool": DemoTool,
        "EventListener": DemoEventListener,
    }
    monkeypatch.setattr(
        ComponentManifest,
        "get_python_component_class",
        lambda self: component_classes[self.kind],
    )
    return controller


def _two_bindings() -> tuple[InstallationBinding, InstallationBinding]:
    binding_a = InstallationBinding(
        instance_uuid="instance-1",
        workspace_uuid="workspace-a",
        placement_generation=1,
        installation_uuid="installation-a",
        runtime_revision=1,
        artifact_digest="a" * 64,
    )
    binding_b = binding_a.model_copy(
        update={"workspace_uuid": "workspace-b", "installation_uuid": "installation-b"}
    )
    return binding_a, binding_b


@pytest.mark.asyncio
async def test_detach_slot_notifies_only_the_revoked_installation(monkeypatch):
    controller = _shared_slot_controller(monkeypatch, RevokeTrackingPlugin)
    binding_a, binding_b = _two_bindings()

    await controller.initialize_slot(
        binding_a, {"enabled": True, "priority": 1, "plugin_config": {}}
    )
    await controller.initialize_slot(
        binding_b, {"enabled": True, "priority": 2, "plugin_config": {}}
    )

    plugin = controller.plugin_container.plugin_instance
    assert plugin.revoked == []

    await controller.detach_slot("installation-a")
    assert plugin.revoked == ["installation-a"]
    # The sibling slot keeps its state: one graph serves every installation.
    assert controller.plugin_container_for_slot("installation-b") is not None

    await controller.detach_slot("installation-b")
    assert plugin.revoked == ["installation-a", "installation-b"]


@pytest.mark.asyncio
async def test_revoke_hook_failure_does_not_block_slot_detach(monkeypatch):
    controller = _shared_slot_controller(monkeypatch, RevokeTrackingPlugin)
    binding_a, _ = _two_bindings()

    await controller.initialize_slot(
        binding_a, {"enabled": True, "priority": 1, "plugin_config": {}}
    )
    plugin = controller.plugin_container.plugin_instance
    plugin.fail_revoke = True

    await controller.detach_slot("installation-a")

    assert controller.plugin_container_for_slot("installation-a") is None


@pytest.mark.asyncio
async def test_legacy_manifest_cannot_enter_shared_slot_mode():
    manifest = _manifest("Plugin", "legacy")
    manifest.manifest["execution"].pop("sharedRuntime")
    manifest.manifest["execution"].pop("componentModel")
    # Rebuild through the public model so the manifest has dedicated semantics.
    manifest = ComponentManifest(
        owner=manifest.owner,
        manifest=manifest.manifest,
        rel_path=manifest.rel_path,
    )
    controller = PluginRuntimeController(
        plugin_manifest=manifest,
        component_manifests=[],
        stdio=True,
        ws_debug_url="ws://runtime/plugin/ws",
    )
    binding = InstallationBinding(
        instance_uuid="instance-1",
        workspace_uuid="workspace-a",
        placement_generation=1,
        installation_uuid="installation-a",
        runtime_revision=1,
        artifact_digest="a" * 64,
    )

    with pytest.raises(ValueError, match="stateless-v1"):
        await controller.initialize_slot(
            binding,
            {"enabled": True, "priority": 0, "plugin_config": {}},
        )


def test_nested_config_snapshot_thaws_to_json_safe_values():
    from langbot_plugin.api.proxies.invocation import freeze_config, thaw_config

    frozen = freeze_config(
        {"nested": {"token": "secret"}, "items": [{"enabled": True}]}
    )

    assert thaw_config(frozen) == {
        "nested": {"token": "secret"},
        "items": [{"enabled": True}],
    }


@pytest.mark.asyncio
async def test_shared_invocations_use_task_local_config_on_single_plugin_instance(
    monkeypatch,
):
    controller = _controller()
    component_classes = {
        "Plugin": DemoPlugin,
        "Tool": DemoTool,
        "EventListener": DemoEventListener,
    }
    monkeypatch.setattr(
        ComponentManifest,
        "get_python_component_class",
        lambda self: component_classes[self.kind],
    )
    digest = "a" * 64
    binding_a = InstallationBinding(
        instance_uuid="instance-1",
        workspace_uuid="workspace-a",
        placement_generation=1,
        installation_uuid="installation-a",
        runtime_revision=1,
        artifact_digest=digest,
    )
    binding_b = binding_a.model_copy(
        update={"workspace_uuid": "workspace-b", "installation_uuid": "installation-b"}
    )
    controller.handler = type("HandlerIdentity", (), {})()
    await controller.initialize_slot(
        binding_a,
        {"enabled": True, "priority": 1, "plugin_config": {"tenant": "a"}},
    )
    await controller.initialize_slot(
        binding_b,
        {"enabled": True, "priority": 2, "plugin_config": {"tenant": "b"}},
    )
    plugin = controller.plugin_container.plugin_instance

    async def observe(binding):
        slot = controller.plugin_container_for_slot(binding.installation_uuid)
        assert slot is not None
        from langbot_plugin.api.proxies.invocation import bind_invocation

        with bind_invocation(
            controller.handler,
            config=slot.plugin_config,
            binding=binding,
        ):
            await asyncio.sleep(0)
            return plugin.get_config(), plugin.get_installation_binding(), id(plugin)

    result_a, result_b = await asyncio.gather(observe(binding_a), observe(binding_b))

    assert result_a == ({"tenant": "a"}, binding_a, id(plugin))
    assert result_b == ({"tenant": "b"}, binding_b, id(plugin))


@pytest.mark.asyncio
async def test_shared_config_revision_replaces_snapshot_without_reinitializing_objects(
    monkeypatch,
):
    controller = _controller()
    controller.handler = object()
    initialized = 0

    class CountedPlugin(BasePlugin):
        async def initialize(self):
            nonlocal initialized
            initialized += 1

    component_classes = {
        "Plugin": CountedPlugin,
        "Tool": DemoTool,
        "EventListener": DemoEventListener,
    }
    monkeypatch.setattr(
        ComponentManifest,
        "get_python_component_class",
        lambda self: component_classes[self.kind],
    )
    binding = InstallationBinding(
        instance_uuid="instance-1",
        workspace_uuid="workspace-a",
        placement_generation=1,
        installation_uuid="installation-a",
        runtime_revision=1,
        artifact_digest="a" * 64,
    )
    first = await controller.initialize_slot(
        binding,
        {"enabled": True, "priority": 1, "plugin_config": {"revision": 1}},
    )
    plugin_id = id(controller.plugin_container.plugin_instance)
    component_ids = [
        id(item.component_instance) for item in controller.plugin_container.components
    ]
    second_binding = binding.model_copy(update={"runtime_revision": 2})
    second = await controller.initialize_slot(
        second_binding,
        {"enabled": True, "priority": 1, "plugin_config": {"revision": 2}},
    )

    assert initialized == 1
    assert first.plugin_container is second.plugin_container
    assert id(controller.plugin_container.plugin_instance) == plugin_id
    assert [
        id(item.component_instance) for item in controller.plugin_container.components
    ] == component_ids
    assert dict(second.plugin_config) == {"revision": 2}


@pytest.mark.asyncio
async def test_shared_slot_proxy_scopes_all_file_helpers_and_knowledge_downloads():
    digest = "a" * 64
    binding_a = InstallationBinding(
        instance_uuid="instance-1",
        workspace_uuid="workspace-a",
        placement_generation=1,
        installation_uuid="installation-a",
        runtime_revision=1,
        artifact_digest=digest,
    )
    binding_b = binding_a.model_copy(
        update={
            "workspace_uuid": "workspace-b",
            "installation_uuid": "installation-b",
        }
    )

    class NamespacedHandler:
        def __init__(self):
            self.files = {(binding_a, "knowledge-key"): b"workspace-a knowledge"}
            self.deleted = []
            self.sent_contexts = []

        async def call_action(self, action, data, timeout=15.0, *, action_context):
            assert action is PluginToRuntimeAction.GET_KNOWLEDEGE_FILE_STREAM
            assert data == {"storage_path": "knowledge/path"}
            assert action_context in {binding_a, binding_b}
            return {"file_key": "knowledge-key"}

        async def read_local_file(self, file_key, *, action_context):
            return self.files[(action_context, file_key)]

        async def delete_local_file(self, file_key, *, action_context):
            self.deleted.append((action_context, file_key))
            self.files.pop((action_context, file_key), None)

        async def send_file(self, file_bytes, file_extension, *, action_context):
            self.sent_contexts.append(action_context)
            return "sent-key"

    handler = NamespacedHandler()
    proxy_a = controller_module._SlotHandlerProxy(handler, binding_a)
    proxy_b = controller_module._SlotHandlerProxy(handler, binding_b)

    assert (
        await LangBotAPIProxy(proxy_a).get_knowledge_file_stream("knowledge/path")
        == b"workspace-a knowledge"
    )
    assert handler.deleted == [(binding_a, "knowledge-key")]
    assert await proxy_a.send_file(b"payload", "bin") == "sent-key"
    assert handler.sent_contexts == [binding_a]

    with pytest.raises(KeyError):
        await proxy_b.read_local_file("knowledge-key")
    assert handler.deleted == [(binding_a, "knowledge-key")]


@pytest.mark.asyncio
async def test_shared_worker_overlapping_attaches_initialize_single_object_graph(
    monkeypatch,
):
    controller = _controller()
    controller.handler = object()
    initialize_started = asyncio.Event()
    release = asyncio.Event()
    initialize_count = 0

    class BarrierPlugin(BasePlugin):
        async def initialize(self) -> None:
            nonlocal initialize_count
            initialize_count += 1
            initialize_started.set()
            await release.wait()

    component_classes = {
        "Plugin": BarrierPlugin,
        "Tool": DemoTool,
        "EventListener": DemoEventListener,
    }

    monkeypatch.setattr(
        ComponentManifest,
        "get_python_component_class",
        lambda self: component_classes[self.kind],
    )
    digest = "a" * 64
    binding_a = InstallationBinding(
        instance_uuid="instance-1",
        workspace_uuid="workspace-a",
        placement_generation=1,
        installation_uuid="installation-a",
        runtime_revision=1,
        artifact_digest=digest,
    )
    binding_b = binding_a.model_copy(
        update={
            "workspace_uuid": "workspace-b",
            "installation_uuid": "installation-b",
        }
    )

    tasks = [
        asyncio.create_task(
            controller.initialize_slot(
                binding_a,
                {"enabled": True, "priority": 1, "plugin_config": {"tenant": "a"}},
            )
        ),
        asyncio.create_task(
            controller.initialize_slot(
                binding_b,
                {"enabled": True, "priority": 2, "plugin_config": {"tenant": "b"}},
            )
        ),
    ]
    await asyncio.wait_for(initialize_started.wait(), timeout=1)
    release.set()
    slot_a, slot_b = await asyncio.gather(*tasks)

    assert initialize_count == 1
    assert slot_b is controller.plugin_container_for_slot("installation-b")
    assert slot_a.plugin_container is slot_b.plugin_container
    assert slot_a.plugin_container is controller.plugin_container
    assert slot_a.plugin_config == {"tenant": "a"}
    assert slot_b.plugin_config == {"tenant": "b"}
    assert slot_a.binding == binding_a
    assert slot_b.binding == binding_b


@pytest.mark.asyncio
async def test_initialize_writes_runner_class_declarations_to_manifest(
    monkeypatch,
):
    controller = _runner_controller()
    controller.handler = object()
    component_classes = {
        "Plugin": DemoPlugin,
        "Runner": DemoRunner,
    }

    def fake_component_class(self: ComponentManifest):
        return component_classes[self.kind]

    monkeypatch.setattr(
        ComponentManifest,
        "get_python_component_class",
        fake_component_class,
    )

    await controller.initialize(
        {"enabled": True, "priority": 0, "plugin_config": {"token": "secret"}}
    )

    runner = controller.plugin_container.components[0]
    spec = runner.manifest.spec

    assert isinstance(runner.component_instance, DemoRunner)
    assert runner.component_instance.initialized is True
    assert runner.component_instance.plugin_identity == "tester/demo"
    assert runner.component_instance.get_plugin_config() == {"token": "secret"}
    assert spec["config"] == [{"type": "string", "name": "mode", "default": "chat"}]
    assert runner.manifest.manifest["spec"] is spec


@pytest.mark.asyncio
async def test_cleanup_instances_resets_runtime_objects(monkeypatch):
    controller = _controller()
    controller.handler = object()

    component_classes = {
        "Plugin": DemoPlugin,
        "Tool": DemoTool,
        "EventListener": DemoEventListener,
    }

    def fake_component_class(self: ComponentManifest):
        return component_classes[self.kind]

    monkeypatch.setattr(
        ComponentManifest,
        "get_python_component_class",
        fake_component_class,
    )

    await controller.initialize({"enabled": True, "priority": 0, "plugin_config": {}})
    await controller.cleanup_instances()

    assert isinstance(controller.plugin_container.plugin_instance, NonePlugin)
    assert controller.plugin_container.status is RuntimeContainerStatus.UNMOUNTED
    assert all(
        isinstance(component.component_instance, NoneComponent)
        for component in controller.plugin_container.components
    )


@pytest.mark.asyncio
async def test_mount_stdio_prod_registers_plugin(monkeypatch):
    capability = "registration-capability-that-is-long-enough-for-tests"
    monkeypatch.setenv("LANGBOT_PLUGIN_REGISTRATION_CAPABILITY", capability)
    fake_handler_cls = _fake_handler_class()
    monkeypatch.setattr(controller_module, "PluginRuntimeHandler", fake_handler_cls)
    controllers = _install_stdio_controller(monkeypatch, "connect")
    controller = PluginRuntimeController(
        plugin_manifest=_manifest("Plugin", "demo"),
        component_manifests=[],
        stdio=True,
        ws_debug_url="ws://runtime/plugin/ws",
        prod_mode=True,
    )

    await controller.mount()

    assert len(controllers) == 1
    handler = fake_handler_cls.instances[0]
    assert handler.plugin_container is controller.plugin_container
    assert handler.register_calls == [(True, capability)]
    assert controller._registration_capability == ""
    assert controller.plugin_container.status is RuntimeContainerStatus.MOUNTED


@pytest.mark.asyncio
async def test_mount_stdio_prod_keeps_serving_after_registration(monkeypatch):
    capability = "registration-capability-that-is-long-enough-for-tests"
    monkeypatch.setenv("LANGBOT_PLUGIN_REGISTRATION_CAPABILITY", capability)
    fake_handler_cls = _fake_handler_class(run_forever=True)
    monkeypatch.setattr(controller_module, "PluginRuntimeHandler", fake_handler_cls)
    _install_stdio_controller(monkeypatch, "connect")
    controller = PluginRuntimeController(
        plugin_manifest=_manifest("Plugin", "demo"),
        component_manifests=[],
        stdio=True,
        ws_debug_url="ws://runtime/plugin/ws",
        prod_mode=True,
    )

    mount_task = asyncio.create_task(controller.mount())
    handler = None
    try:
        await _wait_until(lambda: bool(getattr(fake_handler_cls, "instances")))
        handler = getattr(fake_handler_cls, "instances")[0]
        await handler.registered.wait()
        await asyncio.sleep(0)
        assert not mount_task.done()
    finally:
        mount_task.cancel()
        await asyncio.gather(mount_task, return_exceptions=True)

    assert handler is not None
    assert handler.cancelled.is_set()


@pytest.mark.asyncio
async def test_mount_prod_connection_failure_sets_waiter_and_exits(monkeypatch):
    capability = "registration-capability-that-is-long-enough-for-tests"
    monkeypatch.setenv("LANGBOT_PLUGIN_REGISTRATION_CAPABILITY", capability)
    controller = PluginRuntimeController(
        plugin_manifest=_manifest("Plugin", "demo"),
        component_manifests=[],
        stdio=False,
        ws_debug_url="ws://runtime/plugin/ws",
        prod_mode=True,
    )
    controllers = _install_ws_failure_controller(monkeypatch, RuntimeError("boom"))
    exit_calls = []

    def fake_exit(code):
        exit_calls.append(code)

    monkeypatch.setattr(controller_module, "exit", fake_exit, raising=False)

    with pytest.raises(ConnectionClosedError, match="Connection failed: boom"):
        await controller.mount()

    assert controllers[0].ws_url == "ws://runtime/plugin/ws"
    assert controllers[0].additional_headers == {
        "X-LangBot-Plugin-Registration-Capability": capability
    }
    assert exit_calls == [1]
    assert controller._connection_waiter.done()


@pytest.mark.asyncio
async def test_mount_debug_connection_failure_sets_waiter_exception_without_exit(
    monkeypatch,
):
    monkeypatch.setenv("PLUGIN_DEBUG_KEY", "test-debug-key-which-is-at-least-32-chars")

    class StopMount(Exception):
        pass

    controller = PluginRuntimeController(
        plugin_manifest=_manifest("Plugin", "demo"),
        component_manifests=[],
        stdio=False,
        ws_debug_url="ws://runtime/plugin/ws",
        prod_mode=False,
    )
    FakeHotReloader.instances = []
    monkeypatch.setattr(controller_module, "HotReloader", FakeHotReloader)
    _install_ws_failure_controller(monkeypatch, RuntimeError("boom"))

    def fail_exit(code):
        raise AssertionError(f"debug mode should not exit with {code}")

    async def stop_on_retry(delay):
        assert delay == 3
        raise StopMount

    monkeypatch.setattr(controller_module, "exit", fail_exit, raising=False)
    monkeypatch.setattr(controller_module.asyncio, "sleep", stop_on_retry)

    with pytest.raises(StopMount):
        await controller.mount()

    assert controller._connection_waiter.done()
    with pytest.raises(ConnectionClosedError, match="Connection failed: boom"):
        controller._connection_waiter.result()
    assert FakeHotReloader.instances[0].started is True
    assert FakeHotReloader.instances[0].stopped is True


@pytest.mark.asyncio
async def test_mount_debug_shutdown_callback_closes_connection_and_reconnects(
    monkeypatch,
):
    fake_handler_cls = _fake_handler_class(run_forever=True)
    monkeypatch.setattr(controller_module, "PluginRuntimeHandler", fake_handler_cls)
    FakeHotReloader.instances = []
    monkeypatch.setattr(controller_module, "HotReloader", FakeHotReloader)
    controllers = _install_stdio_controller(monkeypatch, "connect", "wait")
    controller = _controller()

    mount_task = asyncio.create_task(controller.mount())
    await _wait_until(lambda: len(fake_handler_cls.instances) == 1)
    handler = fake_handler_cls.instances[0]
    await asyncio.wait_for(handler.registered.wait(), timeout=1)

    assert handler.shutdown_callback is not None
    await handler.shutdown_callback()

    await asyncio.wait_for(controllers[0].connection.closed_event.wait(), timeout=1)
    await asyncio.wait_for(handler.cancelled.wait(), timeout=1)
    await _wait_until(
        lambda: controller.plugin_container.status is RuntimeContainerStatus.UNMOUNTED
    )

    mount_task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await mount_task
    if hasattr(controller, "_controller_task"):
        controller._controller_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await controller._controller_task

    assert len(controllers) == 2
    assert FakeHotReloader.instances[0].started is True
    assert FakeHotReloader.instances[0].stopped is True


@pytest.mark.asyncio
async def test_mount_hot_reload_callback_reinitializes_current_settings(
    monkeypatch,
    tmp_path,
):
    controller = _controller()
    controller.handler = _fake_handler_class()(
        FakeConnection(),
        controller.initialize,
    )
    cleanup_calls = []
    initialize_calls = []
    reload_calls = []
    FakeHotReloader.instances = []

    async def fake_cleanup():
        cleanup_calls.append(True)

    async def fake_initialize(plugin_settings):
        initialize_calls.append(plugin_settings)

    def fake_reload_plugin_modules(path):
        reload_calls.append(path)

    monkeypatch.setattr(controller, "cleanup_instances", fake_cleanup)
    monkeypatch.setattr(controller, "initialize", fake_initialize)
    monkeypatch.setattr(
        controller_module, "reload_plugin_modules", fake_reload_plugin_modules
    )
    monkeypatch.setattr(controller_module.os, "getcwd", lambda: str(tmp_path))
    monkeypatch.setattr(controller_module, "HotReloader", FakeHotReloader)
    _install_stdio_controller(monkeypatch, "wait")

    mount_task = asyncio.create_task(controller.mount())
    await _wait_until(lambda: len(FakeHotReloader.instances) == 1)

    await FakeHotReloader.instances[0].on_reload_callback()

    assert cleanup_calls == [True]
    assert reload_calls == [str(tmp_path)]
    assert initialize_calls == [
        {
            "enabled": True,
            "priority": 7,
            "plugin_config": {"mode": "debug"},
        }
    ]

    mount_task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await mount_task
    controller._controller_task.cancel()
    with contextlib.suppress(asyncio.CancelledError):
        await controller._controller_task
    assert FakeHotReloader.instances[0].stopped is True


@pytest.mark.asyncio
async def test_reload_and_reinitialize_cleans_instances_and_reloads_cwd(
    monkeypatch,
    tmp_path,
):
    controller = _controller()
    controller.plugin_container.plugin_instance = DemoPlugin()
    controller.plugin_container.components[0].component_instance = DemoTool()
    controller.plugin_container.status = RuntimeContainerStatus.INITIALIZED
    reload_calls = []

    monkeypatch.setattr(controller_module.os, "getcwd", lambda: str(tmp_path))
    monkeypatch.setattr(
        controller_module,
        "reload_plugin_modules",
        lambda path: reload_calls.append(path),
    )

    await controller.reload_and_reinitialize()

    assert reload_calls == [str(tmp_path)]
    assert isinstance(controller.plugin_container.plugin_instance, NonePlugin)
    assert controller.plugin_container.status is RuntimeContainerStatus.UNMOUNTED
    assert all(
        isinstance(component.component_instance, NoneComponent)
        for component in controller.plugin_container.components
    )
