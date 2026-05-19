"""Integration-style tests for AgentRunOrchestrator with a fake plugin runner."""
from __future__ import annotations

import asyncio
import datetime
import types
from unittest.mock import AsyncMock

import pytest

from langbot.pkg.agent.runner.descriptor import AgentRunnerDescriptor
from langbot.pkg.agent.runner.errors import RunnerExecutionError
from langbot.pkg.agent.runner.context_builder import AgentRunContextBuilder
from langbot.pkg.agent.runner.orchestrator import AgentRunOrchestrator
from langbot.pkg.agent.runner.session_registry import get_session_registry
from langbot.pkg.agent.runner.state_store import get_state_store, reset_state_store
from langbot_plugin.api.entities.builtin.platform import entities as platform_entities
from langbot_plugin.api.entities.builtin.platform import events as platform_events
from langbot_plugin.api.entities.builtin.platform import message as platform_message
from langbot_plugin.api.entities.builtin.provider import message as provider_message
from langbot_plugin.api.entities.builtin.provider import session as provider_session
from langbot_plugin.api.entities.builtin.resource import tool as resource_tool


RUNNER_ID = "plugin:langbot/local-agent/default"


class FakeLogger:
    def debug(self, msg):
        pass

    def info(self, msg):
        pass

    def warning(self, msg):
        pass

    def error(self, msg):
        pass


class FakeVersionManager:
    def get_current_version(self):
        return "test-version"


class FakeModel:
    def __init__(self, model_type: str = "chat"):
        self.model_entity = types.SimpleNamespace(model_type=model_type)
        self.provider_entity = types.SimpleNamespace(name="fake-provider")


class FakeKnowledgeBase:
    def __init__(self, kb_id: str):
        self.kb_id = kb_id
        self.knowledge_base_entity = types.SimpleNamespace(kb_type="fake")

    def get_name(self):
        return f"KB {self.kb_id}"


class FakePluginConnector:
    is_enable_plugin = True

    def __init__(self, results=None, error: Exception | None = None, delay: float = 0):
        self.results = results or []
        self.error = error
        self.delay = delay
        self.calls: list[dict] = []
        self.contexts: list[dict] = []
        self.sessions_during_run: list[dict | None] = []

    async def run_agent(self, plugin_author, plugin_name, runner_name, context):
        self.calls.append(
            {
                "plugin_author": plugin_author,
                "plugin_name": plugin_name,
                "runner_name": runner_name,
            }
        )
        self.contexts.append(context)
        self.sessions_during_run.append(await get_session_registry().get(context["run_id"]))

        if self.error:
            raise self.error

        for result in self.results:
            if self.delay:
                await asyncio.sleep(self.delay)
            yield result


class FakeRegistry:
    def __init__(self, descriptor: AgentRunnerDescriptor):
        self.descriptor = descriptor
        self.calls: list[dict] = []

    async def get(self, runner_id, bound_plugins=None):
        self.calls.append({"runner_id": runner_id, "bound_plugins": bound_plugins})
        assert runner_id == self.descriptor.id
        return self.descriptor


class FakeApplication:
    def __init__(self, plugin_connector: FakePluginConnector):
        self.logger = FakeLogger()
        self.ver_mgr = FakeVersionManager()
        self.plugin_connector = plugin_connector

        self.model_mgr = types.SimpleNamespace(
            get_model_by_uuid=AsyncMock(return_value=FakeModel())
        )
        self.rag_mgr = types.SimpleNamespace(
            get_knowledge_base_by_uuid=AsyncMock(return_value=FakeKnowledgeBase("kb_001"))
        )


class FakeConversation:
    uuid = "conv_existing"
    create_time = datetime.datetime(2026, 5, 15, 12, 0, 0)


def make_descriptor() -> AgentRunnerDescriptor:
    return AgentRunnerDescriptor(
        id=RUNNER_ID,
        source="plugin",
        label={"en_US": "Local Agent"},
        plugin_author="langbot",
        plugin_name="local-agent",
        runner_name="default",
        protocol_version="1",
        capabilities={"streaming": True, "tool_calling": True, "knowledge_retrieval": True},
        config_schema=[
            {"name": "model", "type": "model-fallback-selector"},
            {"name": "knowledge-bases", "type": "knowledge-base-multi-selector", "default": []},
        ],
        permissions={
            "models": ["invoke", "stream"],
            "tools": ["list", "detail", "call"],
            "knowledge_bases": ["list", "retrieve"],
            "storage": ["plugin"],
            "files": [],
        },
    )


def make_query():
    async def fake_func(**kwargs):
        return kwargs

    message_chain = platform_message.MessageChain(
        [
            platform_message.Source(
                id="msg_001",
                time=datetime.datetime(2026, 5, 15, 12, 0, 0),
            ),
            platform_message.Plain(text="hello"),
            platform_message.File(name="spec.txt", url="https://example.com/spec.txt"),
        ]
    )
    sender = platform_entities.Friend(id="user_001", nickname="Alice", remark=None)
    message_event = platform_events.FriendMessage(sender=sender, message_chain=message_chain, time=1_784_098_800.0)
    session = types.SimpleNamespace(
        launcher_type=provider_session.LauncherTypes.PERSON,
        launcher_id="user_001",
        sender_id="user_001",
        using_conversation=FakeConversation(),
    )

    return types.SimpleNamespace(
        query_id=1001,
        launcher_type=provider_session.LauncherTypes.PERSON,
        launcher_id="user_001",
        sender_id="user_001",
        message_event=message_event,
        message_chain=message_chain,
        bot_uuid="bot_001",
        pipeline_uuid="pipeline_001",
        pipeline_config={
            "ai": {
                "runner": {"id": RUNNER_ID},
                "runner_config": {
                    RUNNER_ID: {
                        "model": {"primary": "model_primary", "fallbacks": ["model_fallback"]},
                        "knowledge-bases": ["kb_001"],
                        "timeout": 30,
                    },
                },
            },
        },
        session=session,
        messages=[],
        user_message=provider_message.Message(
            role="user",
            content=[
                provider_message.ContentElement.from_text("hello"),
                provider_message.ContentElement.from_file_url("https://example.com/spec.txt", "spec.txt"),
            ],
        ),
        variables={
            "_pipeline_bound_plugins": ["langbot/local-agent"],
            "_fallback_model_uuids": ["model_fallback"],
            "public_param": "visible",
        },
        use_llm_model_uuid="model_primary",
        use_funcs=[
            resource_tool.LLMTool(
                name="langbot/test-tool/search",
                human_desc="Search",
                description="Search test data",
                parameters={"type": "object", "properties": {"q": {"type": "string"}}},
                func=fake_func,
            )
        ],
    )


def test_context_builder_includes_consumable_base64_attachments():
    builder = AgentRunContextBuilder(ap=types.SimpleNamespace())
    query = make_query()
    query.user_message = provider_message.Message(
        role="user",
        content=[
            provider_message.ContentElement.from_text("see attached"),
            provider_message.ContentElement.from_image_base64("data:image/png;base64,aGVsbG8="),
            provider_message.ContentElement.from_file_base64("data:text/plain;base64,aGVsbG8=", "hello.txt"),
        ],
    )
    query.message_chain = platform_message.MessageChain(
        [platform_message.Image(base64="data:image/jpeg;base64,aGVsbG8=")]
    )

    input_data = builder._build_input(query)
    attachments = input_data["attachments"]

    image_attachment = next(item for item in attachments if item["type"] == "image" and item["source"] == "base64")
    file_attachment = next(item for item in attachments if item["type"] == "file" and item["source"] == "base64")
    chain_attachment = next(item for item in attachments if item["source"] == "message_chain")

    assert image_attachment["content"] == "data:image/png;base64,aGVsbG8="
    assert image_attachment["content_type"] == "image/png"
    assert file_attachment["content"] == "data:text/plain;base64,aGVsbG8="
    assert file_attachment["content_type"] == "text/plain"
    assert file_attachment["name"] == "hello.txt"
    assert chain_attachment["content"] == "data:image/jpeg;base64,aGVsbG8="
    assert chain_attachment["content_type"] == "image/jpeg"


@pytest.fixture(autouse=True)
async def clean_agent_state():
    reset_state_store()
    registry = get_session_registry()
    for session in await registry.list_active_runs():
        await registry.unregister(session["run_id"])
    yield
    for session in await registry.list_active_runs():
        await registry.unregister(session["run_id"])
    reset_state_store()


@pytest.mark.asyncio
async def test_orchestrator_runs_fake_plugin_with_authorized_context():
    descriptor = make_descriptor()
    plugin_connector = FakePluginConnector(
        results=[
            {
                "type": "message.completed",
                "data": {"message": {"role": "assistant", "content": "fake response"}},
            }
        ]
    )
    ap = FakeApplication(plugin_connector)
    orchestrator = AgentRunOrchestrator(ap, FakeRegistry(descriptor))
    query = make_query()

    messages = [message async for message in orchestrator.run_from_query(query)]

    assert len(messages) == 1
    assert messages[0].content == "fake response"
    assert plugin_connector.calls == [
        {
            "plugin_author": "langbot",
            "plugin_name": "local-agent",
            "runner_name": "default",
        }
    ]

    context = plugin_connector.contexts[0]
    assert context["config"]["timeout"] == 30
    assert context["runtime"]["deadline_at"] is not None
    assert context["params"] == {"public_param": "visible"}
    assert context["event"]["event_type"] == "message.received"
    assert context["event"]["event_data"]["source_event_type"] == "FriendMessage"
    assert context["actor"]["actor_id"] == "user_001"
    assert context["actor"]["actor_name"] == "Alice"
    assert context["subject"]["subject_id"] == "msg_001"
    assert context["input"]["attachments"]

    resources = context["resources"]
    assert {m["model_id"] for m in resources["models"]} == {"model_primary", "model_fallback"}
    assert resources["tools"][0]["tool_name"] == "langbot/test-tool/search"
    assert resources["knowledge_bases"][0]["kb_id"] == "kb_001"
    assert resources["storage"]["plugin_storage"] is True

    session_during_run = plugin_connector.sessions_during_run[0]
    assert session_during_run is not None
    assert session_during_run["plugin_identity"] == "langbot/local-agent"
    assert session_during_run["_authorized_ids"]["tool"] == {"langbot/test-tool/search"}
    assert await get_session_registry().get(context["run_id"]) is None


@pytest.mark.asyncio
async def test_orchestrator_streams_fake_plugin_deltas():
    descriptor = make_descriptor()
    plugin_connector = FakePluginConnector(
        results=[
            {"type": "message.delta", "data": {"chunk": {"role": "assistant", "content": "hel"}}},
            {"type": "message.delta", "data": {"chunk": {"role": "assistant", "content": "hello"}}},
            {"type": "run.completed", "data": {"finish_reason": "stop"}},
        ]
    )
    orchestrator = AgentRunOrchestrator(FakeApplication(plugin_connector), FakeRegistry(descriptor))

    chunks = [message async for message in orchestrator.run_from_query(make_query())]

    assert [chunk.content for chunk in chunks] == ["hel", "hello"]


@pytest.mark.asyncio
async def test_orchestrator_applies_state_updates_and_suppresses_protocol_event():
    descriptor = make_descriptor()
    plugin_connector = FakePluginConnector(
        results=[
            {
                "type": "state.updated",
                "data": {
                    "scope": "conversation",
                    "key": "external.conversation_id",
                    "value": "external_conv_123",
                },
            },
            {
                "type": "message.completed",
                "data": {"message": {"role": "assistant", "content": "state saved"}},
            },
        ]
    )
    orchestrator = AgentRunOrchestrator(FakeApplication(plugin_connector), FakeRegistry(descriptor))
    query = make_query()

    messages = [message async for message in orchestrator.run_from_query(query)]

    assert [message.content for message in messages] == ["state saved"]
    assert query.session.using_conversation.uuid == "external_conv_123"
    snapshot = get_state_store().build_snapshot(query, descriptor)
    assert snapshot["conversation"]["external.conversation_id"] == "external_conv_123"


@pytest.mark.asyncio
async def test_orchestrator_unregisters_session_after_runner_failure():
    descriptor = make_descriptor()
    plugin_connector = FakePluginConnector(
        results=[
            {
                "type": "run.failed",
                "data": {"error": "boom", "code": "fake.error", "retryable": False},
            }
        ]
    )
    orchestrator = AgentRunOrchestrator(FakeApplication(plugin_connector), FakeRegistry(descriptor))

    with pytest.raises(RunnerExecutionError):
        [message async for message in orchestrator.run_from_query(make_query())]

    context = plugin_connector.contexts[0]
    assert plugin_connector.sessions_during_run[0] is not None
    assert await get_session_registry().get(context["run_id"]) is None


@pytest.mark.asyncio
async def test_orchestrator_enforces_total_runner_deadline():
    descriptor = make_descriptor()
    plugin_connector = FakePluginConnector(
        results=[
            {
                "type": "message.completed",
                "data": {"message": {"role": "assistant", "content": "too late"}},
            }
        ],
        delay=0.05,
    )
    orchestrator = AgentRunOrchestrator(FakeApplication(plugin_connector), FakeRegistry(descriptor))
    query = make_query()
    query.pipeline_config["ai"]["runner_config"][RUNNER_ID]["timeout"] = 0.01

    with pytest.raises(RunnerExecutionError) as exc_info:
        [message async for message in orchestrator.run_from_query(query)]

    assert exc_info.value.retryable is True
    assert "runner.timeout" in str(exc_info.value)
    assert await get_session_registry().get(plugin_connector.contexts[0]["run_id"]) is None
