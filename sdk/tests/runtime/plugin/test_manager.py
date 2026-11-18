from __future__ import annotations

import asyncio
import io
import os
import zipfile
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock

import pytest

from langbot_plugin.api.definition.components.base import NoneComponent
from langbot_plugin.api.definition.components.manifest import ComponentManifest
from langbot_plugin.api.definition.plugin import NonePlugin
from langbot_plugin.api.entities.builtin.runner.result import RunnerResult
from langbot_plugin.api.entities.builtin.command.context import CommandReturn
from langbot_plugin.api.entities.builtin.provider.message import Message
from langbot_plugin.api.entities.context import EventContext
from langbot_plugin.api.entities.builtin.platform import message as platform_message
from langbot_plugin.api.entities.events import (
    PersonCommandSent,
    PersonNormalMessageReceived,
)
from langbot_plugin.runtime.helper import marketplace as marketplace_helper
from langbot_plugin.runtime.plugin.container import (
    ComponentContainer,
    PluginContainer,
    RuntimeContainerStatus,
)
from langbot_plugin.runtime.plugin import mgr as manager_module
from langbot_plugin.runtime.plugin.mgr import PluginInstallSource, PluginManager
from langbot_plugin.entities.io.actions.enums import RuntimeToLangBotAction
from langbot_plugin.entities.io.errors import (
    DependencyInstallError,
    DependencyVerificationError,
)
from langbot_plugin.entities.io.context import ActionContext, InstallationBinding
from langbot_plugin.runtime.context import RuntimeContext
from langbot_plugin.runtime.security import PLUGIN_REGISTRATION_CAPABILITY_ENV


def _manifest(
    kind: str = "Plugin",
    name: str = "demo",
    author: str = "tester",
    spec: dict[str, Any] | None = None,
) -> ComponentManifest:
    return ComponentManifest(
        owner=author,
        rel_path=f"{name}.yaml",
        manifest={
            "apiVersion": "v1",
            "kind": kind,
            "metadata": {
                "name": name,
                "label": {"en_US": name.title()},
                "author": author,
                "version": "1.0.0",
            },
            "spec": spec or {},
        },
    )


def _component(kind: str, name: str, spec: dict[str, Any] | None = None):
    return ComponentContainer(
        manifest=_manifest(kind=kind, name=name, spec=spec),
        component_instance=NoneComponent(),
        component_config={},
    )


def _plugin(
    name: str = "demo",
    author: str = "tester",
    *,
    components: list[ComponentContainer] | None = None,
    status: RuntimeContainerStatus = RuntimeContainerStatus.INITIALIZED,
    enabled: bool = True,
    debug: bool = False,
) -> PluginContainer:
    return PluginContainer(
        debug=debug,
        install_source="local",
        install_info={},
        manifest=_manifest(name=name, author=author),
        plugin_instance=NonePlugin(),
        enabled=enabled,
        priority=0,
        plugin_config={},
        status=status,
        components=components or [],
    )


def _manager() -> PluginManager:
    manager = PluginManager(SimpleNamespace(ws_debug_port=18080))
    manager.plugins = []
    manager.plugin_handlers = []
    manager.plugin_run_tasks = []
    return manager


def _registration_capability(
    manager: PluginManager,
    plugin: PluginContainer,
) -> str:
    return manager._issue_registration_capability(
        plugin_author=str(plugin.manifest.metadata.author),
        plugin_name=plugin.manifest.metadata.name,
        plugin_path=f"/tmp/{plugin.manifest.metadata.author}__{plugin.manifest.metadata.name}",
    )


def _write_installed_plugin(
    root,
    *,
    author: str = "tester",
    name: str = "demo",
):
    plugin_path = root / f"{author}__{name}"
    plugin_path.mkdir()
    (plugin_path / "manifest.yaml").write_text(
        f"""
apiVersion: v1
kind: Plugin
metadata:
  author: {author}
  name: {name}
spec: {{}}
""",
        encoding="utf-8",
    )
    return plugin_path


def _bound_runtime_context(
    control_handler: FakeControlHandler | None = None,
) -> RuntimeContext:
    context = RuntimeContext()
    context.ws_debug_port = 18080
    if control_handler is not None:
        context.control_handler = control_handler
    context.bind_workspace(
        ActionContext(
            instance_uuid="instance-1",
            workspace_uuid="workspace-a",
            placement_generation=9,
        )
    )
    return context


def _plugin_zip(author: str = "tester", name: str = "demo", version: str = "1.0.0"):
    manifest = f"""
apiVersion: v1
kind: Plugin
metadata:
  name: {name}
  label:
    en_US: Demo
  author: {author}
  version: {version}
spec: {{}}
"""
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("manifest.yaml", manifest)
        archive.writestr("main.py", "")
    return buffer.getvalue()


@pytest.mark.asyncio
async def test_launch_plugin_uses_sanitized_environment(monkeypatch, tmp_path):
    from langbot_plugin.runtime.plugin import mgr as mgr_module

    captured: dict[str, Any] = {}

    class FakeStdioClientController:
        process = None

        def __init__(self, command, args, env, working_dir, *, capture_stderr=False):
            captured["capture_stderr"] = capture_stderr
            captured["command"] = command
            captured["args"] = args
            captured["env"] = env
            captured["working_dir"] = working_dir

        async def run(self, new_connection_callback):
            raise asyncio.CancelledError()

    monkeypatch.setenv("PYTHONPATH", "/tmp/langbot-plugin-sdk/src")
    monkeypatch.setattr(mgr_module, "get_platform", lambda: "linux")
    monkeypatch.setattr(
        mgr_module.pkgmgr_helper,
        "get_plugin_site_packages",
        lambda _plugin_path: "/tmp/plugin-dependencies",
    )
    monkeypatch.setattr(
        mgr_module.stdio_client_controller,
        "StdioClientController",
        FakeStdioClientController,
    )

    plugin_path = _write_installed_plugin(tmp_path)
    manager = _manager()
    await manager.launch_plugin(str(plugin_path))

    assert captured["working_dir"] == str(plugin_path)
    # Plugin logs page reads the captured stderr stream.
    assert captured["capture_stderr"] is True
    assert captured["env"] is not os.environ
    assert captured["env"]["PYTHONPATH"] == os.pathsep.join(
        (
            str(manager.worker_launcher.runtime_import_root),
            "/tmp/plugin-dependencies",
        )
    )
    assert "/tmp/langbot-plugin-sdk/src" not in captured["env"]["PYTHONPATH"]
    assert captured["env"][PLUGIN_REGISTRATION_CAPABILITY_ENV]


class FakeControlHandler:
    def __init__(self):
        self.calls: list[tuple[Any, dict[str, Any]]] = []
        self.contexts: list[ActionContext | None] = []

    async def call_action(self, action, payload, *, action_context=None):
        self.calls.append((action, payload))
        self.contexts.append(action_context)
        return {
            "enabled": True,
            "priority": 7,
            "plugin_config": {"api_key": "secret"},
            "install_source": PluginInstallSource.MARKETPLACE.value,
            "install_info": {"plugin_version": "1.0.0"},
            "installation_uuid": "installation-1",
        }


class FakeConnection:
    closed = False

    async def close(self):
        self.closed = True


class FakeLogBuffer:
    has_active_reader = False

    def __init__(self):
        self.entries = []

    def add_entry(self, level, text):
        self.entries.append((level, text))

    def get_logs(self, limit=200, level=None):
        return [{"limit": limit, "level": level, "text": "ready"}]


class FakeHandler:
    def __init__(self, plugin: PluginContainer):
        self.plugin = plugin
        self.debug_plugin = False
        self.conn = FakeConnection()
        self.stdio_process = None
        self.initialized_with = None
        self.shutdown_calls = 0
        self.diagnostics = []
        self.log_buffer = FakeLogBuffer()
        self.agent_run_calls: list[tuple[Any, dict[str, Any], float]] = []
        self.bound_action_context = None
        self.files = {
            "icon-key": b"<svg/>",
            "readme-key": b"# Demo",
            "asset-key": b"asset-bytes",
        }

    def bind_action_context(self, action_context):
        self.bound_action_context = action_context
        return action_context

    async def initialize_plugin(self, plugin_settings):
        self.initialized_with = plugin_settings

    async def get_plugin_container(self):
        refreshed = self.plugin.model_dump()
        refreshed["status"] = RuntimeContainerStatus.INITIALIZED.value
        return refreshed

    async def shutdown_plugin(self):
        self.shutdown_calls += 1

    async def notify_plugin_diagnostic(self, diagnostic):
        self.diagnostics.append(diagnostic)
        return {"ok": True}

    async def emit_event(self, event_context):
        return {"emitted": True, "event_context": event_context}

    async def call_tool(
        self,
        tool_name,
        tool_parameters,
        session,
        query_id,
        query_uuid=None,
    ):
        query_ref = {"query_id": query_id}
        if query_uuid is not None:
            query_ref["query_uuid"] = query_uuid
        return {
            "tool_response": {
                "tool_name": tool_name,
                "params": tool_parameters,
                **query_ref,
            }
        }

    async def execute_command(self, command_context):
        yield {"command_response": {"text": command_context["command"]}}

    async def call_action_generator(self, action, data, timeout=300):
        self.agent_run_calls.append((action, data, timeout))
        run_id = data["context"]["run_id"]
        yield RunnerResult.message_completed(
            run_id=run_id,
            message=Message(role="assistant", content="toy runner ok"),
        ).model_dump(mode="json")
        yield RunnerResult.run_completed(
            run_id=run_id,
            finish_reason="stop",
        ).model_dump(mode="json")

    async def get_plugin_icon(self):
        return {"plugin_icon_file_key": "icon-key", "mime_type": "image/svg+xml"}

    async def get_plugin_readme(self, language="en"):
        return {"plugin_readme_file_key": "readme-key", "language": language}

    async def get_plugin_assets_file(self, file_key):
        if file_key == "missing":
            return {"file_file_key": "", "mime_type": ""}
        return {"file_file_key": "asset-key", "mime_type": "text/plain"}

    async def read_local_file(self, file_key):
        return self.files[file_key]

    async def delete_local_file(self, file_key):
        del self.files[file_key]

    async def call_page_api(self, page_id, endpoint, method, body):
        return {
            "data": {
                "page_id": page_id,
                "endpoint": endpoint,
                "method": method,
                "body": body,
            },
            "error": None,
        }

    async def get_rag_capabilities(self):
        return {"capabilities": ["ingest", "retrieve"]}

    async def retrieve_knowledge(self, retriever_name, retrieval_context):
        return {
            "retriever_name": retriever_name,
            "retrieval_context": retrieval_context,
        }

    async def rag_ingest_document(self, context_data):
        return {"ingested": context_data["document_id"]}

    async def rag_delete_document(self, kb_id, document_id):
        return {"deleted": [kb_id, document_id]}

    async def rag_on_kb_create(self, kb_id, config):
        return {"created": kb_id, "config": config}

    async def rag_on_kb_delete(self, kb_id):
        return {"deleted_kb": kb_id}

    async def parse_document(self, context_data, file_bytes):
        return {"context": context_data, "text": file_bytes.decode()}


class ReplyChangingFakeHandler(FakeHandler):
    async def emit_event(self, event_context):
        event_context["event"]["reply_message_chain"] = [
            {"type": "Plain", "text": "plugin reply"}
        ]
        return {"emitted": True, "event_context": event_context}


class DefaultPreventingFakeHandler(FakeHandler):
    async def emit_event(self, event_context):
        event_context["is_prevent_default"] = True
        return {"emitted": True, "event_context": event_context}


class QueryUuidChangingFakeHandler(FakeHandler):
    async def emit_event(self, event_context):
        event_context["query_uuid"] = "query-forged"
        event_context["event"]["query_uuid"] = "query-forged"
        return {"emitted": True, "event_context": event_context}


class QueryUuidDroppingFakeHandler(FakeHandler):
    async def emit_event(self, event_context):
        event_context.pop("query_uuid", None)
        event_context["event"].pop("query_uuid", None)
        return {"emitted": True, "event_context": event_context}


def test_plugin_manager_instances_should_not_share_plugin_state():
    PluginManager.plugins = []
    first = PluginManager(SimpleNamespace())
    second = PluginManager(SimpleNamespace())

    first.plugins.append(_plugin())

    assert second.plugins == []


@pytest.mark.asyncio
async def test_launch_plugin_passes_registration_capability_not_debug_key(
    monkeypatch, tmp_path
):
    captured: dict[str, Any] = {}

    class FakeStdioController:
        process = None

        def __init__(self, command, args, env, working_dir, **_kwargs):
            captured.update(
                command=command,
                args=args,
                env=env,
                working_dir=working_dir,
            )

        async def run(self, _callback):
            return None

    monkeypatch.setattr(manager_module, "get_platform", lambda: "linux")
    monkeypatch.setattr(
        manager_module.stdio_client_controller,
        "StdioClientController",
        FakeStdioController,
    )
    plugin_path = _write_installed_plugin(tmp_path)
    await _manager().launch_plugin(str(plugin_path))

    assert "--plugin-debug-key" not in captured["args"]
    assert "PLUGIN_DEBUG_KEY" not in captured["env"]
    capability = captured["env"]["LANGBOT_PLUGIN_REGISTRATION_CAPABILITY"]
    assert len(capability) >= 32


@pytest.mark.asyncio
async def test_windows_launch_uses_minimal_env_and_fences_runtime_url(
    monkeypatch, tmp_path
):
    captured: dict[str, Any] = {}

    class FakeProcess:
        async def wait(self):
            return 0

    async def fake_create_subprocess_exec(*args, **kwargs):
        captured.update(args=args, kwargs=kwargs)
        return FakeProcess()

    monkeypatch.setattr(manager_module, "get_platform", lambda: "win32")
    monkeypatch.setattr(
        manager_module.asyncio,
        "create_subprocess_exec",
        fake_create_subprocess_exec,
    )
    monkeypatch.setenv("RUNTIME_WS_URL", "ws://untrusted.example/plugin/ws")
    monkeypatch.setenv("LANGBOT_PLUGIN_RUNTIME_CONTROL_TOKEN", "runtime-secret")
    monkeypatch.setenv("LANGBOT_BOX_CONTROL_TOKEN", "box-secret")
    monkeypatch.setenv("UNRELATED_SECRET", "also-secret")

    plugin_path = _write_installed_plugin(tmp_path)
    await _manager().launch_plugin(str(plugin_path))

    assert "--plugin-debug-key" not in captured["args"]
    child_env = captured["kwargs"]["env"]
    assert "PLUGIN_DEBUG_KEY" not in child_env
    assert "LANGBOT_PLUGIN_RUNTIME_CONTROL_TOKEN" not in child_env
    assert "LANGBOT_BOX_CONTROL_TOKEN" not in child_env
    assert "UNRELATED_SECRET" not in child_env
    assert len(child_env["LANGBOT_PLUGIN_REGISTRATION_CAPABILITY"]) >= 32
    assert child_env["RUNTIME_WS_URL"] == "ws://localhost:18080/plugin/ws"
    assert child_env["PYTHONUTF8"] == "1"
    assert child_env["PYTHONIOENCODING"] == "utf-8"
    assert captured["kwargs"]["stdout"] is manager_module.sys.stderr


@pytest.mark.asyncio
async def test_windows_launch_cancellation_reaps_worker(monkeypatch, tmp_path):
    class HangingProcess:
        def __init__(self):
            self.returncode = None
            self.wait_started = asyncio.Event()
            self.release = asyncio.Event()

        async def wait(self):
            self.wait_started.set()
            await self.release.wait()

    process = HangingProcess()

    async def fake_create_subprocess_exec(*_args, **_kwargs):
        return process

    async def stop_process(stopped_process):
        assert stopped_process is process
        process.returncode = -9
        process.release.set()
        return True

    monkeypatch.setattr(manager_module, "get_platform", lambda: "win32")
    monkeypatch.setattr(
        manager_module.asyncio,
        "create_subprocess_exec",
        fake_create_subprocess_exec,
    )
    monkeypatch.setattr(
        manager_module.stdio_client_controller,
        "stop_process",
        AsyncMock(side_effect=stop_process),
    )
    plugin_path = _write_installed_plugin(tmp_path)
    launch_task = asyncio.create_task(_manager().launch_plugin(str(plugin_path)))
    await process.wait_started.wait()
    launch_task.cancel()

    with pytest.raises(asyncio.CancelledError):
        await launch_task
    manager_module.stdio_client_controller.stop_process.assert_awaited_once_with(
        process
    )


@pytest.mark.asyncio
async def test_launch_all_plugins_waits_for_trusted_workspace_binding(monkeypatch):
    context = RuntimeContext()
    context.ws_debug_port = 18080
    manager = PluginManager(context)
    context.plugin_mgr = manager
    monkeypatch.setattr(
        "langbot_plugin.runtime.plugin.mgr.glob.glob",
        lambda _pattern: [],
    )

    launch_task = asyncio.create_task(manager.launch_all_plugins())
    await asyncio.sleep(0)

    assert not launch_task.done()

    context.bind_workspace(
        ActionContext(
            instance_uuid="instance-1",
            workspace_uuid="workspace-a",
            placement_generation=9,
        )
    )
    await launch_task


def test_find_plugin_and_component_lists_respect_include_filters():
    manager = _manager()
    tool = _component("Tool", "lookup")
    command = _component("Command", "admin")
    parser = _component("Parser", "pdf", {"supported_mime_types": ["application/pdf"]})
    manager.plugins = [
        _plugin(name="demo", components=[tool, command, parser]),
        _plugin(name="other", components=[_component("Tool", "skip")]),
    ]

    assert manager.find_plugin("tester", "demo") is manager.plugins[0]
    assert manager.find_plugin("tester", "missing") is None

    tools = asyncio.run(manager.list_tools(include_plugins=["tester/demo"]))
    commands = asyncio.run(manager.list_commands(include_plugins=["tester/demo"]))
    parsers = asyncio.run(manager.list_parsers())

    assert [tool.metadata.name for tool in tools] == ["lookup"]
    assert [command.metadata.name for command in commands] == ["admin"]
    assert parsers[0]["plugin_id"] == "tester/demo"
    assert parsers[0]["supported_mime_types"] == ["application/pdf"]


@pytest.mark.asyncio
async def test_notify_plugin_diagnostic_routes_to_target_and_log_buffer():
    manager = _manager()
    plugin = _plugin()
    handler = FakeHandler(plugin)
    plugin._runtime_plugin_handler = handler
    manager.plugins = [plugin]
    diagnostic = {
        "level": "ERROR",
        "code": "deferred_response_delivery_failed",
        "message": "Deferred response delivery failed",
        "plugin": {"author": "tester", "name": "demo"},
        "query": {
            "query_id": 123,
            "event_name": "GroupNormalMessageReceived",
            "stage": "SendResponseBackStage",
        },
        "delivery": {
            "error_type": "ActionFailed",
            "error_message": "retcode=1200",
        },
        "message_chain": {
            "component_types": ["Plain", "Image"],
            "component_count": 2,
        },
    }

    await manager.notify_plugin_diagnostic(diagnostic)

    assert handler.diagnostics == [
        {
            "level": "ERROR",
            "code": "deferred_response_delivery_failed",
            "message": "Deferred response delivery failed",
            "details": {
                "query_id": 123,
                "event_name": "GroupNormalMessageReceived",
                "stage": "SendResponseBackStage",
                "delivery_error": "ActionFailed: retcode=1200",
                "message_chain": {
                    "component_types": ["Plain", "Image"],
                    "component_count": 2,
                },
            },
        }
    ]
    assert handler.log_buffer.entries == [
        (
            "ERROR",
            "[deferred_response_delivery_failed] Deferred response delivery failed"
            " | query_id=123 | event=GroupNormalMessageReceived"
            " | stage=SendResponseBackStage"
            " | delivery_error=ActionFailed: retcode=1200",
        )
    ]


@pytest.mark.asyncio
async def test_notify_plugin_diagnostic_missing_target_only_warns(caplog):
    manager = _manager()
    manager.plugins = []
    caplog.set_level("WARNING")

    await manager.notify_plugin_diagnostic(
        {
            "level": "ERROR",
            "code": "deferred_response_delivery_failed",
            "message": "Deferred response delivery failed",
            "plugin": {"author": "tester", "name": "missing"},
        }
    )

    assert "Plugin diagnostic target not found (tester/missing)" in caplog.text


@pytest.mark.asyncio
async def test_notify_plugin_diagnostic_skips_synthetic_log_with_active_reader():
    manager = _manager()
    plugin = _plugin()
    handler = FakeHandler(plugin)
    handler.log_buffer.has_active_reader = True
    plugin._runtime_plugin_handler = handler
    manager.plugins = [plugin]

    await manager.notify_plugin_diagnostic(
        {
            "level": "ERROR",
            "code": "deferred_response_delivery_failed",
            "message": "Deferred response delivery failed",
            "plugin": {"author": "tester", "name": "demo"},
        }
    )

    assert handler.diagnostics
    assert handler.log_buffer.entries == []


@pytest.mark.asyncio
async def test_install_plugin_from_file_extracts_manifest_to_staging(
    tmp_path,
    monkeypatch,
):
    monkeypatch.chdir(tmp_path)
    manager = _manager()
    old_plugin = _plugin(name="demo")
    old_plugin._runtime_plugin_handler = FakeHandler(old_plugin)
    manager.plugins = [old_plugin]
    old_path = tmp_path / "data/plugins/tester__demo"
    old_path.mkdir(parents=True)
    (old_path / "old.py").write_text("", encoding="utf-8")

    new_path, author, name, version = await manager.install_plugin_from_file(
        _plugin_zip(version="2.0.0")
    )

    staged = tmp_path / new_path
    assert (staged / "manifest.yaml").exists()
    assert new_path.startswith("data/.plugin-staging/tester__demo-")
    assert (author, name, version) == ("tester", "demo", "2.0.0")
    assert manager.plugins == [old_plugin]
    assert (old_path / "old.py").exists()


@pytest.mark.asyncio
async def test_install_plugin_from_file_rejects_same_version_duplicate(
    tmp_path, monkeypatch
):
    monkeypatch.chdir(tmp_path)
    manager = _manager()
    manager.plugins = [_plugin(name="demo")]

    with pytest.raises(ValueError, match="already exists"):
        await manager.install_plugin_from_file(_plugin_zip(version="1.0.0"))


@pytest.mark.asyncio
async def test_install_plugin_from_file_reuses_verified_extractor(
    tmp_path, monkeypatch
):
    monkeypatch.chdir(tmp_path)
    manager = _manager()
    with zipfile.ZipFile(io.BytesIO(_plugin_zip()), "r") as source:
        manifest = source.read("manifest.yaml")
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("manifest.yaml", manifest)
        archive.writestr("../escaped.py", "unsafe")

    with pytest.raises(ValueError, match="unsafe path"):
        await manager.install_plugin_from_file(buffer.getvalue())

    assert not (tmp_path / "escaped.py").exists()


def test_idle_plugin_operation_locks_are_not_retained():
    manager = _manager()
    lock = manager._get_plugin_operation_lock("tester", "transient")

    manager._forget_plugin_operation_lock("tester", "transient", lock)

    assert manager._plugin_operation_locks == {}


@pytest.mark.asyncio
async def test_dependency_reconciliation_isolates_plugin_failures(monkeypatch):
    manager = _manager()

    async def fake_install(plugin_path):
        if plugin_path.endswith("bad"):
            raise OSError("venv unavailable")
        return 0, ""

    monkeypatch.setattr(
        "langbot_plugin.runtime.plugin.mgr.glob.glob",
        lambda pattern: ["data/plugins/bad", "data/plugins/good"],
    )
    monkeypatch.setattr(
        "langbot_plugin.runtime.plugin.mgr.os.path.isdir",
        lambda path: True,
    )
    monkeypatch.setattr(
        "langbot_plugin.runtime.plugin.mgr.pkgmgr_helper.install_requirements_isolated",
        fake_install,
    )

    await manager.ensure_all_plugins_dependencies_installed()

    assert manager._dependency_errors == {
        "data/plugins/bad": "OSError: venv unavailable"
    }


@pytest.mark.asyncio
async def test_activation_stops_supervisor_without_registered_container(
    tmp_path, monkeypatch
):
    monkeypatch.chdir(tmp_path)
    manager = _manager()
    target_path = tmp_path / "data/plugins/tester__demo"
    target_path.mkdir(parents=True)
    (target_path / "old.py").write_text("old", encoding="utf-8")
    staging_path = tmp_path / "data/.plugin-staging/tester__demo-new"
    staging_path.mkdir(parents=True)
    (staging_path / "new.py").write_text("new", encoding="utf-8")
    manager.stop_plugin_supervisor = AsyncMock()

    await manager._activate_staged_plugin(str(staging_path), "tester", "demo")

    manager.stop_plugin_supervisor.assert_awaited_once_with("data/plugins/tester__demo")
    assert (target_path / "new.py").is_file()


@pytest.mark.asyncio
async def test_activation_failure_restores_and_restarts_previous_generation(
    tmp_path, monkeypatch
):
    monkeypatch.chdir(tmp_path)
    manager = _manager()
    target_path = tmp_path / "data/plugins/tester__demo"
    target_path.mkdir(parents=True)
    (target_path / "old.py").write_text("old", encoding="utf-8")
    staging_path = tmp_path / "data/.plugin-staging/tester__demo-new"
    staging_path.mkdir(parents=True)
    (staging_path / "new.py").write_text("new", encoding="utf-8")
    manager.stop_plugin_supervisor = AsyncMock()
    restarted = []
    manager.start_plugin_supervisor = lambda path: restarted.append(path)
    real_replace = os.replace

    def fail_new_generation(source, destination):
        if str(source) == str(staging_path):
            raise OSError("swap failed")
        return real_replace(source, destination)

    monkeypatch.setattr(
        "langbot_plugin.runtime.plugin.mgr.os.replace",
        fail_new_generation,
    )

    with pytest.raises(OSError, match="swap failed"):
        await manager._activate_staged_plugin(str(staging_path), "tester", "demo")

    assert (target_path / "old.py").read_text(encoding="utf-8") == "old"
    assert restarted == ["data/plugins/tester__demo"]


@pytest.mark.asyncio
async def test_install_plugin_raises_when_dependency_install_fails(
    tmp_path, monkeypatch
):
    monkeypatch.chdir(tmp_path)
    plugin_path = tmp_path / "data/plugins/tester__demo"
    plugin_path.mkdir(parents=True)
    (plugin_path / "requirements.txt").write_text("missing-package\n", encoding="utf-8")
    manager = _manager()

    async def fake_install_from_file(plugin_file):
        return "data/plugins/tester__demo", "tester", "demo", "1.0.0"

    call_count = {"n": 0}

    async def fake_install_single_async(
        dep, extra_params=None, *, python_executable=None, timeout_sec=300
    ):
        call_count["n"] += 1
        return 1, 0, "pip could not find package"

    # No real sleeping between retries.
    async def fake_sleep(delay):
        return None

    async def fake_ensure_plugin_environment(plugin_path):
        return "plugin-python"

    monkeypatch.setattr(manager, "install_plugin_from_file", fake_install_from_file)
    monkeypatch.setattr(
        "langbot_plugin.runtime.plugin.mgr.pkgmgr_helper.ensure_plugin_environment",
        fake_ensure_plugin_environment,
    )
    monkeypatch.setattr(
        "langbot_plugin.runtime.helper.pkgmgr.install_single_async",
        fake_install_single_async,
    )
    monkeypatch.setattr(
        "langbot_plugin.runtime.helper.pkgmgr.asyncio.sleep",
        fake_sleep,
    )

    progress = []
    with pytest.raises(DependencyInstallError) as exc_info:
        async for item in manager.install_plugin(
            PluginInstallSource.LOCAL,
            {"plugin_file": b"zip"},
        ):
            progress.append(item["current_action"])

    err = exc_info.value
    assert err.plugin == "tester/demo"
    assert err.failed == ["missing-package"]
    # pip stderr preserved in structured details for debugging.
    assert "pip could not find package" in err.details["missing-package"]
    # install_with_retry must have retried up to max_retries (3) before giving up.
    assert call_count["n"] == 3

    assert progress[0] == "downloading plugin package"
    assert "installing dependencies" in progress
    assert "initializing plugin settings" not in progress
    assert "launching plugin" not in progress


@pytest.mark.asyncio
async def test_install_plugin_raises_verification_error_when_pip_lies(
    tmp_path, monkeypatch
):
    """pip reports success but the dependency is still unsatisfiable."""
    monkeypatch.chdir(tmp_path)
    plugin_path = tmp_path / "data/plugins/tester__demo"
    plugin_path.mkdir(parents=True)
    (plugin_path / "requirements.txt").write_text(
        "langbot-absent-after-install\n", encoding="utf-8"
    )
    manager = _manager()

    async def fake_install_from_file(plugin_file):
        return "data/plugins/tester__demo", "tester", "demo", "1.0.0"

    # pip exits 0 (success) but nothing actually got installed.
    async def fake_install_single_async(
        dep, extra_params=None, *, python_executable=None, timeout_sec=300
    ):
        return 0, 0, "Successfully installed langbot-absent-after-install"

    monkeypatch.setattr(manager, "install_plugin_from_file", fake_install_from_file)
    monkeypatch.setattr(
        "langbot_plugin.runtime.plugin.mgr.pkgmgr_helper.ensure_plugin_environment",
        lambda plugin_path: asyncio.sleep(0, result="plugin-python"),
    )
    monkeypatch.setattr(
        "langbot_plugin.runtime.helper.pkgmgr.install_single_async",
        fake_install_single_async,
    )
    monkeypatch.setattr(
        "langbot_plugin.runtime.plugin.mgr.pkgmgr_helper.classify_requirements_in_environment",
        lambda python, deps: asyncio.sleep(
            0, result=(["langbot-absent-after-install"], [])
        ),
    )

    with pytest.raises(DependencyVerificationError) as exc_info:
        async for _ in manager.install_plugin(
            PluginInstallSource.LOCAL,
            {"plugin_file": b"zip"},
        ):
            pass

    err = exc_info.value
    assert err.plugin == "tester/demo"
    assert "langbot-absent-after-install" in err.missing
    assert err.version_mismatch == []


@pytest.mark.asyncio
async def test_register_plugin_initializes_settings_and_refreshes_container():
    manager = _manager()
    control_handler = FakeControlHandler()
    manager.context = _bound_runtime_context(control_handler)
    plugin = _plugin(
        name="demo",
        components=[_component("Tool", "lookup")],
        status=RuntimeContainerStatus.MOUNTED,
    )
    handler = FakeHandler(plugin)

    capability = _registration_capability(manager, plugin)
    await manager.register_plugin(
        handler,
        plugin.model_dump(),
        registration_capability=capability,
    )

    registered = manager.plugins[0]
    assert registered._runtime_plugin_handler is handler
    assert registered.install_source == PluginInstallSource.MARKETPLACE.value
    assert registered.install_info == {"plugin_version": "1.0.0"}
    assert registered.status is RuntimeContainerStatus.INITIALIZED
    assert [
        component.manifest.metadata.name for component in registered.components
    ] == ["lookup"]
    assert handler.initialized_with["plugin_config"] == {"api_key": "secret"}


@pytest.mark.asyncio
async def test_register_plugin_binds_installation_from_trusted_host_settings():
    manager = _manager()
    control_handler = FakeControlHandler()
    manager.context = _bound_runtime_context(control_handler)
    workspace_binding = manager.context.workspace_binding
    plugin = _plugin(status=RuntimeContainerStatus.MOUNTED)
    handler = FakeHandler(plugin)

    capability = _registration_capability(manager, plugin)
    await manager.register_plugin(
        handler,
        plugin.model_dump(),
        registration_capability=capability,
    )

    assert handler.bound_action_context == workspace_binding.for_installation(
        "installation-1"
    )


@pytest.mark.asyncio
async def test_registration_capability_is_one_use_and_manifest_bound():
    manager = _manager()
    control_handler = FakeControlHandler()
    manager.context = _bound_runtime_context(control_handler)
    expected = _plugin(status=RuntimeContainerStatus.MOUNTED)
    forged = _plugin(
        author="attacker",
        name="forged",
        status=RuntimeContainerStatus.MOUNTED,
    )
    capability = _registration_capability(manager, expected)

    with pytest.raises(ValueError, match="manifest identity"):
        await manager.register_plugin(
            FakeHandler(forged),
            forged.model_dump(),
            registration_capability=capability,
        )

    assert control_handler.calls == []
    assert not manager.is_registration_capability_pending(capability)
    with pytest.raises(ValueError, match="invalid or already used"):
        await manager.register_plugin(
            FakeHandler(expected),
            expected.model_dump(),
            registration_capability=capability,
        )


@pytest.mark.asyncio
async def test_registered_plugin_cannot_change_manifest_identity_on_refresh():
    manager = _manager()
    control_handler = FakeControlHandler()
    manager.context = _bound_runtime_context(control_handler)
    plugin = _plugin(status=RuntimeContainerStatus.MOUNTED)
    handler = FakeHandler(plugin)
    capability = _registration_capability(manager, plugin)

    async def forged_container():
        payload = plugin.model_dump()
        payload["manifest"]["manifest"]["metadata"]["name"] = "forged"
        return payload

    handler.get_plugin_container = forged_container

    with pytest.raises(ValueError, match="changed its manifest identity"):
        await manager.register_plugin(
            handler,
            plugin.model_dump(),
            registration_capability=capability,
        )

    assert manager.plugins == []


@pytest.mark.asyncio
async def test_register_plugin_waits_for_binding_before_host_settings_request():
    manager = _manager()
    control_handler = FakeControlHandler()
    context = RuntimeContext()
    context.control_handler = control_handler
    context.ws_debug_port = 18080
    manager.context = context
    plugin = _plugin(status=RuntimeContainerStatus.MOUNTED)
    handler = FakeHandler(plugin)

    capability = _registration_capability(manager, plugin)
    register_task = asyncio.create_task(
        manager.register_plugin(
            handler,
            plugin.model_dump(),
            registration_capability=capability,
        )
    )
    await asyncio.sleep(0)

    assert not register_task.done()
    assert control_handler.calls == []

    context.bind_workspace(
        ActionContext(
            instance_uuid="instance-1",
            workspace_uuid="workspace-a",
            placement_generation=9,
        )
    )
    await register_task

    assert [call[0] for call in control_handler.calls] == [
        RuntimeToLangBotAction.GET_PLUGIN_SETTINGS
    ]
    assert handler.bound_action_context == context.workspace_binding.for_installation(
        "installation-1"
    )


@pytest.mark.asyncio
async def test_register_plugin_rejects_missing_installation_capability():
    manager = _manager()
    control_handler = FakeControlHandler()

    async def settings_without_installation(action, payload, *, action_context=None):
        result = await FakeControlHandler.call_action(
            control_handler, action, payload, action_context=action_context
        )
        result.pop("installation_uuid")
        return result

    control_handler.call_action = settings_without_installation
    manager.context = _bound_runtime_context(control_handler)
    plugin = _plugin(status=RuntimeContainerStatus.MOUNTED)
    capability = _registration_capability(manager, plugin)

    with pytest.raises(ValueError, match="installation capability"):
        await manager.register_plugin(
            FakeHandler(plugin),
            plugin.model_dump(),
            registration_capability=capability,
        )

    assert manager.plugins == []


@pytest.mark.asyncio
async def test_register_debug_plugin_initializes_settings_first():
    manager = _manager()
    control_handler = FakeControlHandler()
    manager.context = _bound_runtime_context(control_handler)
    plugin = _plugin(name="debug", status=RuntimeContainerStatus.MOUNTED)
    handler = FakeHandler(plugin)
    handler.debug_plugin = True
    handler.bound_action_context = manager.context.workspace_binding

    await manager.register_plugin(handler, plugin.model_dump(), debug_plugin=True)

    assert control_handler.contexts[:2] == [
        manager.context.workspace_binding,
        manager.context.workspace_binding,
    ]

    assert [call[0] for call in control_handler.calls] == [
        RuntimeToLangBotAction.INITIALIZE_PLUGIN_SETTINGS,
        RuntimeToLangBotAction.GET_PLUGIN_SETTINGS,
    ]
    assert (
        control_handler.calls[0][1]["install_source"] == PluginInstallSource.DEBUG.value
    )
    assert manager.plugins[0].debug is True


@pytest.mark.asyncio
async def test_register_plugin_requires_control_handler():
    manager = _manager()
    manager.context = _bound_runtime_context()
    plugin = _plugin(status=RuntimeContainerStatus.MOUNTED)
    capability = _registration_capability(manager, plugin)

    with pytest.raises(ValueError, match="Failed to get plugin settings"):
        await manager.register_plugin(
            FakeHandler(plugin),
            plugin.model_dump(),
            registration_capability=capability,
        )


@pytest.mark.asyncio
async def test_minimal_toy_plugin_registers_and_dispatches_core_surfaces():
    manager = _manager()
    control_handler = FakeControlHandler()
    manager.context = _bound_runtime_context(control_handler)
    components = [
        _component("Tool", "lookup"),
        _component("Command", "admin"),
        _component("Page", "settings"),
        _component(
            "Runner",
            "default",
            {
                "usages": ["agent"],
                "capabilities": {"streaming": True},
                "permissions": {},
                "config": [],
            },
        ),
    ]
    plugin = _plugin(
        name="toy",
        components=components,
        status=RuntimeContainerStatus.MOUNTED,
    )
    handler = FakeHandler(plugin)
    capability = _registration_capability(manager, plugin)

    await manager.register_plugin(
        handler,
        plugin.model_dump(),
        registration_capability=capability,
    )

    assert [tool.metadata.name for tool in await manager.list_tools()] == ["lookup"]
    assert [tool.owner for tool in await manager.list_tools()] == ["tester/toy"]
    assert [command.metadata.name for command in await manager.list_commands()] == [
        "admin"
    ]
    assert await manager.call_tool(
        "lookup",
        {"city": "Shanghai"},
        {"launcher_type": "person"},
        query_id=7,
    ) == {
        "tool_name": "lookup",
        "params": {"city": "Shanghai"},
        "query_id": 7,
    }
    command_responses = [
        response
        async for response in manager.execute_command(
            SimpleNamespace(
                command="admin",
                model_dump=lambda mode="json": {"command": "admin"},
            )
        )
    ]
    assert command_responses == [CommandReturn(text="admin")]

    page_response = await manager.handle_page_api(
        "tester",
        "toy",
        page_id="settings",
        endpoint="/save",
        method="POST",
        body={"enabled": True},
    )
    assert page_response["data"]["body"] == {"enabled": True}

    runners = await manager.list_runners()
    assert runners[0]["manifest"]["id"] == "plugin:tester/toy/default"
    results = [
        item
        async for item in manager.run_runner(
            "tester",
            "toy",
            "default",
            {
                "run_id": "run_toy",
                "trigger": {"type": "message.received"},
                "event": {
                    "event_id": "event_toy",
                    "event_type": "message.received",
                    "source": "test",
                },
                "input": {"text": "hello"},
                "delivery": {"surface": "platform"},
                "resources": {},
                "runtime": {},
                "config": {},
            },
        )
    ]

    assert [item["type"] for item in results] == [
        "message.completed",
        "run.completed",
    ]
    assert [item["sequence"] for item in results] == [1, 2]
    assert handler.agent_run_calls[0][1]["runner_name"] == "default"


@pytest.mark.asyncio
async def test_call_tool_and_execute_command_delegate_to_connected_plugin():
    manager = _manager()
    plugin = _plugin(
        components=[
            _component("Tool", "lookup"),
            _component("Command", "admin"),
        ]
    )
    plugin._runtime_plugin_handler = FakeHandler(plugin)
    manager.plugins = [plugin]

    tool_response = await manager.call_tool(
        "lookup",
        {"city": "Paris"},
        {"launcher_type": "person"},
        query_id=99,
        query_uuid="query-opaque-99",
    )
    command_responses = [
        response
        async for response in manager.execute_command(
            SimpleNamespace(
                command="admin",
                model_dump=lambda mode="json": {"command": "admin"},
            )
        )
    ]

    assert tool_response == {
        "tool_name": "lookup",
        "params": {"city": "Paris"},
        "query_id": 99,
        "query_uuid": "query-opaque-99",
    }
    assert command_responses == [CommandReturn(text="admin")]


@pytest.mark.asyncio
async def test_call_tool_and_execute_command_return_empty_when_filtered_or_disconnected():
    manager = _manager()
    plugin = _plugin(
        components=[
            _component("Tool", "lookup"),
            _component("Command", "admin"),
        ]
    )
    manager.plugins = [plugin]

    assert (
        await manager.call_tool(
            "lookup",
            {},
            {},
            query_id=1,
            include_plugins=["tester/other"],
        )
        == {}
    )
    assert await manager.call_tool("lookup", {}, {}, query_id=1) == {}
    assert [
        response
        async for response in manager.execute_command(
            SimpleNamespace(
                command="admin",
                model_dump=lambda mode="json": {"command": "admin"},
            )
        )
    ] == []


@pytest.mark.asyncio
async def test_shutdown_plugin_closes_connection_and_removes_container():
    manager = _manager()
    plugin = _plugin()
    handler = FakeHandler(plugin)
    plugin._runtime_plugin_handler = handler
    manager.plugins = [plugin]
    manager.plugin_handlers = [handler]

    await manager.shutdown_plugin(plugin)

    assert manager.plugins == []
    assert manager.plugin_handlers == []
    assert handler.shutdown_calls == 1
    assert handler.conn.closed is True


@pytest.mark.asyncio
async def test_shutdown_all_plugins_uses_snapshot_and_closes_every_plugin():
    manager = _manager()
    plugins = [_plugin(name="one"), _plugin(name="two")]
    handlers = [FakeHandler(plugin) for plugin in plugins]
    for plugin, handler in zip(plugins, handlers, strict=True):
        plugin._runtime_plugin_handler = handler
    manager.plugins = list(plugins)
    manager.plugin_handlers = list(handlers)

    await manager.shutdown_all_plugins()

    assert manager.plugins == []
    assert manager.plugin_handlers == []
    assert [handler.shutdown_calls for handler in handlers] == [1, 1]


@pytest.mark.asyncio
async def test_add_plugin_handler_cleans_up_after_unexpected_run_failure():
    manager = _manager()
    plugin = _plugin()
    handler = FakeHandler(plugin)
    plugin._runtime_plugin_handler = handler
    manager.plugins = [plugin]
    handler.run = AsyncMock(side_effect=RuntimeError("protocol failure"))

    with pytest.raises(RuntimeError, match="protocol failure"):
        await manager.add_plugin_handler(handler)

    assert manager.plugin_handlers == []
    assert manager.plugins == []


@pytest.mark.asyncio
async def test_plugin_supervisor_restarts_after_crash(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    plugin_path = tmp_path / "data/plugins/tester__demo"
    plugin_path.mkdir(parents=True)
    manager = _manager()
    second_generation_started = asyncio.Event()
    calls = 0

    async def fake_launch(path):
        nonlocal calls
        calls += 1
        if calls == 1:
            raise RuntimeError("crash")
        second_generation_started.set()
        await asyncio.Event().wait()

    monkeypatch.setattr(manager, "launch_plugin", fake_launch)
    monkeypatch.setattr(
        "langbot_plugin.runtime.plugin.mgr._PLUGIN_RESTART_INITIAL_DELAY_SEC",
        0,
    )

    manager.start_plugin_supervisor(str(plugin_path))
    await asyncio.wait_for(second_generation_started.wait(), timeout=1)
    assert calls == 2

    await manager.stop_plugin_supervisor(str(plugin_path))
    assert str(plugin_path) not in manager._desired_plugin_paths


@pytest.mark.asyncio
async def test_register_plugin_rolls_back_container_when_initialize_fails():
    manager = _manager()
    manager.context = _bound_runtime_context(FakeControlHandler())
    plugin = _plugin(status=RuntimeContainerStatus.MOUNTED)
    handler = FakeHandler(plugin)
    handler.initialize_plugin = AsyncMock(side_effect=RuntimeError("init failed"))
    registration_capability = _registration_capability(manager, plugin)

    with pytest.raises(RuntimeError, match="init failed"):
        await manager.register_plugin(
            handler,
            plugin.model_dump(),
            registration_capability=registration_capability,
        )

    assert manager.plugins == []
    assert manager.plugin_handlers == []


@pytest.mark.asyncio
async def test_restart_plugin_debug_skips_relaunch_and_missing_plugin_errors():
    manager = _manager()
    plugin = _plugin(debug=True)
    handler = FakeHandler(plugin)
    plugin._runtime_plugin_handler = handler
    manager.plugins = [plugin]
    manager.plugin_handlers = [handler]

    actions = [
        item["current_action"]
        async for item in manager.restart_plugin("tester", "demo")
    ]

    assert actions == [
        "shutting down plugin",
        "removing plugin container",
        "plugin restarted",
    ]
    assert manager.plugin_run_tasks == []
    assert manager.plugins == []

    with pytest.raises(ValueError, match="Plugin tester/missing not found"):
        async for _ in manager.restart_plugin("tester", "missing"):
            pass


@pytest.mark.asyncio
async def test_delete_plugin_removes_files_and_rejects_debug_plugins(
    tmp_path, monkeypatch
):
    monkeypatch.chdir(tmp_path)
    manager = _manager()
    plugin_path = tmp_path / "data/plugins/tester__demo"
    plugin_path.mkdir(parents=True)
    (plugin_path / "manifest.yaml").write_text("kind: Plugin\n", encoding="utf-8")
    plugin = _plugin()
    handler = FakeHandler(plugin)
    plugin._runtime_plugin_handler = handler
    manager.plugins = [plugin]
    manager.plugin_handlers = [handler]

    actions = [
        item["current_action"] async for item in manager.delete_plugin("tester", "demo")
    ]

    assert actions == [
        "shutting down plugin",
        "removing plugin container",
        "deleting plugin files",
        "plugin deleted",
    ]
    assert not plugin_path.exists()

    debug = _plugin(debug=True)
    manager.plugins = [debug]
    with pytest.raises(ValueError, match="is a debugging plugin"):
        async for _ in manager.delete_plugin("tester", "demo"):
            pass


@pytest.mark.asyncio
async def test_delete_plugin_removes_installed_files_when_plugin_is_not_running(
    tmp_path, monkeypatch
):
    monkeypatch.chdir(tmp_path)
    manager = _manager()
    plugin_path = tmp_path / "data/plugins/tester__demo"
    plugin_path.mkdir(parents=True)
    (plugin_path / "manifest.yaml").write_text(
        "kind: Plugin\nmetadata:\n  author: tester\n  name: demo\n",
        encoding="utf-8",
    )

    actions = [
        item["current_action"] async for item in manager.delete_plugin("tester", "demo")
    ]

    assert actions == [
        "stopping plugin supervisor",
        "deleting plugin files",
        "plugin deleted",
    ]
    assert not plugin_path.exists()


@pytest.mark.asyncio
async def test_upgrade_plugin_validates_source_and_reports_up_to_date(monkeypatch):
    manager = _manager()
    debug = _plugin(debug=True)
    manager.plugins = [debug]

    with pytest.raises(ValueError, match="is a debugging plugin"):
        async for _ in manager.upgrade_plugin("tester", "demo"):
            pass

    local = _plugin()
    manager.plugins = [local]
    with pytest.raises(ValueError, match="not installed from marketplace"):
        async for _ in manager.upgrade_plugin("tester", "demo"):
            pass

    marketplace = _plugin()
    marketplace.install_source = PluginInstallSource.MARKETPLACE.value
    manager.plugins = [marketplace]

    async def fake_get_plugin_info(author, name):
        return SimpleNamespace(latest_version="1.0.0")

    monkeypatch.setattr(marketplace_helper, "get_plugin_info", fake_get_plugin_info)

    actions = [
        item["current_action"]
        async for item in manager.upgrade_plugin("tester", "demo")
    ]

    assert actions == ["checking for latest version", "plugin is up to date"]


@pytest.mark.asyncio
async def test_plugin_resource_and_page_methods_delegate_to_connected_handler():
    manager = _manager()
    plugin = _plugin()
    handler = FakeHandler(plugin)
    plugin._runtime_plugin_handler = handler
    manager.plugins = [plugin]

    assert await manager.get_plugin_icon("tester", "missing") == (b"", "")
    assert await manager.get_plugin_icon("tester", "demo") == (
        b"<svg/>",
        "image/svg+xml",
    )
    assert "icon-key" not in handler.files
    assert await manager.get_plugin_readme("tester", "demo", language="zh") == b"# Demo"
    assert "readme-key" not in handler.files
    assert await manager.get_plugin_assets_file("tester", "demo", "missing") == (
        b"",
        "",
    )
    assert await manager.get_plugin_assets_file("tester", "demo", "asset.txt") == (
        b"asset-bytes",
        "text/plain",
    )
    assert "asset-key" not in handler.files

    page_response = await manager.handle_page_api(
        "tester",
        "demo",
        page_id="settings",
        endpoint="/save",
        method="POST",
        body={"enabled": True},
    )
    assert page_response["data"]["page_id"] == "settings"
    assert page_response["data"]["body"] == {"enabled": True}
    assert await manager.handle_page_api(
        "tester",
        "missing",
        page_id="settings",
        endpoint="/save",
        method="POST",
    ) == {"data": None, "error": "Plugin not found"}


@pytest.mark.asyncio
async def test_shared_plugin_resource_transfers_use_exact_installation_binding():
    manager = _manager()
    plugin = _plugin()
    digest = "a" * 64
    binding = InstallationBinding(
        instance_uuid="instance-1",
        workspace_uuid="workspace-a",
        placement_generation=1,
        installation_uuid="installation-a",
        runtime_revision=1,
        artifact_digest=digest,
    )
    sibling = binding.model_copy(
        update={
            "workspace_uuid": "workspace-b",
            "installation_uuid": "installation-b",
        }
    )

    class SharedHandler(FakeHandler):
        def __init__(self, container):
            super().__init__(container)
            self.files = {
                (binding, "icon-key"): b"<svg/>",
                (binding, "readme-key"): b"# Demo",
                (binding, "asset-key"): b"asset-bytes",
                (sibling, "icon-key"): b"sibling icon",
            }
            self.file_calls = []

        async def read_local_file(self, file_key, *, action_context):
            self.file_calls.append(("read", action_context, file_key))
            return self.files[(action_context, file_key)]

        async def delete_local_file(self, file_key, *, action_context):
            self.file_calls.append(("delete", action_context, file_key))
            self.files.pop((action_context, file_key), None)

    handler = SharedHandler(plugin)
    plugin._runtime_plugin_handler = handler
    manager.plugins = [plugin]
    manager._binding_by_container_id[id(plugin)] = binding

    assert await manager.get_plugin_icon("tester", "demo") == (
        b"<svg/>",
        "image/svg+xml",
    )
    assert await manager.get_plugin_readme("tester", "demo") == b"# Demo"
    assert await manager.get_plugin_assets_file("tester", "demo", "asset.txt") == (
        b"asset-bytes",
        "text/plain",
    )
    assert {call[1] for call in handler.file_calls} == {binding}
    assert handler.files[(sibling, "icon-key")] == b"sibling icon"
    assert not any(key[0] == binding for key in handler.files)


@pytest.mark.asyncio
async def test_plugin_logs_and_resource_methods_handle_missing_connections():
    manager = _manager()
    assert await manager.get_plugin_logs("tester", "missing") == []
    assert await manager.get_plugin_readme("tester", "missing") == b""
    assert await manager.get_plugin_assets_file("tester", "missing", "asset.txt") == (
        b"",
        "",
    )

    plugin = _plugin()
    manager.plugins = [plugin]
    assert await manager.get_plugin_logs("tester", "demo") == []
    assert await manager.handle_page_api(
        "tester",
        "demo",
        page_id="settings",
        endpoint="/save",
        method="POST",
    ) == {"data": None, "error": "Plugin is not connected"}

    handler = FakeHandler(plugin)
    plugin._runtime_plugin_handler = handler
    assert await manager.get_plugin_logs("tester", "demo", limit=3, level="INFO") == [
        {"limit": 3, "level": "INFO", "text": "ready"}
    ]


@pytest.mark.asyncio
async def test_knowledge_engine_methods_validate_components_and_delegate_to_handler():
    manager = _manager()
    rag = _component(
        "KnowledgeEngine",
        "kb",
        {
            "creation_schema": [{"name": "api_key"}],
            "retrieval_schema": [{"name": "top_k"}],
        },
    )
    plugin = _plugin(components=[rag])
    plugin._runtime_plugin_handler = FakeHandler(plugin)
    manager.plugins = [plugin]

    engines = await manager.list_knowledge_engines()
    assert engines[0]["plugin_id"] == "tester/demo"
    assert engines[0]["capabilities"] == ["ingest", "retrieve"]
    assert engines[0]["creation_schema"] == {"schema": [{"name": "api_key"}]}
    assert await manager.get_rag_creation_schema("tester", "demo") == {
        "schema": [{"name": "api_key"}]
    }
    assert await manager.get_rag_retrieval_schema("tester", "demo") == {
        "schema": [{"name": "top_k"}]
    }
    assert await manager.rag_ingest_document(
        "tester",
        "demo",
        {"document_id": "doc-1"},
    ) == {"ingested": "doc-1"}
    assert await manager.rag_delete_document("tester", "demo", "kb-1", "doc-1") == {
        "deleted": ["kb-1", "doc-1"]
    }
    assert await manager.rag_on_kb_create(
        "tester",
        "demo",
        "kb-1",
        {"api_key": "secret"},
    ) == {"created": "kb-1", "config": {"api_key": "secret"}}
    assert await manager.rag_on_kb_delete("tester", "demo", "kb-1") == {
        "deleted_kb": "kb-1"
    }

    with pytest.raises(ValueError, match="has no KnowledgeEngine component"):
        manager.plugins = [_plugin(components=[])]
        await manager.rag_ingest_document("tester", "demo", {})


@pytest.mark.asyncio
async def test_knowledge_engine_errors_and_retrieve_knowledge_delegate():
    manager = _manager()

    with pytest.raises(ValueError, match="Plugin tester/missing not found"):
        await manager.retrieve_knowledge("tester", "missing", "kb", {"query": "hi"})

    plugin = _plugin(components=[_component("KnowledgeEngine", "kb")])
    manager.plugins = [plugin]
    with pytest.raises(ValueError, match="is not connected"):
        await manager.retrieve_knowledge("tester", "demo", "kb", {"query": "hi"})

    handler = FakeHandler(plugin)
    plugin._runtime_plugin_handler = handler
    assert await manager.retrieve_knowledge(
        "tester", "demo", "kb", {"query": "hi"}
    ) == {
        "retriever_name": "kb",
        "retrieval_context": {"query": "hi"},
    }
    assert await manager.get_rag_creation_schema("tester", "missing") == {"schema": []}
    assert await manager.get_rag_retrieval_schema("tester", "missing") == {"schema": []}

    manager.plugins = [_plugin(components=[])]
    with pytest.raises(ValueError, match="has no KnowledgeEngine component"):
        await manager.rag_delete_document("tester", "demo", "kb-1", "doc-1")

    plugin_without_handler = _plugin(components=[_component("KnowledgeEngine", "kb")])
    manager.plugins = [plugin_without_handler]
    with pytest.raises(ValueError, match="is not connected"):
        await manager.rag_on_kb_create("tester", "demo", "kb-1", {})


@pytest.mark.asyncio
async def test_parser_methods_validate_components_and_delegate_to_handler():
    manager = _manager()
    parser = _component(
        "Parser",
        "pdf",
        {"supported_mime_types": ["application/pdf"]},
    )
    plugin = _plugin(components=[parser])
    plugin._runtime_plugin_handler = FakeHandler(plugin)
    manager.plugins = [plugin]

    parsers = await manager.list_parsers()
    assert parsers[0]["plugin_id"] == "tester/demo"
    assert parsers[0]["supported_mime_types"] == ["application/pdf"]
    assert await manager.parse_document(
        "tester",
        "demo",
        {"filename": "a.txt"},
        b"hello",
    ) == {"context": {"filename": "a.txt"}, "text": "hello"}

    plugin._runtime_plugin_handler = None
    with pytest.raises(ValueError, match="is not connected"):
        await manager.parse_document("tester", "demo", {}, b"")


@pytest.mark.asyncio
async def test_parser_errors_for_missing_plugin_and_component():
    manager = _manager()

    with pytest.raises(ValueError, match="Plugin tester/missing not found"):
        await manager.parse_document("tester", "missing", {}, b"")

    manager.plugins = [_plugin(components=[])]
    with pytest.raises(ValueError, match="has no Parser component"):
        await manager.parse_document("tester", "demo", {}, b"")


@pytest.mark.asyncio
async def test_emit_event_should_report_each_emitting_plugin_once():
    manager = _manager()
    plugin = _plugin(components=[_component("EventListener", "events")])
    plugin._runtime_plugin_handler = FakeHandler(plugin)
    manager.plugins = [plugin]
    event_context = EventContext(
        query_id=1,
        event_name="PersonCommandSent",
        event=PersonCommandSent(
            launcher_type="person",
            launcher_id="launcher",
            sender_id="sender",
            command="demo",
            params=[],
            text_message="/demo",
            is_admin=False,
        ),
    )

    emitted_plugins, _, _ = await manager.emit_event(event_context)

    assert emitted_plugins == [plugin]


@pytest.mark.asyncio
async def test_emit_event_rejects_plugin_query_uuid_forgery():
    manager = _manager()
    plugin = _plugin(components=[_component("EventListener", "events")])
    plugin._runtime_plugin_handler = QueryUuidChangingFakeHandler(plugin)
    manager.plugins = [plugin]
    event_context = EventContext(
        query_id=1,
        query_uuid="query-trusted",
        event_name="PersonCommandSent",
        event=PersonCommandSent(
            query_uuid="query-trusted",
            launcher_type="person",
            launcher_id="launcher",
            sender_id="sender",
            command="demo",
            params=[],
            text_message="/demo",
            is_admin=False,
        ),
    )

    with pytest.raises(ValueError, match="changed EventContext query_uuid"):
        await manager.emit_event(event_context)


@pytest.mark.asyncio
async def test_emit_event_restores_query_uuid_dropped_by_legacy_plugin():
    manager = _manager()
    plugin = _plugin(components=[_component("EventListener", "events")])
    plugin._runtime_plugin_handler = QueryUuidDroppingFakeHandler(plugin)
    manager.plugins = [plugin]
    event_context = EventContext(
        query_id=1,
        query_uuid="query-trusted",
        event_name="PersonCommandSent",
        event=PersonCommandSent(
            query_uuid="query-trusted",
            launcher_type="person",
            launcher_id="launcher",
            sender_id="sender",
            command="demo",
            params=[],
            text_message="/demo",
            is_admin=False,
        ),
    )

    _, returned_context, _ = await manager.emit_event(event_context)

    assert returned_context.query_uuid == "query-trusted"
    assert returned_context.event.query_uuid == "query-trusted"


@pytest.mark.asyncio
async def test_emit_event_reports_only_plugins_that_changed_reply_message_chain():
    manager = _manager()
    observer = _plugin(
        name="observer", components=[_component("EventListener", "events")]
    )
    responder = _plugin(
        name="responder", components=[_component("EventListener", "events")]
    )
    observer._runtime_plugin_handler = FakeHandler(observer)
    responder._runtime_plugin_handler = ReplyChangingFakeHandler(responder)
    manager.plugins = [observer, responder]
    event_context = EventContext(
        query_id=1,
        event_name="PersonNormalMessageReceived",
        event=PersonNormalMessageReceived(
            launcher_type="person",
            launcher_id="launcher",
            sender_id="sender",
            text_message="hello",
            message_event={
                "time": 0.0,
                "self_id": "bot",
                "sender": {"id": "sender", "nickname": "Sender", "remark": ""},
                "message_chain": [{"type": "Plain", "text": "hello"}],
            },
            message_chain=platform_message.MessageChain(
                [platform_message.Plain(text="hello")]
            ),
        ),
    )

    emitted_plugins, event_context, response_sources = await manager.emit_event(
        event_context
    )

    assert emitted_plugins == [observer, responder]
    assert response_sources == [
        {
            "kind": "reply_message_chain",
            "plugin": {"author": "tester", "name": "responder"},
        }
    ]
    assert str(event_context.event.reply_message_chain) == "plugin reply"


@pytest.mark.asyncio
async def test_install_plugin_marketplace_streams_progress_and_launches(monkeypatch):
    manager = _manager()
    control_handler = FakeControlHandler()
    manager.context = SimpleNamespace(control_handler=control_handler)

    async def fake_download_plugin_streaming(author, name, version):
        yield {
            "done": False,
            "downloaded": 5,
            "total": 10,
            "speed": 2,
        }
        yield {"done": True, "data": b"zip"}

    async def fake_install_plugin_from_file(plugin_file):
        assert plugin_file == b"zip"
        return "data/.plugin-staging/tester__demo-stage", "tester", "demo", "1.0.0"

    launched = []

    def fake_start_plugin_supervisor(plugin_path):
        launched.append(plugin_path)

    async def fake_wait_for_plugin_ready(author, name, timeout):
        return None

    monkeypatch.setattr(
        marketplace_helper,
        "download_plugin_streaming",
        fake_download_plugin_streaming,
    )
    monkeypatch.setattr(
        manager, "install_plugin_from_file", fake_install_plugin_from_file
    )
    monkeypatch.setattr(
        manager, "start_plugin_supervisor", fake_start_plugin_supervisor
    )
    monkeypatch.setattr(manager, "_wait_for_plugin_ready", fake_wait_for_plugin_ready)
    monkeypatch.setattr(
        manager,
        "_activate_staged_plugin",
        lambda path, author, name: asyncio.sleep(0, result=None),
    )

    progress = [
        item
        async for item in manager.install_plugin(
            PluginInstallSource.MARKETPLACE,
            {
                "plugin_author": "tester",
                "plugin_name": "demo",
                "plugin_version": "1.0.0",
            },
        )
    ]
    assert [item["current_action"] for item in progress] == [
        "downloading plugin package",
        "downloading plugin package",
        "installing dependencies",
        "initializing plugin settings",
        "launching plugin",
    ]
    assert progress[1]["metadata"] == {
        "download_current": 5,
        "download_total": 10,
        "download_speed": 2,
    }
    assert control_handler.calls[-1][1]["install_info"] == {
        "plugin_author": "tester",
        "plugin_name": "demo",
        "plugin_version": "1.0.0",
    }
    assert launched == ["data/plugins/tester__demo"]


@pytest.mark.asyncio
async def test_reinstall_cancellation_does_not_cancel_runtime_launch(monkeypatch):
    context = SimpleNamespace(wait_for_workspace_binding=AsyncMock())
    manager = PluginManager(context)
    monkeypatch.setattr(manager_module.glob, "glob", lambda pattern: [])
    ready = asyncio.Event()

    async def worker():
        ready.set()
        await asyncio.Future()

    child = asyncio.create_task(worker())
    manager.plugin_run_tasks = [child]
    launch = asyncio.create_task(manager.launch_all_plugins())
    await ready.wait()
    child.cancel()
    await launch
    assert child.cancelled()
    assert not launch.cancelled()


def _command_event():
    return EventContext(
        query_id=1,
        event_name="PersonCommandSent",
        event=PersonCommandSent(
            launcher_type="person",
            launcher_id="launcher",
            sender_id="sender",
            command="demo",
            params=[],
            text_message="/demo",
            is_admin=False,
        ),
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "kind", [None, "Runner", "Tool", "Command", "Parser", "Page", "KnowledgeEngine"]
)
async def test_emit_event_skips_plugins_without_listener(kind):
    manager = _manager()
    plugin = _plugin(
        components=[
            _component(
                kind, "component", {"usages": ["agent"]} if kind == "Runner" else {}
            )
        ]
        if kind
        else []
    )
    handler = FakeHandler(plugin)
    handler.emit_event = AsyncMock(side_effect=RuntimeError("must not contact worker"))
    plugin._runtime_plugin_handler = handler
    listener = _plugin(
        name="listener", components=[_component("EventListener", "events")]
    )
    listener._runtime_plugin_handler = FakeHandler(listener)
    manager.plugins = [plugin, listener]
    emitted, _, _ = await manager.emit_event(_command_event())
    assert emitted == [listener]
    handler.emit_event.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize("prevent", [False, True])
async def test_listener_dispatch_preserves_order_mutation_and_prevention(prevent):
    manager = _manager()
    calls = []
    for name in ["first", "second", "third"]:
        plugin = _plugin(name=name, components=[_component("EventListener", "events")])
        handler = FakeHandler(plugin)

        async def emit(context, name=name):
            calls.append((name, context["event"]["text_message"]))
            await asyncio.sleep(0)
            context["event"]["text_message"] += ":" + name
            context["is_prevent_postorder"] = prevent and name == "second"
            return {"emitted": True, "event_context": context}

        handler.emit_event = emit
        plugin._runtime_plugin_handler = handler
        manager.plugins.append(plugin)
    emitted, context, _ = await manager.emit_event(_command_event())
    expected = ["first", "second"] if prevent else ["first", "second", "third"]
    assert [p.manifest.metadata.name for p in emitted] == expected
    assert [c[0] for c in calls] == expected
    assert calls[1][1] == "/demo:first"
    assert context.event.text_message == "/demo:" + ":".join(expected)


@pytest.mark.asyncio
@pytest.mark.parametrize("error", [RuntimeError, TimeoutError, ConnectionError])
async def test_subscriber_failures_preserve_existing_propagation(error):
    manager = _manager()
    first = _plugin(components=[_component("EventListener", "events")])
    first._runtime_plugin_handler = FakeHandler(first)
    first._runtime_plugin_handler.emit_event = AsyncMock(
        side_effect=error("listener fault")
    )
    second = _plugin(name="second", components=[_component("EventListener", "events")])
    second._runtime_plugin_handler = FakeHandler(second)
    second._runtime_plugin_handler.emit_event = AsyncMock()
    manager.plugins = [first, second]
    with pytest.raises(error):
        await manager.emit_event(_command_event())
    second._runtime_plugin_handler.emit_event.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "excluded", ["disabled", "uninitialized", "disconnected", "binding"]
)
async def test_listener_dispatch_retains_admission_filters(excluded):
    manager = _manager()
    plugin = _plugin(
        components=[
            _component("Runner", "run", {"usages": ["agent"]}),
            _component("EventListener", "events"),
        ]
    )
    handler = FakeHandler(plugin)
    handler.emit_event = AsyncMock(
        side_effect=AssertionError("filtered listener contacted")
    )
    plugin._runtime_plugin_handler = handler
    if excluded == "disabled":
        plugin.enabled = False
    elif excluded == "uninitialized":
        plugin.status = RuntimeContainerStatus.MOUNTED
    elif excluded == "disconnected":
        plugin._runtime_plugin_handler = None
    manager.plugins = [plugin]
    emitted, _, _ = await manager.emit_event(
        _command_event(), include_plugins=[] if excluded == "binding" else None
    )
    assert emitted == []
    handler.emit_event.assert_not_awaited()


@pytest.mark.asyncio
async def test_emit_event_reports_only_the_plugin_that_prevented_default():
    manager = _manager()
    observer = _plugin(
        name="observer", components=[_component("EventListener", "events")]
    )
    taker = _plugin(name="taker", components=[_component("EventListener", "events")])
    later = _plugin(name="later", components=[_component("EventListener", "events")])
    observer._runtime_plugin_handler = FakeHandler(observer)
    taker._runtime_plugin_handler = DefaultPreventingFakeHandler(taker)
    # A later plugin that sets the flag again must not take the attribution.
    later._runtime_plugin_handler = DefaultPreventingFakeHandler(later)
    manager.plugins = [observer, taker, later]
    event_context = EventContext(
        query_id=1,
        event_name="PersonNormalMessageReceived",
        event=PersonNormalMessageReceived(
            launcher_type="person",
            launcher_id="launcher",
            sender_id="sender",
            text_message="hello",
            message_event={
                "time": 0.0,
                "self_id": "bot",
                "sender": {"id": "sender", "nickname": "Sender", "remark": ""},
                "message_chain": [{"type": "Plain", "text": "hello"}],
            },
            message_chain=platform_message.MessageChain(
                [platform_message.Plain(text="hello")]
            ),
        ),
    )

    _, returned_context, response_sources = await manager.emit_event(event_context)

    assert returned_context.is_prevented_default()
    assert response_sources == [
        {
            "kind": "prevent_default",
            "plugin": {"author": "tester", "name": "taker"},
        }
    ]
