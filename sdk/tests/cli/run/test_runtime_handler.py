from __future__ import annotations

import asyncio
import logging
from types import SimpleNamespace

import pytest

from langbot_plugin.api.definition.components.base import NoneComponent
from langbot_plugin.api.definition.components.knowledge_engine.engine import (
    KnowledgeEngine,
)
from langbot_plugin.api.definition.components.page import Page, PageRequest
from langbot_plugin.api.definition.components.parser.parser import Parser
from langbot_plugin.api.definition.components.tool.tool import Tool
from langbot_plugin.api.entities.builtin.rag.context import (
    RetrievalResponse,
    RetrievalResultEntry,
)
from langbot_plugin.api.entities.builtin.rag.enums import DocumentStatus
from langbot_plugin.api.entities.builtin.rag.models import (
    IngestionResult,
    ParseResult,
)
from langbot_plugin.api.entities.builtin.provider.message import ContentElement
import langbot_plugin.cli.run.handler as runtime_handler_module
from langbot_plugin.cli.run.handler import (
    PluginRuntimeHandler,
    _read_runtime_ui_file_limited,
    _resolve_asset_path,
)
from langbot_plugin.entities.io.actions.enums import RuntimeToPluginAction
from langbot_plugin.entities.io.context import ActionContext, InstallationBinding

from tests.helpers.protocol import ProtocolConnection, ProtocolSession


class FakeManifest:
    def __init__(
        self,
        kind: str = "Plugin",
        name: str = "demo",
        component_class=None,
    ):
        self.kind = kind
        self.metadata = SimpleNamespace(name=name)
        self.icon_rel_path = None
        self._component_class = component_class

    def model_dump(self, **kwargs):
        return {
            "kind": self.kind,
            "metadata": {"name": self.metadata.name},
        }

    def get_python_component_class(self):
        if self._component_class is None:
            raise AssertionError("component class not configured")
        return self._component_class


class FakePluginContainer:
    def __init__(self):
        self.manifest = FakeManifest()
        self.components = []

    def model_dump(self, **kwargs):
        return {
            "manifest": self.manifest.model_dump(),
            "components": [
                component.manifest.model_dump() for component in self.components
            ],
        }


class FakeComponentContainer:
    def __init__(
        self,
        kind: str,
        name: str,
        component_instance,
        component_class=None,
    ):
        self.manifest = FakeManifest(
            kind=kind,
            name=name,
            component_class=component_class,
        )
        self.component_instance = component_instance


class FakePage(Page):
    def __init__(self):
        self.requests = []

    async def handle_api(self, request: PageRequest):
        self.requests.append(request)
        return {"endpoint": request.endpoint, "body": request.body}


class FakeTool(Tool):
    def __init__(self):
        self.calls = []

    async def call(self, params, session, query_id, query_uuid=None):
        self.calls.append((params, session, query_id, query_uuid))
        return {
            "ok": True,
            "sender_id": session.sender_id,
            "query_id": query_id,
            "query_uuid": query_uuid,
        }


class SimpleTool(Tool):
    async def call(self, params):
        return {"ok": True, "params": params}


class FakeKnowledgeEngine(KnowledgeEngine):
    def __init__(self):
        self.created = []
        self.deleted = []

    @classmethod
    def get_capabilities(cls):
        return ["doc_ingestion", "doc_parsing"]

    async def ingest(self, context):
        return IngestionResult(
            document_id=context.file_object.metadata.document_id,
            status=DocumentStatus.COMPLETED,
            chunks_created=2,
            metadata={"collection_id": context.get_collection_id()},
        )

    async def delete_document(self, kb_id: str, document_id: str) -> bool:
        self.deleted.append((kb_id, document_id))
        return True

    async def retrieve(self, context):
        return RetrievalResponse(
            results=[
                RetrievalResultEntry(
                    id="chunk-1",
                    content=[ContentElement.from_text(f"answer:{context.query}")],
                    metadata={"kb": context.get_collection_id()},
                    distance=0.1,
                    score=0.9,
                )
            ],
            total_found=1,
        )

    async def on_knowledge_base_create(self, kb_id: str, config: dict) -> None:
        self.created.append((kb_id, config))

    async def on_knowledge_base_delete(self, kb_id: str) -> None:
        self.deleted.append((kb_id, None))


class FakeParser(Parser):
    async def parse(self, context):
        return ParseResult(
            text=context.file_content.decode() or context.filename,
            metadata={"mime_type": context.mime_type},
        )


def _handler():
    initialized = []

    async def initialize(plugin_settings):
        initialized.append(plugin_settings)

    handler = PluginRuntimeHandler(ProtocolConnection(), initialize)
    handler.plugin_container = FakePluginContainer()
    return handler, initialized


async def test_worker_ping_responds_without_plugin_initialization():
    handler, initialized = _handler()
    async with ProtocolSession(handler) as session:
        result = await session.request("__ping", {}, seq_id=1)
        assert result["code"] == 0
    assert initialized == []


def test_resolve_asset_path_accepts_assets_and_component_page_files(
    tmp_path, monkeypatch
):
    assets_file = tmp_path / "assets" / "icon.svg"
    page_file = tmp_path / "components" / "pages" / "settings.html"
    outside_file = tmp_path / "components" / "tools" / "secret.txt"
    assets_file.parent.mkdir()
    page_file.parent.mkdir(parents=True)
    outside_file.parent.mkdir(parents=True)
    assets_file.write_text("icon", encoding="utf-8")
    page_file.write_text("page", encoding="utf-8")
    outside_file.write_text("secret", encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    assert _resolve_asset_path("icon.svg") == assets_file.resolve()
    assert _resolve_asset_path("components/pages/settings.html") == page_file.resolve()
    assert _resolve_asset_path("components/tools/secret.txt") is None
    assert _resolve_asset_path(str(assets_file.resolve())) is None


async def test_runtime_ui_file_read_is_bounded(tmp_path, monkeypatch):
    monkeypatch.setattr(runtime_handler_module, "MAX_RUNTIME_UI_FILE_BYTES", 4)
    asset = tmp_path / "large.bin"
    asset.write_bytes(b"12345")

    with pytest.raises(ValueError, match="Plugin UI file exceeds"):
        await _read_runtime_ui_file_limited(asset)


async def test_plugin_runtime_handler_initializes_plugin_and_returns_container():
    handler, initialized = _handler()

    async with ProtocolSession(handler) as session:
        initialized_response = await session.request(
            RuntimeToPluginAction.INITIALIZE_PLUGIN.value,
            {"plugin_settings": {"enabled": True}},
            seq_id=1,
        )
        container_response = await session.request(
            RuntimeToPluginAction.GET_PLUGIN_CONTAINER.value,
            seq_id=2,
        )

    assert initialized_response["code"] == 0
    assert initialized == [{"enabled": True}]
    assert container_response["data"] == {
        "manifest": {"kind": "Plugin", "metadata": {"name": "demo"}},
        "components": [],
    }


async def test_plugin_registration_separates_debug_key_and_prod_capability(
    monkeypatch,
):
    handler, _initialized = _handler()
    calls = []
    monkeypatch.setenv("PLUGIN_DEBUG_KEY", "explicit-debug-key")

    async def fake_call_action(action, data, **_kwargs):
        calls.append((action, data))
        return {"ok": True}

    monkeypatch.setattr(handler, "call_action", fake_call_action)

    await handler.register_plugin(prod_mode=False)
    await handler.register_plugin(
        prod_mode=True,
        registration_capability="one-use-capability",
    )

    assert calls[0][1]["plugin_debug_key"] == "explicit-debug-key"
    assert calls[0][1]["registration_capability"] == ""
    assert calls[1][1]["plugin_debug_key"] == ""
    assert calls[1][1]["registration_capability"] == "one-use-capability"


async def test_plugin_runtime_handler_binds_context_from_initialize_envelope():
    handler, initialized = _handler()
    action_context = ActionContext(
        instance_uuid="instance-1",
        workspace_uuid="workspace-a",
        placement_generation=2,
        installation_uuid="installation-1",
    )

    async with ProtocolSession(handler) as session:
        response = await session.request(
            RuntimeToPluginAction.INITIALIZE_PLUGIN.value,
            {"plugin_settings": {"enabled": True}},
            action_context=action_context,
        )

    assert response["code"] == 0
    assert initialized == [{"enabled": True}]
    assert handler.bound_action_context == action_context


async def test_dedicated_initialize_uses_bound_installation_without_shared_slot():
    from langbot_plugin.api.proxies.invocation import invocation_capability

    handler, initialized = _handler()
    binding = InstallationBinding(
        instance_uuid="instance-1",
        workspace_uuid="workspace-a",
        placement_generation=2,
        installation_uuid="dedicated-1",
        runtime_revision=1,
        artifact_digest="a" * 64,
    )
    handler.plugin_container.plugin_config = {"dedicated": True}
    assert handler.bound_action_context is None
    with handler.action_invocation_scope(
        RuntimeToPluginAction.INITIALIZE_PLUGIN.value, binding
    ):
        assert handler.bound_action_context == binding
        capability = invocation_capability(handler)
        assert capability is not None
        assert capability.binding == binding
    async with ProtocolSession(handler) as session:
        response = await session.request(
            RuntimeToPluginAction.INITIALIZE_PLUGIN.value,
            {"plugin_settings": {"enabled": True}},
            action_context=binding,
        )
    assert response["code"] == 0
    assert initialized == [{"enabled": True}]
    assert handler._slot_containers == {}


async def test_unattached_shared_slot_remains_rejected():
    handler, _initialized = _handler()
    binding = InstallationBinding(
        instance_uuid="instance-1",
        workspace_uuid="workspace-a",
        placement_generation=2,
        installation_uuid="shared-1",
        runtime_revision=1,
        artifact_digest="a" * 64,
    )
    handler.bind_action_context(
        InstallationBinding(
            instance_uuid="instance-1",
            workspace_uuid="workspace-a",
            placement_generation=2,
            installation_uuid="dedicated-1",
            runtime_revision=1,
            artifact_digest="a" * 64,
        )
    )
    with pytest.raises(ValueError, match="Shared plugin slot is not attached"):
        with handler.action_invocation_scope(
            RuntimeToPluginAction.GET_PLUGIN_SLOT_CONTAINER.value, binding
        ):
            pass


async def test_attach_scope_revokes_authority_copied_by_initialize_task():
    from langbot_plugin.api.proxies.invocation import invocation_capability

    handler, _initialized = _handler()
    binding = InstallationBinding(
        instance_uuid="instance-1",
        workspace_uuid="workspace-a",
        placement_generation=2,
        installation_uuid="installation-1",
        runtime_revision=1,
        artifact_digest="a" * 64,
    )
    release = asyncio.Event()
    outcomes = []

    async def escaped():
        await release.wait()
        try:
            invocation_capability(handler)
        except RuntimeError as exc:
            outcomes.append(str(exc))

    with handler.action_invocation_scope(
        RuntimeToPluginAction.ATTACH_PLUGIN_SLOT.value,
        binding,
    ):
        task = asyncio.create_task(escaped())

    release.set()
    await task
    assert outcomes == ["Plugin invocation has ended"]


async def test_plugin_runtime_handler_icon_without_icon_path_returns_empty_payload():
    handler, _initialized = _handler()

    async with ProtocolSession(handler) as session:
        response = await session.request(RuntimeToPluginAction.GET_PLUGIN_ICON.value)

    assert response["data"] == {"plugin_icon_file_key": "", "mime_type": ""}


async def test_plugin_runtime_handler_sends_readme_file_key(tmp_path, monkeypatch):
    handler, _initialized = _handler()
    (tmp_path / "readme").mkdir()
    (tmp_path / "readme" / "README_zh.md").write_bytes(b"zh readme")
    monkeypatch.chdir(tmp_path)
    sent = []

    async def fake_send_file(file_bytes, extension):
        sent.append((file_bytes, extension))
        return "readme-key"

    monkeypatch.setattr(handler, "send_file", fake_send_file)

    async with ProtocolSession(handler) as session:
        response = await session.request(
            RuntimeToPluginAction.GET_PLUGIN_README.value,
            {"language": "zh"},
        )

    assert sent == [(b"zh readme", "md")]
    assert response["data"] == {
        "plugin_readme_file_key": "readme-key",
        "mime_type": "text/markdown",
    }


async def test_plugin_runtime_handler_get_assets_file_rejects_path_traversal(
    tmp_path,
    monkeypatch,
):
    handler, _initialized = _handler()
    outside = tmp_path / "secret.txt"
    outside.write_text("secret", encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    async with ProtocolSession(handler) as session:
        response = await session.request(
            RuntimeToPluginAction.GET_PLUGIN_ASSETS_FILE.value,
            {"file_key": "../secret.txt"},
        )

    assert response["data"] == {"file_file_key": None, "mime_type": None}


async def test_plugin_runtime_handler_get_assets_file_sends_allowed_asset(
    tmp_path,
    monkeypatch,
):
    handler, _initialized = _handler()
    asset = tmp_path / "assets" / "config.json"
    asset.parent.mkdir()
    asset.write_bytes(b'{"ok": true}')
    monkeypatch.chdir(tmp_path)
    sent = []

    async def fake_send_file(file_bytes, extension):
        sent.append((file_bytes, extension))
        return "asset-key"

    monkeypatch.setattr(handler, "send_file", fake_send_file)

    async with ProtocolSession(handler) as session:
        response = await session.request(
            RuntimeToPluginAction.GET_PLUGIN_ASSETS_FILE.value,
            {"file_key": "config.json"},
        )

    assert sent == [(b'{"ok": true}', "")]
    assert response["data"] == {
        "file_file_key": "asset-key",
        "mime_type": "application/json",
    }


async def test_plugin_runtime_handler_page_api_reports_missing_and_uninitialized_page():
    handler, _initialized = _handler()
    handler.plugin_container.components = [
        FakeComponentContainer(Page.__kind__, "settings", NoneComponent())
    ]

    async with ProtocolSession(handler) as session:
        missing_page_id = await session.request(
            RuntimeToPluginAction.PAGE_API.value,
            {},
            seq_id=1,
        )
        uninitialized = await session.request(
            RuntimeToPluginAction.PAGE_API.value,
            {"page_id": "settings"},
            seq_id=2,
        )
        missing = await session.request(
            RuntimeToPluginAction.PAGE_API.value,
            {"page_id": "missing"},
            seq_id=3,
        )

    assert missing_page_id["data"] == {
        "data": None,
        "error": "page_id is required",
    }
    assert uninitialized["data"] == {
        "data": None,
        "error": "Page component is not initialized",
    }
    assert missing["data"] == {"data": None, "error": "Page 'missing' not found"}


async def test_plugin_runtime_handler_page_api_invokes_page_component():
    handler, _initialized = _handler()
    page = FakePage()
    handler.plugin_container.components = [
        FakeComponentContainer(Page.__kind__, "settings", page)
    ]

    async with ProtocolSession(handler) as session:
        response = await session.request(
            RuntimeToPluginAction.PAGE_API.value,
            {
                "page_id": "settings",
                "endpoint": "/save",
                "method": "PUT",
                "body": {"enabled": True},
            },
        )

    assert response["data"] == {
        "data": {"endpoint": "/save", "body": {"enabled": True}},
        "error": None,
    }
    assert page.requests[0].method == "PUT"


async def test_plugin_runtime_handler_call_tool_invokes_matching_tool_component():
    handler, _initialized = _handler()
    tool = FakeTool()
    handler.plugin_container.components = [
        FakeComponentContainer(Tool.__kind__, "weather", tool)
    ]

    async with ProtocolSession(handler) as session:
        response = await session.request(
            RuntimeToPluginAction.CALL_TOOL.value,
            {
                "tool_name": "weather",
                "tool_parameters": {"city": "Shanghai"},
                "session": {
                    "launcher_type": "person",
                    "launcher_id": "launcher",
                    "sender_id": "sender",
                },
                "query_id": 7,
                "query_uuid": "query-opaque-7",
            },
        )

    assert response["data"] == {
        "tool_response": {
            "ok": True,
            "sender_id": "sender",
            "query_id": 7,
            "query_uuid": "query-opaque-7",
        }
    }
    assert tool.calls[0][0] == {"city": "Shanghai"}


async def test_plugin_runtime_handler_call_tool_reports_missing_or_uninitialized_tool():
    handler, _initialized = _handler()
    handler.plugin_container.components = [
        FakeComponentContainer(Tool.__kind__, "weather", NoneComponent())
    ]

    async with ProtocolSession(handler) as session:
        uninitialized = await session.request(
            RuntimeToPluginAction.CALL_TOOL.value,
            {
                "tool_name": "weather",
                "tool_parameters": {},
                "session": {
                    "launcher_type": "person",
                    "launcher_id": "launcher",
                    "sender_id": "sender",
                },
                "query_id": 1,
            },
            seq_id=1,
        )
        missing = await session.request(
            RuntimeToPluginAction.CALL_TOOL.value,
            {
                "tool_name": "missing",
                "tool_parameters": {},
                "session": {},
                "query_id": 1,
            },
            seq_id=2,
        )

    assert uninitialized["code"] == 1
    assert uninitialized["message"] == "Tool is not initialized"
    assert missing["code"] == 1
    assert missing["message"] == "Tool missing not found"


async def test_plugin_runtime_handler_call_tool_supports_simple_call_signature():
    handler, _initialized = _handler()
    handler.plugin_container.components = [
        FakeComponentContainer(Tool.__kind__, "simple", SimpleTool())
    ]

    async with ProtocolSession(handler) as session:
        response = await session.request(
            RuntimeToPluginAction.CALL_TOOL.value,
            {
                "tool_name": "simple",
                "tool_parameters": {"x": 1},
                "session": {},
                "query_id": 1,
            },
        )

    assert response["data"] == {"tool_response": {"ok": True, "params": {"x": 1}}}


async def test_plugin_runtime_handler_knowledge_engine_actions_succeed():
    handler, _initialized = _handler()
    engine = FakeKnowledgeEngine()
    handler.plugin_container.components = [
        FakeComponentContainer(
            KnowledgeEngine.__kind__,
            "kb",
            engine,
            component_class=FakeKnowledgeEngine,
        )
    ]

    async with ProtocolSession(handler) as session:
        retrieve = await session.request(
            RuntimeToPluginAction.RETRIEVE_KNOWLEDGE.value,
            {
                "retriever_name": "kb",
                "retrieval_context": {
                    "query": "hello",
                    "knowledge_base_id": "kb-1",
                },
            },
            seq_id=1,
        )
        ingest = await session.request(
            RuntimeToPluginAction.INGEST_DOCUMENT.value,
            {
                "context": {
                    "knowledge_base_id": "kb-1",
                    "file_object": {
                        "metadata": {
                            "filename": "a.md",
                            "file_size": 4,
                            "mime_type": "text/markdown",
                            "document_id": "doc-1",
                            "knowledge_base_id": "kb-1",
                        },
                        "storage_path": "files/doc-1",
                    },
                }
            },
            seq_id=2,
        )
        delete_doc = await session.request(
            RuntimeToPluginAction.DELETE_DOCUMENT.value,
            {"kb_id": "kb-1", "document_id": "doc-1"},
            seq_id=3,
        )
        create_kb = await session.request(
            RuntimeToPluginAction.ON_KB_CREATE.value,
            {"kb_id": "kb-2", "config": {"top_k": 3}},
            seq_id=4,
        )
        delete_kb = await session.request(
            RuntimeToPluginAction.ON_KB_DELETE.value,
            {"kb_id": "kb-2"},
            seq_id=5,
        )
        capabilities = await session.request(
            RuntimeToPluginAction.GET_RAG_CAPABILITIES.value,
            seq_id=6,
        )

    assert retrieve["data"]["total_found"] == 1
    assert retrieve["data"]["results"][0]["content"][0]["text"] == "answer:hello"
    assert ingest["data"]["document_id"] == "doc-1"
    assert ingest["data"]["chunks_created"] == 2
    assert delete_doc["data"] == {"success": True}
    assert create_kb["data"] == {"success": True}
    assert delete_kb["data"] == {"success": True}
    assert capabilities["data"] == {"capabilities": ["doc_ingestion", "doc_parsing"]}
    assert engine.created == [("kb-2", {"top_k": 3})]
    assert engine.deleted == [("kb-1", "doc-1"), ("kb-2", None)]


async def test_plugin_runtime_handler_knowledge_engine_reports_missing_states():
    handler, _initialized = _handler()

    async with ProtocolSession(handler) as session:
        missing = await session.request(
            RuntimeToPluginAction.RETRIEVE_KNOWLEDGE.value,
            {"retriever_name": "kb", "retrieval_context": {"query": "hello"}},
            seq_id=1,
        )
        missing_capabilities = await session.request(
            RuntimeToPluginAction.GET_RAG_CAPABILITIES.value,
            seq_id=2,
        )

    assert missing["code"] == 1
    assert missing["message"] == "KnowledgeEngine kb not found"
    assert missing_capabilities["code"] == 1
    assert (
        missing_capabilities["message"]
        == "KnowledgeEngine component not found in this plugin"
    )

    handler, _initialized = _handler()
    handler.plugin_container.components = [
        FakeComponentContainer(KnowledgeEngine.__kind__, "kb", NoneComponent())
    ]
    async with ProtocolSession(handler) as session:
        uninitialized = await session.request(
            RuntimeToPluginAction.INGEST_DOCUMENT.value,
            {
                "context": {
                    "knowledge_base_id": "kb-1",
                    "file_object": {
                        "metadata": {
                            "filename": "a.md",
                            "file_size": 4,
                            "mime_type": "text/markdown",
                            "document_id": "doc-1",
                            "knowledge_base_id": "kb-1",
                        },
                        "storage_path": "files/doc-1",
                    },
                }
            },
        )

    assert uninitialized["code"] == 1
    assert uninitialized["message"] == "KnowledgeEngine component is not initialized"


async def test_plugin_runtime_handler_parser_actions_succeed(tmp_path, monkeypatch):
    handler, _initialized = _handler()
    handler.plugin_container.components = [
        FakeComponentContainer(Parser.__kind__, "pdf", FakeParser())
    ]
    read_keys = []
    deleted_keys = []

    async def fake_read_local_file(file_key):
        read_keys.append(file_key)
        return b"parsed bytes"

    async def fake_delete_local_file(file_key):
        deleted_keys.append(file_key)

    monkeypatch.setattr(handler, "read_local_file", fake_read_local_file)
    monkeypatch.setattr(handler, "delete_local_file", fake_delete_local_file)

    async with ProtocolSession(handler) as session:
        response = await session.request(
            RuntimeToPluginAction.PARSE_DOCUMENT.value,
            {
                "context": {
                    "file_key": "file-key",
                    "mime_type": "application/pdf",
                    "filename": "a.pdf",
                    "metadata": {"page": 1},
                }
            },
        )

    assert response["data"] == {
        "text": "parsed bytes",
        "sections": [],
        "metadata": {"mime_type": "application/pdf"},
    }
    assert read_keys == ["file-key"]
    assert deleted_keys == ["file-key"]


async def test_plugin_runtime_handler_parser_reports_missing_states():
    handler, _initialized = _handler()

    async with ProtocolSession(handler) as session:
        missing = await session.request(
            RuntimeToPluginAction.PARSE_DOCUMENT.value,
            {"context": {"filename": "a.pdf"}},
            seq_id=1,
        )

    assert missing["code"] == 1
    assert missing["message"] == "Parser component not found in this plugin"

    handler, _initialized = _handler()
    handler.plugin_container.components = [
        FakeComponentContainer(Parser.__kind__, "pdf", NoneComponent())
    ]
    async with ProtocolSession(handler) as session:
        uninitialized = await session.request(
            RuntimeToPluginAction.PARSE_DOCUMENT.value,
            {"context": {"filename": "a.pdf"}},
            seq_id=2,
        )

    assert uninitialized["code"] == 1
    assert uninitialized["message"] == "Parser component is not initialized"


async def test_plugin_runtime_handler_shutdown_schedules_callback():
    handler, _initialized = _handler()
    called = asyncio.Event()

    async def shutdown():
        called.set()

    handler.shutdown_callback = shutdown

    async with ProtocolSession(handler) as session:
        response = await session.request(RuntimeToPluginAction.SHUTDOWN.value)
        await asyncio.wait_for(called.wait(), timeout=1)

    assert response["data"] == {}


async def test_plugin_runtime_handler_coalesces_shutdown_callbacks():
    handler, _initialized = _handler()
    started = 0
    entered = asyncio.Event()
    release = asyncio.Event()

    async def shutdown():
        nonlocal started
        started += 1
        entered.set()
        await release.wait()

    handler.shutdown_callback = shutdown

    async with ProtocolSession(handler) as session:
        await session.request(RuntimeToPluginAction.SHUTDOWN.value, seq_id=1)
        await asyncio.wait_for(entered.wait(), timeout=1)
        await session.request(RuntimeToPluginAction.SHUTDOWN.value, seq_id=2)
        assert started == 1
        release.set()
        await asyncio.wait_for(handler._shutdown_task, timeout=1)


async def test_plugin_runtime_handler_plugin_diagnostic_logs(caplog):
    handler, _initialized = _handler()
    caplog.set_level(logging.ERROR, logger="langbot_plugin.cli.run.handler")

    async with ProtocolSession(handler) as session:
        response = await session.request(
            RuntimeToPluginAction.PLUGIN_DIAGNOSTIC.value,
            {
                "level": "ERROR",
                "code": "deferred_response_delivery_failed",
                "message": "Deferred response delivery failed",
                "details": {
                    "query_id": 123,
                    "event_name": "GroupNormalMessageReceived",
                    "stage": "SendResponseBackStage",
                    "delivery_error": "ActionFailed: retcode=1200",
                },
            },
        )

    assert response["data"] == {}
    assert "[deferred_response_delivery_failed]" in caplog.text
    assert "query_id=123" in caplog.text
    assert "event=GroupNormalMessageReceived" in caplog.text
    assert "stage=SendResponseBackStage" in caplog.text
    assert "delivery_error=ActionFailed: retcode=1200" in caplog.text


@pytest.mark.parametrize("host_accepts_origin", [True, False])
async def test_event_listener_calls_carry_the_event_origin_only_while_handling(
    host_accepts_origin,
):
    from langbot_plugin.api.definition.components.common.event_listener import (
        EventListener,
    )
    from langbot_plugin.api.entities import events
    from langbot_plugin.api.proxies.invocation import current_event_origin

    seen: list[str | None] = []

    class Listener(EventListener):
        def __init__(self):
            super().__init__()

            @self.handler(events.PersonNormalMessageReceived)
            async def on_message(ctx):
                seen.append(current_event_origin())

    handler, _initialized = _handler()
    handler.plugin_container.components = [
        FakeComponentContainer(EventListener.__kind__, "events", Listener())
    ]
    event = {
        "event_name": "PersonNormalMessageReceived",
        "query_uuid": "query-opaque-9",
        "launcher_type": "person",
        "launcher_id": "launcher",
        "sender_id": "sender",
        "text_message": "hello",
        "message_chain": [{"type": "Plain", "text": "hello"}],
        "message_event": {
            "time": 0.0,
            "self_id": "bot",
            "sender": {"id": "sender", "nickname": "Sender", "remark": ""},
            "message_chain": [{"type": "Plain", "text": "hello"}],
        },
    }

    async with ProtocolSession(handler) as session:
        response = await session.request(
            RuntimeToPluginAction.EMIT_EVENT.value,
            {
                "event_context": {
                    "query_id": 9,
                    "query_uuid": "query-opaque-9",
                    "event_name": "PersonNormalMessageReceived",
                    "event": event,
                    **({"origin_attribution": True} if host_accepts_origin else {}),
                }
            },
        )

    assert response["data"]["emitted"] is True
    # Older Hosts never set the hint and must not receive an unknown field.
    assert seen == (["query-opaque-9"] if host_accepts_origin else [None])
    assert current_event_origin() is None
