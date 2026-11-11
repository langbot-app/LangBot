from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest

from langbot_plugin.api.entities.context import EventContext
from langbot_plugin.entities.io.actions.enums import (
    CommonAction,
    LangBotToRuntimeAction,
)
from langbot_plugin.runtime.io.handlers.control import ControlConnectionHandler
from langbot_plugin.runtime.settings import settings as runtime_settings
from langbot_plugin.entities.io.context import (
    ActionContext,
    InstallationBinding,
    PluginWorkerPolicy,
    RuntimeConfig,
    RuntimeIdentity,
)
from langbot_plugin.runtime.context import RuntimeContext

from tests.helpers.protocol import (
    ProtocolConnection,
    ProtocolSession as BaseProtocolSession,
)


TEST_RUNTIME_IDENTITY = RuntimeIdentity(
    instance_uuid="instance-1",
    runtime_id="runtime-boot-1",
)
TEST_WORKER_POLICY = PluginWorkerPolicy(
    max_cpus=1.0,
    max_memory_mb=512,
    max_pids=128,
    max_open_files=256,
    max_file_size_mb=512,
)
TEST_RUNTIME_CONFIG = RuntimeConfig(
    runtime_identity=TEST_RUNTIME_IDENTITY,
    worker_policy=TEST_WORKER_POLICY,
)
TEST_SHARED_RUNTIME_CONFIG = TEST_RUNTIME_CONFIG.model_copy(
    update={"runtime_profile": "shared"}
)
TEST_INSTALLATION_BINDING = InstallationBinding(
    instance_uuid="instance-1",
    workspace_uuid="workspace-a",
    placement_generation=4,
    installation_uuid="installation-1",
    runtime_revision=2,
    artifact_digest="a" * 64,
)


def ProtocolSession(handler):
    """Use an explicit tenant envelope by default in control action tests."""

    return BaseProtocolSession(
        handler,
        default_action_context=TEST_INSTALLATION_BINDING,
    )


class Dumpable:
    def __init__(self, payload):
        self.payload = payload

    def model_dump(self, **kwargs):
        return self.payload


class FakePlugin:
    def __init__(self, author="tester", name="demo"):
        self.manifest = SimpleNamespace(
            metadata=SimpleNamespace(author=author, name=name)
        )

    def model_dump(self, **kwargs):
        return {
            "manifest": {
                "author": self.manifest.metadata.author,
                "name": self.manifest.metadata.name,
            }
        }


class FakePluginManager:
    def __init__(self):
        self.plugins = [FakePlugin()]
        self.calls = []
        self.worker_policy = None
        self.runtime_profile = None

    def configure_worker_runtime(self, policy, runtime_profile):
        self.worker_policy = policy
        self.runtime_profile = runtime_profile

    async def reconcile_plugin_installations(self, installations):
        self.calls.append(("reconcile_plugin_installations", installations))
        return {"applied": [], "removed": [], "missing_artifacts": []}

    async def apply_plugin_installation(
        self,
        binding,
        *,
        artifact_package=None,
        enabled=True,
    ):
        self.calls.append(
            (
                "apply_plugin_installation",
                binding,
                artifact_package,
                enabled,
            )
        )
        return {"installation_uuid": binding.installation_uuid, "state": "starting"}

    async def remove_plugin_installation(self, binding):
        self.calls.append(("remove_plugin_installation", binding))
        return {"installation_uuid": binding.installation_uuid, "state": "removed"}

    async def get_plugin_icon(self, author, plugin_name):
        self.calls.append(("get_plugin_icon", author, plugin_name))
        return b"icon", "image/svg+xml"

    async def get_plugin_readme(self, author, plugin_name, language):
        self.calls.append(("get_plugin_readme", author, plugin_name, language))
        return b"# readme"

    async def get_plugin_logs(self, author, plugin_name, limit=200, level=None):
        self.calls.append(("get_plugin_logs", author, plugin_name, limit, level))
        return [{"level": level, "text": "ready"}]

    async def notify_plugin_diagnostic(self, diagnostic):
        self.calls.append(("notify_plugin_diagnostic", diagnostic))

    async def get_plugin_assets_file(self, author, plugin_name, file_key):
        self.calls.append(("get_plugin_assets_file", author, plugin_name, file_key))
        return b"asset", "text/plain"

    async def handle_page_api(
        self,
        plugin_author,
        plugin_name,
        page_id,
        endpoint,
        method,
        body,
    ):
        self.calls.append(
            (
                "handle_page_api",
                plugin_author,
                plugin_name,
                page_id,
                endpoint,
                method,
                body,
            )
        )
        return {"data": {"ok": True}, "error": None}

    async def install_plugin(self, install_source, install_info):
        self.calls.append(("install_plugin", install_source.value, install_info))
        yield {"current_action": "downloaded"}
        yield {"current_action": "mounted"}

    async def restart_plugin(self, plugin_author, plugin_name):
        self.calls.append(("restart_plugin", plugin_author, plugin_name))
        yield {"current_action": "stopped"}

    async def delete_plugin(self, plugin_author, plugin_name):
        self.calls.append(("delete_plugin", plugin_author, plugin_name))
        yield {"current_action": "deleted"}

    async def upgrade_plugin(self, plugin_author, plugin_name):
        self.calls.append(("upgrade_plugin", plugin_author, plugin_name))
        yield {"current_action": "upgraded"}

    async def emit_event(self, event_context, include_plugins=None):
        self.calls.append(("emit_event", event_context, include_plugins))
        event_context.prevent_postorder()
        return (
            [
                self.plugins[0],
            ],
            event_context,
            [
                {
                    "kind": "reply_message_chain",
                    "plugin": {"author": "tester", "name": "demo"},
                }
            ],
        )

    async def list_tools(self, include_plugins=None):
        self.calls.append(("list_tools", include_plugins))
        return [Dumpable({"name": "weather"})]

    async def call_tool(
        self,
        tool_name,
        tool_parameters,
        session,
        query_id,
        include_plugins=None,
        query_uuid=None,
    ):
        call = (
            "call_tool",
            tool_name,
            tool_parameters,
            session,
            query_id,
            include_plugins,
        )
        if query_uuid is not None:
            call = (
                *call,
                query_uuid,
            )
        self.calls.append(call)
        return {"text": "sunny"}

    async def list_commands(self, include_plugins=None):
        self.calls.append(("list_commands", include_plugins))
        return [Dumpable({"name": "start"})]

    async def execute_command(self, command_context, include_plugins=None):
        self.calls.append(("execute_command", command_context, include_plugins))
        yield Dumpable({"text": command_context.command})

    async def retrieve_knowledge(
        self, plugin_author, plugin_name, retriever_name, retrieval_context
    ):
        self.calls.append(
            (
                "retrieve_knowledge",
                plugin_author,
                plugin_name,
                retriever_name,
                retrieval_context,
            )
        )
        return {"results": [{"id": "r1"}]}

    async def list_knowledge_engines(self):
        self.calls.append(("list_knowledge_engines",))
        return [{"name": "rag"}]

    async def rag_ingest_document(self, plugin_author, plugin_name, context_data):
        self.calls.append(
            ("rag_ingest_document", plugin_author, plugin_name, context_data)
        )
        return {"document_id": "doc"}

    async def rag_delete_document(self, plugin_author, plugin_name, kb_id, document_id):
        self.calls.append(
            ("rag_delete_document", plugin_author, plugin_name, kb_id, document_id)
        )
        return {"deleted": document_id}

    async def rag_on_kb_create(self, plugin_author, plugin_name, kb_id, config):
        self.calls.append(
            ("rag_on_kb_create", plugin_author, plugin_name, kb_id, config)
        )
        return {"created": kb_id}

    async def rag_on_kb_delete(self, plugin_author, plugin_name, kb_id):
        self.calls.append(("rag_on_kb_delete", plugin_author, plugin_name, kb_id))
        return {"deleted_kb": kb_id}

    async def get_rag_creation_schema(self, plugin_author, plugin_name):
        self.calls.append(("get_rag_creation_schema", plugin_author, plugin_name))
        return {"schema": [{"name": "api_key"}]}

    async def get_rag_retrieval_schema(self, plugin_author, plugin_name):
        self.calls.append(("get_rag_retrieval_schema", plugin_author, plugin_name))
        return {"schema": [{"name": "top_k"}]}

    async def list_parsers(self):
        self.calls.append(("list_parsers",))
        return [{"name": "parser"}]

    async def parse_document(
        self, plugin_author, plugin_name, context_data, file_bytes
    ):
        self.calls.append(
            ("parse_document", plugin_author, plugin_name, context_data, file_bytes)
        )
        return {"text": "parsed"}


def _handler(*, configured=True, runtime_config=TEST_RUNTIME_CONFIG):
    manager = FakePluginManager()
    context = RuntimeContext()
    context.plugin_mgr = manager
    context.ws_debug_port = 5401
    handler = ControlConnectionHandler(ProtocolConnection(), context)
    context.activate_control_handler(handler)
    if configured:
        handler.configure_runtime(runtime_config)
    return handler, manager


async def test_control_handler_ping_protocol_response():
    handler, _manager = _handler()

    async with ProtocolSession(handler) as session:
        response = await session.request(
            CommonAction.PING.value,
            seq_id=10,
            action_context=None,
        )

    assert response["seq_id"] == 10
    assert response["code"] == 0
    assert response["data"] == {"message": "pong"}


async def test_control_handler_lists_plugins_over_protocol():
    handler, _manager = _handler()

    async with ProtocolSession(handler) as session:
        response = await session.request(LangBotToRuntimeAction.LIST_PLUGINS.value)

    assert response["code"] == 0
    assert response["data"] == {
        "plugins": [{"manifest": {"author": "tester", "name": "demo"}}]
    }


async def test_control_handler_get_plugin_info_returns_match_or_none():
    handler, _manager = _handler()

    async with ProtocolSession(handler) as session:
        found = await session.request(
            LangBotToRuntimeAction.GET_PLUGIN_INFO.value,
            {"author": "tester", "plugin_name": "demo"},
            seq_id=1,
        )
        missing = await session.request(
            LangBotToRuntimeAction.GET_PLUGIN_INFO.value,
            {"author": "tester", "plugin_name": "missing"},
            seq_id=2,
        )

    assert found["data"]["plugin"] == {"manifest": {"author": "tester", "name": "demo"}}
    assert missing["data"]["plugin"] is None


async def test_control_handler_set_runtime_config_updates_cloud_service_url(
    monkeypatch,
):
    handler, _manager = _handler(configured=False)
    monkeypatch.setattr(runtime_settings, "cloud_service_url", "https://old.example")
    config = TEST_RUNTIME_CONFIG.model_copy(
        update={"cloud_service_url": "https://space.example"}
    )

    async with ProtocolSession(handler) as session:
        response = await session.request(
            LangBotToRuntimeAction.SET_RUNTIME_CONFIG.value,
            config.model_dump(),
            action_context=None,
        )

    assert response["data"] == {"event_batch": True}
    assert runtime_settings.cloud_service_url == "https://space.example"
    assert handler.context.runtime_identity == TEST_RUNTIME_IDENTITY
    assert handler.context.worker_policy == TEST_WORKER_POLICY
    assert handler.context.workspace_binding is None


async def test_control_handler_rejects_incomplete_runtime_config():
    handler, _manager = _handler(configured=False)

    async with ProtocolSession(handler) as session:
        response = await session.request(
            LangBotToRuntimeAction.SET_RUNTIME_CONFIG.value,
            {},
            action_context=None,
        )

    assert response["code"] == 1
    assert "runtime_identity" in response["message"]
    assert handler.context.workspace_binding is None
    assert handler.context.runtime_identity is None


async def test_control_handler_binds_runtime_once_to_identity_and_policy():
    context = RuntimeContext()
    context.plugin_mgr = FakePluginManager()
    context.ws_debug_port = 5401
    handler = ControlConnectionHandler(ProtocolConnection(), context)
    context.activate_control_handler(handler)

    async with ProtocolSession(handler) as session:
        first = await session.request(
            LangBotToRuntimeAction.SET_RUNTIME_CONFIG.value,
            TEST_RUNTIME_CONFIG.model_dump(),
            action_context=None,
        )
        repeated = await session.request(
            LangBotToRuntimeAction.SET_RUNTIME_CONFIG.value,
            TEST_RUNTIME_CONFIG.model_dump(),
            action_context=None,
        )
        rebound = await session.request(
            LangBotToRuntimeAction.SET_RUNTIME_CONFIG.value,
            TEST_RUNTIME_CONFIG.model_copy(
                update={
                    "runtime_identity": TEST_RUNTIME_IDENTITY.model_copy(
                        update={"runtime_id": "runtime-boot-2"}
                    )
                }
            ).model_dump(),
            action_context=None,
        )

    assert first["code"] == 0
    assert repeated["code"] == 0
    assert context.runtime_identity == TEST_RUNTIME_IDENTITY
    assert context.worker_policy == TEST_WORKER_POLICY
    assert context.workspace_binding is None
    assert handler.bound_action_context is None
    assert rebound["code"] == 1
    assert "identity cannot be rebound" in rebound["message"]


async def test_control_handler_get_debug_info_returns_workspace_token():
    handler, _manager = _handler()
    workspace_context = ActionContext(
        instance_uuid="instance-1",
        workspace_uuid="workspace-a",
        placement_generation=4,
    )

    async with ProtocolSession(handler) as session:
        response = await session.request(
            LangBotToRuntimeAction.GET_DEBUG_INFO.value,
            action_context=workspace_context,
        )

    assert response["code"] == 0
    assert len(response["data"]["plugin_debug_key"]) >= 32
    assert response["data"]["expires_at"].endswith("Z")
    assert response["data"]["ws_debug_port"] == 5401
    resources = response["data"]["resources"]
    assert resources["installation_states"] == {
        "running": 0,
        "starting": 0,
        "failed": 0,
        "disabled": 0,
        "other": 0,
    }
    assert resources["shared_pool"]["workers"] == 0
    assert resources["shared_pool"]["slots"] == 0
    assert resources["restart_coordinator"] == {"configured": False}
    assert "workspace-a" not in str(resources)


async def test_control_handler_rejects_tenant_action_without_complete_binding():
    handler, manager = _handler()
    workspace_only = ActionContext(
        instance_uuid="instance-1",
        workspace_uuid="workspace-a",
        placement_generation=4,
    )

    async with ProtocolSession(handler) as session:
        missing = await session.request(
            LangBotToRuntimeAction.LIST_PLUGINS.value,
            action_context=None,
            seq_id=1,
        )
        partial = await session.request(
            LangBotToRuntimeAction.LIST_PLUGINS.value,
            action_context=workspace_only,
            seq_id=2,
        )

    assert missing["code"] == 1
    assert partial["code"] == 1
    assert "complete InstallationBinding" in missing["message"]
    assert "complete InstallationBinding" in partial["message"]
    assert manager.calls == []
    assert handler.context.workspace_binding is None


async def test_control_handler_rejects_cross_instance_and_cross_workspace_actions():
    handler, _manager = _handler()

    async with ProtocolSession(handler) as session:
        accepted = await session.request(
            LangBotToRuntimeAction.LIST_PLUGINS.value,
            seq_id=1,
        )
        cross_instance = await session.request(
            LangBotToRuntimeAction.LIST_PLUGINS.value,
            action_context=TEST_INSTALLATION_BINDING.model_copy(
                update={"instance_uuid": "instance-2"}
            ),
            seq_id=2,
        )
        cross_workspace = await session.request(
            LangBotToRuntimeAction.LIST_PLUGINS.value,
            action_context=TEST_INSTALLATION_BINDING.model_copy(
                update={
                    "workspace_uuid": "workspace-b",
                    "installation_uuid": "installation-2",
                }
            ),
            seq_id=3,
        )

    assert accepted["code"] == 0
    assert cross_instance["code"] == 1
    assert "does not match Runtime instance" in cross_instance["message"]
    assert cross_workspace["code"] == 1
    assert "cannot dispatch another Workspace safely" in cross_workspace["message"]


async def test_control_handler_rejects_changed_installation_revision_or_artifact():
    handler, _manager = _handler()

    async with ProtocolSession(handler) as session:
        accepted = await session.request(
            LangBotToRuntimeAction.LIST_PLUGINS.value,
            seq_id=1,
        )
        stale_or_rebound = await session.request(
            LangBotToRuntimeAction.LIST_PLUGINS.value,
            action_context=TEST_INSTALLATION_BINDING.model_copy(
                update={"runtime_revision": 3, "artifact_digest": "b" * 64}
            ),
            seq_id=2,
        )

    assert accepted["code"] == 0
    assert stale_or_rebound["code"] == 1
    assert (
        "cannot change generation, revision, or artifact" in stale_or_rebound["message"]
    )


async def test_superseded_control_handler_rejects_even_instance_scoped_actions():
    context = RuntimeContext()
    context.plugin_mgr = FakePluginManager()
    context.ws_debug_port = 5401
    old_handler = ControlConnectionHandler(ProtocolConnection(), context)
    context.activate_control_handler(old_handler)
    old_handler.configure_runtime(TEST_RUNTIME_CONFIG)

    new_handler = ControlConnectionHandler(ProtocolConnection(), context)
    previous = context.activate_control_handler(new_handler)
    assert previous is old_handler
    old_handler.invalidate()
    new_handler.configure_runtime(TEST_RUNTIME_CONFIG)

    async with ProtocolSession(old_handler) as old_session:
        rejected = await old_session.request(
            CommonAction.PING.value,
            action_context=None,
        )
    async with ProtocolSession(new_handler) as new_session:
        accepted = await new_session.request(
            CommonAction.PING.value,
            action_context=None,
        )

    assert rejected["code"] == 1
    assert "superseded" in rejected["message"]
    assert accepted["code"] == 0


async def test_control_handler_reconciles_instance_desired_state_without_context():
    handler, manager = _handler()
    second_binding = TEST_INSTALLATION_BINDING.model_copy(
        update={
            "workspace_uuid": "workspace-b",
            "installation_uuid": "installation-2",
        }
    )

    async with ProtocolSession(handler) as session:
        response = await session.request(
            LangBotToRuntimeAction.RECONCILE_PLUGIN_INSTALLATIONS.value,
            {
                "installations": [
                    {
                        "binding": TEST_INSTALLATION_BINDING.model_dump(),
                        "enabled": True,
                    },
                    {"binding": second_binding.model_dump(), "enabled": False},
                ]
            },
            action_context=None,
        )

    assert response["code"] == 0
    call_name, desired = manager.calls[0]
    assert call_name == "reconcile_plugin_installations"
    assert [item.binding for item in desired] == [
        TEST_INSTALLATION_BINDING,
        second_binding,
    ]


async def test_control_handler_applies_artifact_with_envelope_binding(monkeypatch):
    handler, manager = _handler()
    file_ops = []

    async def fake_read(file_key):
        file_ops.append(("read", file_key))
        return b"verified-package"

    async def fake_delete(file_key):
        file_ops.append(("delete", file_key))

    monkeypatch.setattr(handler, "read_local_file", fake_read)
    monkeypatch.setattr(handler, "delete_local_file", fake_delete)

    async with ProtocolSession(handler) as session:
        response = await session.request(
            LangBotToRuntimeAction.APPLY_PLUGIN_INSTALLATION.value,
            {"artifact_file_key": "artifact-key", "enabled": True},
        )

    assert response["code"] == 0
    assert file_ops == [("read", "artifact-key"), ("delete", "artifact-key")]
    assert manager.calls == [
        (
            "apply_plugin_installation",
            TEST_INSTALLATION_BINDING,
            b"verified-package",
            True,
        )
    ]


async def test_control_handler_remove_requires_exact_current_binding():
    handler, manager = _handler()
    handler.context.activate_installation_binding(TEST_INSTALLATION_BINDING)

    async with ProtocolSession(handler) as session:
        response = await session.request(
            LangBotToRuntimeAction.REMOVE_PLUGIN_INSTALLATION.value,
            {},
        )

    assert response["code"] == 0
    assert manager.calls == [("remove_plugin_installation", TEST_INSTALLATION_BINDING)]


async def test_control_handler_get_plugin_icon_sends_file_key(monkeypatch):
    handler, manager = _handler()

    async def fake_send_file(file_bytes, extension):
        assert file_bytes == b"icon"
        assert extension == ""
        return "icon-key"

    monkeypatch.setattr(handler, "send_file", fake_send_file)

    async with ProtocolSession(handler) as session:
        response = await session.request(
            LangBotToRuntimeAction.GET_PLUGIN_ICON.value,
            {
                "plugin_author": "tester",
                "plugin_name": "demo",
            },
        )

    assert manager.calls == [("get_plugin_icon", "tester", "demo")]
    assert response["data"] == {
        "plugin_icon_file_key": "icon-key",
        "mime_type": "image/svg+xml",
    }


async def test_control_handler_get_plugin_readme_sends_file_key(monkeypatch):
    handler, manager = _handler()

    async def fake_send_file(file_bytes, extension):
        assert file_bytes == b"# readme"
        assert extension == "md"
        return "readme-key"

    monkeypatch.setattr(handler, "send_file", fake_send_file)

    async with ProtocolSession(handler) as session:
        response = await session.request(
            LangBotToRuntimeAction.GET_PLUGIN_README.value,
            {
                "plugin_author": "tester",
                "plugin_name": "demo",
                "language": "zh",
            },
        )

    assert manager.calls == [("get_plugin_readme", "tester", "demo", "zh")]
    assert response["data"] == {"readme_file_key": "readme-key"}


async def test_control_handler_get_plugin_readme_returns_none_for_empty_readme(
    monkeypatch,
):
    handler, manager = _handler()

    async def fake_get_plugin_readme(author, plugin_name, language):
        manager.calls.append(("get_plugin_readme", author, plugin_name, language))
        return b""

    monkeypatch.setattr(manager, "get_plugin_readme", fake_get_plugin_readme)

    async with ProtocolSession(handler) as session:
        response = await session.request(
            LangBotToRuntimeAction.GET_PLUGIN_README.value,
            {
                "plugin_author": "tester",
                "plugin_name": "demo",
            },
        )

    assert manager.calls == [("get_plugin_readme", "tester", "demo", "en")]
    assert response["data"] == {"readme_file_key": None}


async def test_control_handler_get_plugin_logs_delegates_limit_and_level():
    handler, manager = _handler()

    async with ProtocolSession(handler) as session:
        response = await session.request(
            LangBotToRuntimeAction.GET_PLUGIN_LOGS.value,
            {
                "plugin_author": "tester",
                "plugin_name": "demo",
                "limit": "5",
                "level": "INFO",
            },
        )

    assert manager.calls == [("get_plugin_logs", "tester", "demo", 5, "INFO")]
    assert response["data"] == {"logs": [{"level": "INFO", "text": "ready"}]}


async def test_control_handler_plugin_diagnostic_delegates_to_plugin_manager():
    handler, manager = _handler()
    payload = {
        "level": "ERROR",
        "code": "deferred_response_delivery_failed",
        "message": "Deferred response delivery failed",
        "plugin": {"author": "tester", "name": "demo"},
    }

    async with ProtocolSession(handler) as session:
        response = await session.request(
            LangBotToRuntimeAction.PLUGIN_DIAGNOSTIC.value,
            payload,
        )

    assert response["data"] == {}
    assert manager.calls == [("notify_plugin_diagnostic", payload)]


async def test_control_handler_get_plugin_assets_file_sends_file_key(monkeypatch):
    handler, manager = _handler()

    async def fake_send_file(file_bytes, extension):
        assert file_bytes == b"asset"
        assert extension == ""
        return "asset-key"

    monkeypatch.setattr(handler, "send_file", fake_send_file)

    async with ProtocolSession(handler) as session:
        response = await session.request(
            LangBotToRuntimeAction.GET_PLUGIN_ASSETS_FILE.value,
            {
                "plugin_author": "tester",
                "plugin_name": "demo",
                "file_path": "icon.svg",
            },
        )

    assert manager.calls == [("get_plugin_assets_file", "tester", "demo", "icon.svg")]
    assert response["data"] == {
        "file_file_key": "asset-key",
        "mime_type": "text/plain",
    }


async def test_control_handler_get_plugin_assets_file_returns_none_for_missing_file(
    monkeypatch,
):
    handler, manager = _handler()

    async def fake_get_plugin_assets_file(author, plugin_name, file_key):
        manager.calls.append(("get_plugin_assets_file", author, plugin_name, file_key))
        return b"", ""

    monkeypatch.setattr(manager, "get_plugin_assets_file", fake_get_plugin_assets_file)

    async with ProtocolSession(handler) as session:
        response = await session.request(
            LangBotToRuntimeAction.GET_PLUGIN_ASSETS_FILE.value,
            {
                "plugin_author": "tester",
                "plugin_name": "demo",
                "file_path": "missing.txt",
            },
        )

    assert manager.calls == [
        ("get_plugin_assets_file", "tester", "demo", "missing.txt")
    ]
    assert response["data"] == {"file_file_key": None, "mime_type": None}


async def test_control_handler_page_api_validates_required_fields():
    handler, _manager = _handler()

    async with ProtocolSession(handler) as session:
        response = await session.request(
            LangBotToRuntimeAction.PAGE_API.value,
            {"plugin_author": "tester", "plugin_name": "demo"},
        )

    assert response["code"] == 0
    assert response["data"] == {
        "data": None,
        "error": "Missing required field: page_id",
    }


async def test_control_handler_page_api_delegates_to_plugin_manager():
    handler, manager = _handler()

    async with ProtocolSession(handler) as session:
        response = await session.request(
            LangBotToRuntimeAction.PAGE_API.value,
            {
                "plugin_author": "tester",
                "plugin_name": "demo",
                "page_id": "settings",
                "endpoint": "/save",
                "method": "POST",
                "body": {"enabled": True},
            },
        )

    assert manager.calls == [
        (
            "handle_page_api",
            "tester",
            "demo",
            "settings",
            "/save",
            "POST",
            {"enabled": True},
        )
    ]
    assert response["data"] == {"data": {"ok": True}, "error": None}


async def test_control_handler_install_plugin_streams_progress_and_reads_local_package(
    monkeypatch,
):
    handler, manager = _handler()
    file_ops = []

    async def fake_read_local_file(file_key):
        file_ops.append(("read", file_key))
        return b"package"

    async def fake_delete_local_file(file_key):
        file_ops.append(("delete", file_key))

    monkeypatch.setattr(handler, "read_local_file", fake_read_local_file)
    monkeypatch.setattr(handler, "delete_local_file", fake_delete_local_file)

    async with ProtocolSession(handler) as session:
        responses = await session.request_messages(
            LangBotToRuntimeAction.INSTALL_PLUGIN.value,
            {
                "install_source": "local",
                "install_info": {
                    "plugin_file_key": "pkg-key",
                    "workspace_uuid": "workspace-forged",
                    "instance_uuid": "instance-forged",
                    "placement_generation": 999,
                    "installation_uuid": "installation-forged",
                },
            },
            count=4,
        )

    assert file_ops == [("read", "pkg-key"), ("delete", "pkg-key")]
    assert manager.calls == [
        (
            "install_plugin",
            "local",
            {"plugin_file_key": "pkg-key", "plugin_file": b"package"},
        )
    ]
    assert [response["chunk_status"] for response in responses] == [
        "continue",
        "continue",
        "continue",
        "end",
    ]
    assert [response["data"] for response in responses] == [
        {"current_action": "downloaded"},
        {"current_action": "mounted"},
        {"current_action": "plugin installed"},
        {},
    ]


async def test_control_handler_install_plugin_marketplace_does_not_read_local_file():
    handler, manager = _handler()

    async with ProtocolSession(handler) as session:
        responses = await session.request_messages(
            LangBotToRuntimeAction.INSTALL_PLUGIN.value,
            {
                "install_source": "marketplace",
                "install_info": {
                    "plugin_author": "tester",
                    "plugin_name": "demo",
                    "plugin_version": "1.0.0",
                },
            },
            count=4,
        )

    assert manager.calls == [
        (
            "install_plugin",
            "marketplace",
            {
                "plugin_author": "tester",
                "plugin_name": "demo",
                "plugin_version": "1.0.0",
            },
        )
    ]
    assert [response["data"] for response in responses] == [
        {"current_action": "downloaded"},
        {"current_action": "mounted"},
        {"current_action": "plugin installed"},
        {},
    ]


async def test_status_reads_remain_available_during_plugin_apply(monkeypatch):
    """A long desired-state apply must not serialize unrelated status reads."""

    handler, manager = _handler()
    install_started = asyncio.Event()
    release_install = asyncio.Event()

    async def slow_apply(
        binding,
        *,
        artifact_package=None,
        enabled=True,
    ):
        del binding, artifact_package, enabled
        install_started.set()
        await release_install.wait()
        return {"installation_uuid": "installation-1", "state": "starting"}

    monkeypatch.setattr(manager, "apply_plugin_installation", slow_apply)

    async with ProtocolSession(handler) as session:
        await session.connection.send_peer_request(
            LangBotToRuntimeAction.APPLY_PLUGIN_INSTALLATION.value,
            {"enabled": True},
            seq_id=41,
            action_context=TEST_INSTALLATION_BINDING,
        )
        try:
            await asyncio.wait_for(install_started.wait(), timeout=1)

            ping_response = await asyncio.wait_for(
                session.request(
                    CommonAction.PING.value,
                    seq_id=42,
                    action_context=None,
                ),
                timeout=0.5,
            )
            list_response = await asyncio.wait_for(
                session.request(
                    LangBotToRuntimeAction.LIST_PLUGINS.value,
                    seq_id=43,
                ),
                timeout=0.5,
            )

            assert ping_response["seq_id"] == 42
            assert ping_response["code"] == 0
            assert list_response["seq_id"] == 43
            assert list_response["code"] == 0
            assert len(list_response["data"]["plugins"]) == 1
        finally:
            release_install.set()


async def test_shared_control_handler_rejects_legacy_plugin_lifecycle_before_io(
    monkeypatch,
):
    handler, manager = _handler(runtime_config=TEST_SHARED_RUNTIME_CONFIG)
    file_ops = []

    async def fake_read_local_file(file_key):
        file_ops.append(("read", file_key))
        return b"package"

    monkeypatch.setattr(handler, "read_local_file", fake_read_local_file)

    requests = [
        (
            LangBotToRuntimeAction.INSTALL_PLUGIN,
            {
                "install_source": "local",
                "install_info": {"plugin_file_key": "pkg-key"},
            },
        ),
        *(
            (
                action,
                {"plugin_author": "tester", "plugin_name": "demo"},
            )
            for action in (
                LangBotToRuntimeAction.RESTART_PLUGIN,
                LangBotToRuntimeAction.DELETE_PLUGIN,
                LangBotToRuntimeAction.UPGRADE_PLUGIN,
            )
        ),
    ]

    async with ProtocolSession(handler) as session:
        responses = [
            await session.request(action.value, data, seq_id=index)
            for index, (action, data) in enumerate(requests, start=1)
        ]

    assert all(response["code"] == 1 for response in responses)
    assert all(
        "unavailable in the shared Runtime profile" in response["message"]
        for response in responses
    )
    assert file_ops == []
    assert manager.calls == []


@pytest.mark.parametrize(
    ("action", "expected_call", "terminal_action"),
    [
        (
            LangBotToRuntimeAction.RESTART_PLUGIN,
            "restart_plugin",
            "plugin restarted",
        ),
        (
            LangBotToRuntimeAction.DELETE_PLUGIN,
            "delete_plugin",
            "plugin removed",
        ),
        (
            LangBotToRuntimeAction.UPGRADE_PLUGIN,
            "upgrade_plugin",
            "plugin upgraded",
        ),
    ],
)
async def test_control_handler_plugin_lifecycle_actions_stream_progress(
    action,
    expected_call,
    terminal_action,
):
    handler, manager = _handler()

    async with ProtocolSession(handler) as session:
        responses = await session.request_messages(
            action.value,
            {"plugin_author": "tester", "plugin_name": "demo"},
            count=3,
        )

    assert manager.calls == [(expected_call, "tester", "demo")]
    assert responses[-2]["data"] == {"current_action": terminal_action}
    assert responses[-1]["chunk_status"] == "end"


async def test_control_handler_emit_event_delegates_and_serializes_result():
    handler, manager = _handler()

    async with ProtocolSession(handler) as session:
        response = await session.request(
            LangBotToRuntimeAction.EMIT_EVENT.value,
            {
                "include_plugins": ["tester/demo"],
                "event_context": {
                    "query_id": 12,
                    "event_name": "PersonCommandSent",
                    "event": {
                        "event_name": "PersonCommandSent",
                        "launcher_type": "person",
                        "launcher_id": "launcher",
                        "sender_id": "sender",
                        "command": "demo",
                        "params": [],
                        "text_message": "/demo",
                        "is_admin": False,
                    },
                },
            },
        )

    call_name, event_context, include_plugins = manager.calls[0]
    assert call_name == "emit_event"
    assert isinstance(event_context, EventContext)
    assert include_plugins == ["tester/demo"]
    assert response["data"]["emitted_plugins"] == [
        {"manifest": {"author": "tester", "name": "demo"}}
    ]
    assert response["data"]["response_sources"] == [
        {
            "kind": "reply_message_chain",
            "plugin": {"author": "tester", "name": "demo"},
        }
    ]
    assert response["data"]["event_context"]["is_prevent_postorder"] is True


async def test_control_handler_parse_document_reads_transferred_file(monkeypatch):
    handler, manager = _handler()
    file_ops = []

    async def fake_read_local_file(file_key):
        file_ops.append(("read", file_key))
        return b"document"

    async def fake_delete_local_file(file_key):
        file_ops.append(("delete", file_key))

    monkeypatch.setattr(handler, "read_local_file", fake_read_local_file)
    monkeypatch.setattr(handler, "delete_local_file", fake_delete_local_file)

    async with ProtocolSession(handler) as session:
        response = await session.request(
            LangBotToRuntimeAction.PARSE_DOCUMENT.value,
            {
                "plugin_author": "tester",
                "plugin_name": "demo",
                "context": {"file_key": "file-key", "mime_type": "text/plain"},
            },
        )

    assert file_ops == [("read", "file-key"), ("delete", "file-key")]
    assert manager.calls == [
        (
            "parse_document",
            "tester",
            "demo",
            {"mime_type": "text/plain"},
            b"document",
        )
    ]
    assert response["data"] == {"text": "parsed"}


async def test_control_handler_parse_document_without_file_key_uses_empty_bytes():
    handler, manager = _handler()

    async with ProtocolSession(handler) as session:
        response = await session.request(
            LangBotToRuntimeAction.PARSE_DOCUMENT.value,
            {
                "plugin_author": "tester",
                "plugin_name": "demo",
                "context": {"mime_type": "text/plain"},
            },
        )

    assert manager.calls == [
        (
            "parse_document",
            "tester",
            "demo",
            {"mime_type": "text/plain"},
            b"",
        )
    ]
    assert response["data"] == {"text": "parsed"}


async def test_control_handler_lists_tools_and_commands_with_include_filter():
    handler, manager = _handler()

    async with ProtocolSession(handler) as session:
        tools = await session.request(
            LangBotToRuntimeAction.LIST_TOOLS.value,
            {"include_plugins": ["tester/demo"]},
            seq_id=1,
        )
        commands = await session.request(
            LangBotToRuntimeAction.LIST_COMMANDS.value,
            {"include_plugins": ["tester/demo"]},
            seq_id=2,
        )

    assert tools["data"] == {"tools": [{"name": "weather"}]}
    assert commands["data"] == {"commands": [{"name": "start"}]}
    assert manager.calls == [
        ("list_tools", ["tester/demo"]),
        ("list_commands", ["tester/demo"]),
    ]


async def test_control_handler_execute_command_streams_command_returns():
    handler, manager = _handler()

    async with ProtocolSession(handler) as session:
        responses = await session.request_messages(
            LangBotToRuntimeAction.EXECUTE_COMMAND.value,
            {
                "include_plugins": ["tester/demo"],
                "command_context": {
                    "query_id": 7,
                    "session": {
                        "launcher_type": "person",
                        "launcher_id": "launcher",
                        "sender_id": "sender",
                    },
                    "command_text": "start now",
                    "full_command_text": "/start now",
                    "command": "start",
                    "crt_command": "start",
                    "params": ["now"],
                    "crt_params": ["now"],
                    "privilege": 0,
                },
            },
            count=2,
        )

    call_name, command_context, include_plugins = manager.calls[0]
    assert call_name == "execute_command"
    assert command_context.command == "start"
    assert include_plugins == ["tester/demo"]
    assert responses[0]["data"] == {"text": "start"}
    assert responses[1]["chunk_status"] == "end"


async def test_control_handler_call_tool_delegates_session_and_query_context():
    handler, manager = _handler()

    async with ProtocolSession(handler) as session:
        response = await session.request(
            LangBotToRuntimeAction.CALL_TOOL.value,
            {
                "tool_name": "weather",
                "tool_parameters": {"city": "Shanghai"},
                "session": {"id": "s"},
                "query_id": 7,
                "query_uuid": "query-opaque-7",
                "include_plugins": ["tester/demo"],
            },
        )

    assert response["data"] == {"tool_response": {"text": "sunny"}}
    assert manager.calls == [
        (
            "call_tool",
            "weather",
            {"city": "Shanghai"},
            {
                "id": "s",
                "instance_uuid": "instance-1",
                "workspace_uuid": "workspace-a",
                "placement_generation": 4,
            },
            7,
            ["tester/demo"],
            "query-opaque-7",
        )
    ]


async def test_control_handler_rag_and_parser_discovery_actions():
    handler, manager = _handler()

    async with ProtocolSession(handler) as session:
        engines = await session.request(
            LangBotToRuntimeAction.LIST_KNOWLEDGE_ENGINES.value,
            seq_id=1,
        )
        parsers = await session.request(
            LangBotToRuntimeAction.LIST_PARSERS.value,
            seq_id=2,
        )

    assert engines["data"] == {"engines": [{"name": "rag"}]}
    assert parsers["data"] == {"parsers": [{"name": "parser"}]}
    assert manager.calls == [("list_knowledge_engines",), ("list_parsers",)]


async def test_control_handler_rag_ingest_document_delegates_context():
    handler, manager = _handler()

    async with ProtocolSession(handler) as session:
        response = await session.request(
            LangBotToRuntimeAction.RAG_INGEST_DOCUMENT.value,
            {
                "plugin_author": "tester",
                "plugin_name": "demo",
                "context": {"document_id": "doc"},
            },
        )

    assert response["data"] == {"document_id": "doc"}
    assert manager.calls == [
        (
            "rag_ingest_document",
            "tester",
            "demo",
            {"document_id": "doc"},
        )
    ]


async def test_control_handler_retrieve_knowledge_delegates_context():
    handler, manager = _handler()

    async with ProtocolSession(handler) as session:
        response = await session.request(
            LangBotToRuntimeAction.RETRIEVE_KNOWLEDGE.value,
            {
                "plugin_author": "tester",
                "plugin_name": "demo",
                "retriever_name": "kb",
                "retrieval_context": {"query": "hello"},
            },
        )

    assert response["data"] == {"results": [{"id": "r1"}]}
    assert manager.calls == [
        (
            "retrieve_knowledge",
            "tester",
            "demo",
            "kb",
            {"query": "hello"},
        )
    ]


@pytest.mark.parametrize(
    ("action", "payload", "expected_call", "expected_response"),
    [
        (
            LangBotToRuntimeAction.RAG_DELETE_DOCUMENT,
            {
                "plugin_author": "tester",
                "plugin_name": "demo",
                "kb_id": "kb-1",
                "document_id": "doc-1",
            },
            ("rag_delete_document", "tester", "demo", "kb-1", "doc-1"),
            {"deleted": "doc-1"},
        ),
        (
            LangBotToRuntimeAction.RAG_ON_KB_CREATE,
            {
                "plugin_author": "tester",
                "plugin_name": "demo",
                "kb_id": "kb-1",
                "config": {"top_k": 3},
            },
            ("rag_on_kb_create", "tester", "demo", "kb-1", {"top_k": 3}),
            {"created": "kb-1"},
        ),
        (
            LangBotToRuntimeAction.RAG_ON_KB_DELETE,
            {
                "plugin_author": "tester",
                "plugin_name": "demo",
                "kb_id": "kb-1",
            },
            ("rag_on_kb_delete", "tester", "demo", "kb-1"),
            {"deleted_kb": "kb-1"},
        ),
        (
            LangBotToRuntimeAction.GET_RAG_CREATION_SETTINGS_SCHEMA,
            {"plugin_author": "tester", "plugin_name": "demo"},
            ("get_rag_creation_schema", "tester", "demo"),
            {"schema": [{"name": "api_key"}]},
        ),
        (
            LangBotToRuntimeAction.GET_RAG_RETRIEVAL_SETTINGS_SCHEMA,
            {"plugin_author": "tester", "plugin_name": "demo"},
            ("get_rag_retrieval_schema", "tester", "demo"),
            {"schema": [{"name": "top_k"}]},
        ),
    ],
)
async def test_control_handler_rag_actions_delegate_to_plugin_manager(
    action,
    payload,
    expected_call,
    expected_response,
):
    handler, manager = _handler()

    async with ProtocolSession(handler) as session:
        response = await session.request(action.value, payload)

    assert response["data"] == expected_response
    assert manager.calls == [expected_call]


def _batch_event_data(bindings):
    return {
        "installation_bindings": [binding.model_dump() for binding in bindings],
        "event_context": {
            "query_id": 12,
            "event_name": "PersonCommandSent",
            "event": {
                "event_name": "PersonCommandSent",
                "launcher_type": "person",
                "launcher_id": "launcher",
                "sender_id": "sender",
                "command": "demo",
                "params": [],
                "text_message": "/demo",
                "is_admin": False,
            },
        },
    }


def _batch_handler():
    handler, manager = _handler(runtime_config=TEST_SHARED_RUNTIME_CONFIG)
    first = TEST_INSTALLATION_BINDING
    second = first.model_copy(update={"installation_uuid": "installation-2"})
    for binding in [first, second]:
        handler.context.activate_installation_binding(binding)
    return handler, manager, first, second


@pytest.mark.parametrize(
    "invalid",
    [
        "workspace",
        "instance",
        "generation",
        "revision",
        "artifact",
        "unknown",
        "duplicate",
        "first",
        "empty",
    ],
)
async def test_event_batch_rejects_invalid_authority_before_dispatch(invalid):
    handler, manager, first, second = _batch_handler()
    changes = {
        "workspace": {"workspace_uuid": "other"},
        "instance": {"instance_uuid": "other"},
        "generation": {"placement_generation": 5},
        "revision": {"runtime_revision": 3},
        "artifact": {"artifact_digest": "b" * 64},
        "unknown": {"installation_uuid": "unknown"},
    }
    bindings = [first, second.model_copy(update=changes.get(invalid, {}))]
    if invalid == "duplicate":
        bindings = [first, first]
    elif invalid == "first":
        bindings = [second, first]
    elif invalid == "empty":
        bindings = []
    async with ProtocolSession(handler) as session:
        response = await session.request(
            LangBotToRuntimeAction.EMIT_EVENT.value, _batch_event_data(bindings)
        )
    assert response["code"] != 0
    assert manager.calls == []
    assert handler.current_action_context is None


@pytest.mark.parametrize(
    "transition", ["revoke", "replace", "raise", "cancel", "stop", "continue"]
)
async def test_event_batch_scope_chain_and_lifecycle(transition):
    handler, manager, first, second = _batch_handler()
    calls = []

    async def emit(event, include_plugins):
        calls.append(handler.current_action_context)
        if len(calls) == 1:
            event.event.text_message += ":first"
            if transition == "revoke":
                handler.context.deactivate_installation_binding(second)
            elif transition == "replace":
                handler._invalidated = True
            elif transition == "raise":
                raise ValueError("listener failed")
            elif transition == "cancel":
                raise asyncio.CancelledError()
            elif transition == "stop":
                event.prevent_postorder()
            await asyncio.sleep(0)
        else:
            assert event.event.text_message == "/demo:first"
            event.event.text_message += ":second"
        return [FakePlugin(name=str(len(calls)))], event, [{"step": len(calls)}]

    manager.emit_event = emit
    # Call the registered action with its validated envelope to inspect reset even on cancellation.
    token = handler._current_action_context.set(first)
    try:
        action = handler.actions[LangBotToRuntimeAction.EMIT_EVENT.value]
        if transition in {"revoke", "replace", "raise", "cancel"}:
            error = asyncio.CancelledError if transition == "cancel" else ValueError
            with pytest.raises(error):
                await action(_batch_event_data([first, second]))
        else:
            response = await action(_batch_event_data([first, second]))
            expected = (
                "/demo:first:second" if transition == "continue" else "/demo:first"
            )
            assert response.data["event_context"]["event"]["text_message"] == expected
            assert response.data["response_sources"] == [
                {"step": i + 1} for i in range(len(calls))
            ]
        assert handler.current_action_context == first
        assert calls == ([first, second] if transition == "continue" else [first])
    finally:
        handler._current_action_context.reset(token)
