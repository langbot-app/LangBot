"""Integration-style tests for AgentRunOrchestrator with a fake plugin runner."""
from __future__ import annotations

import asyncio
import datetime
import types
from unittest.mock import AsyncMock

import pytest
from sqlalchemy.ext.asyncio import create_async_engine, AsyncEngine

from langbot.pkg.agent.runner.descriptor import AgentRunnerDescriptor
from langbot.pkg.agent.runner.errors import RunnerExecutionError
from langbot.pkg.agent.runner.orchestrator import AgentRunOrchestrator
from langbot.pkg.agent.runner.query_entry_adapter import QueryEntryAdapter
from langbot.pkg.agent.runner.binding_resolver import AgentBindingResolver
from langbot.pkg.agent.runner.session_registry import get_session_registry
from langbot.pkg.agent.runner.persistent_state_store import reset_persistent_state_store
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


class FakePersistenceManager:
    def __init__(self, db_engine: AsyncEngine):
        self._db_engine = db_engine

    def get_db_engine(self):
        return self._db_engine


class FakeApplication:
    def __init__(self, plugin_connector: FakePluginConnector, db_engine: AsyncEngine):
        self.logger = FakeLogger()
        self.ver_mgr = FakeVersionManager()
        self.plugin_connector = plugin_connector
        self.persistence_mgr = FakePersistenceManager(db_engine)

        self.model_mgr = types.SimpleNamespace(
            get_model_by_uuid=AsyncMock(return_value=FakeModel())
        )
        self.rag_mgr = types.SimpleNamespace(
            get_knowledge_base_by_uuid=AsyncMock(return_value=FakeKnowledgeBase("kb_001"))
        )
        self.skill_mgr = types.SimpleNamespace(
            skills={
                "demo": {
                    "name": "demo",
                    "display_name": "Demo Skill",
                    "description": "Helps with demo tasks.",
                },
                "hidden": {
                    "name": "hidden",
                    "display_name": "Hidden Skill",
                    "description": "Not bound to this pipeline.",
                },
            }
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
        capabilities={
            "streaming": True,
            "tool_calling": True,
            "knowledge_retrieval": True,
            "skill_authoring": True,
        },
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
            "_pipeline_bound_skills": ["demo"],
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

    input_data = QueryEntryAdapter._build_input(query)

    assert input_data.contents[0].text == "see attached"
    assert input_data.contents[1].image_base64 == "data:image/png;base64,aGVsbG8="
    assert input_data.contents[2].file_base64 == "data:text/plain;base64,aGVsbG8="

    artifact_types = [attachment.artifact_type for attachment in input_data.attachments]
    assert artifact_types == ["image", "file", "image"]
    assert input_data.attachments[1].name == "hello.txt"


@pytest.fixture(autouse=True)
async def clean_agent_state():
    """Reset all singleton stores and create a test database engine."""
    from langbot.pkg.entity.persistence.base import Base

    reset_persistent_state_store()
    registry = get_session_registry()
    for session in await registry.list_active_runs():
        await registry.unregister(session["run_id"])

    # Create in-memory SQLite engine for tests
    test_engine = create_async_engine("sqlite+aiosqlite:///:memory:")

    # Create tables
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield test_engine

    # Cleanup
    for session in await registry.list_active_runs():
        await registry.unregister(session["run_id"])
    reset_persistent_state_store()
    await test_engine.dispose()


@pytest.mark.asyncio
async def test_orchestrator_runs_fake_plugin_with_authorized_context(clean_agent_state):
    """Test that orchestrator properly builds and passes authorized context to runner."""
    db_engine = clean_agent_state
    descriptor = make_descriptor()
    plugin_connector = FakePluginConnector(
        results=[
            {
                "type": "message.completed",
                "data": {"message": {"role": "assistant", "content": "fake response"}},
            }
        ]
    )
    ap = FakeApplication(plugin_connector, db_engine)
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
    # Protocol v1: params is in adapter.extra
    assert context["adapter"]["extra"]["params"] == {"public_param": "visible"}
    assert context["event"]["event_type"] == "message.received"
    # Note: source_event_type is in event.source_event_type, not event.data
    # (event.data contains the raw event payload, not metadata)
    assert context["actor"]["actor_id"] == "user_001"
    assert context["actor"]["actor_name"] == "Alice"
    assert context["subject"]["subject_id"] == "msg_001"
    assert context["input"]["attachments"]

    resources = context["resources"]
    assert {m["model_id"] for m in resources["models"]} == {"model_primary", "model_fallback"}
    assert resources["tools"][0]["tool_name"] == "langbot/test-tool/search"
    assert resources["knowledge_bases"][0]["kb_id"] == "kb_001"
    assert resources["skills"] == [
        {
            "skill_name": "demo",
            "display_name": "Demo Skill",
            "description": "Helps with demo tasks.",
        }
    ]
    assert resources["storage"]["plugin_storage"] is True

    session_during_run = plugin_connector.sessions_during_run[0]
    assert session_during_run is not None
    assert session_during_run["plugin_identity"] == "langbot/local-agent"
    assert session_during_run["authorization"]["authorized_ids"]["tool"] == {"langbot/test-tool/search"}
    assert session_during_run["authorization"]["authorized_ids"]["skill"] == {"demo"}
    assert await get_session_registry().get(context["run_id"]) is None


@pytest.mark.asyncio
async def test_orchestrator_does_not_package_query_messages_into_context(clean_agent_state):
    """Host should not build an agent working-context window from query.messages."""
    db_engine = clean_agent_state
    descriptor = make_descriptor()
    plugin_connector = FakePluginConnector(
        results=[
            {
                "type": "message.completed",
                "data": {"message": {"role": "assistant", "content": "fake response"}},
            }
        ]
    )
    ap = FakeApplication(plugin_connector, db_engine)
    orchestrator = AgentRunOrchestrator(ap, FakeRegistry(descriptor))
    query = make_query()
    query.pipeline_config["ai"]["runner_config"][RUNNER_ID]["custom-option"] = 2
    query.messages = [
        provider_message.Message(role="user", content="message 1"),
        provider_message.Message(role="assistant", content="response 1"),
        provider_message.Message(role="user", content="message 2"),
        provider_message.Message(role="assistant", content="response 2"),
        provider_message.Message(role="user", content="message 3"),
        provider_message.Message(role="assistant", content="response 3"),
    ]

    messages = [message async for message in orchestrator.run_from_query(query)]

    assert len(messages) == 1
    context = plugin_connector.contexts[0]
    assert context["config"]["custom-option"] == 2
    assert "bootstrap" not in context
    assert set(context["adapter"]) == {"extra"}
    assert "context_packaging" not in context["runtime"]["metadata"]
    assert [message.content for message in query.messages] == [
        "message 1",
        "response 1",
        "message 2",
        "response 2",
        "message 3",
        "response 3",
    ]


@pytest.mark.asyncio
async def test_orchestrator_streams_fake_plugin_deltas(clean_agent_state):
    """Test that orchestrator properly streams message chunks."""
    db_engine = clean_agent_state
    descriptor = make_descriptor()
    plugin_connector = FakePluginConnector(
        results=[
            {"type": "message.delta", "data": {"chunk": {"role": "assistant", "content": "hel"}}},
            {"type": "message.delta", "data": {"chunk": {"role": "assistant", "content": "hello"}}},
            {"type": "run.completed", "data": {"finish_reason": "stop"}},
        ]
    )
    orchestrator = AgentRunOrchestrator(FakeApplication(plugin_connector, db_engine), FakeRegistry(descriptor))

    chunks = [message async for message in orchestrator.run_from_query(make_query())]

    assert [chunk.content for chunk in chunks] == ["hel", "hello"]


@pytest.mark.asyncio
async def test_orchestrator_applies_state_updates_and_suppresses_protocol_event(clean_agent_state):
    """Test that state.updated events are applied and not yielded to pipeline."""
    db_engine = clean_agent_state
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
    orchestrator = AgentRunOrchestrator(FakeApplication(plugin_connector, db_engine), FakeRegistry(descriptor))
    query = make_query()

    messages = [message async for message in orchestrator.run_from_query(query)]

    assert [message.content for message in messages] == ["state saved"]
    # State is persisted to the database via PersistentStateStore.


@pytest.mark.asyncio
async def test_orchestrator_unregisters_session_after_runner_failure(clean_agent_state):
    """Test that session is unregistered even when runner fails."""
    db_engine = clean_agent_state
    descriptor = make_descriptor()
    plugin_connector = FakePluginConnector(
        results=[
            {
                "type": "run.failed",
                "data": {"error": "boom", "code": "fake.error", "retryable": False},
            }
        ]
    )
    orchestrator = AgentRunOrchestrator(FakeApplication(plugin_connector, db_engine), FakeRegistry(descriptor))

    with pytest.raises(RunnerExecutionError):
        [message async for message in orchestrator.run_from_query(make_query())]

    context = plugin_connector.contexts[0]
    assert plugin_connector.sessions_during_run[0] is not None
    assert await get_session_registry().get(context["run_id"]) is None


@pytest.mark.asyncio
async def test_orchestrator_enforces_total_runner_deadline(clean_agent_state):
    """Test that orchestrator enforces total runner timeout."""
    db_engine = clean_agent_state
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
    orchestrator = AgentRunOrchestrator(FakeApplication(plugin_connector, db_engine), FakeRegistry(descriptor))
    query = make_query()
    query.pipeline_config["ai"]["runner_config"][RUNNER_ID]["timeout"] = 0.01

    with pytest.raises(RunnerExecutionError) as exc_info:
        [message async for message in orchestrator.run_from_query(query)]

    assert exc_info.value.retryable is True
    assert "runner.timeout" in str(exc_info.value)
    assert await get_session_registry().list_active_runs() == []


class TestQueryEntrySessionQueryId:
    """Tests for internal query_id entering session registry."""

    @pytest.mark.asyncio
    async def test_query_id_registered_in_session_for_query_entry_flow(self, clean_agent_state):
        """query_id from Query entry flow is registered internally in session."""
        db_engine = clean_agent_state
        descriptor = make_descriptor()
        plugin_connector = FakePluginConnector(
            results=[
                {
                    "type": "message.completed",
                    "data": {"message": {"role": "assistant", "content": "response"}},
                }
            ]
        )
        ap = FakeApplication(plugin_connector, db_engine)
        orchestrator = AgentRunOrchestrator(ap, FakeRegistry(descriptor))
        query = make_query()

        messages = [message async for message in orchestrator.run_from_query(query)]

        assert len(messages) == 1
        # Verify session during run had query_id
        session_during_run = plugin_connector.sessions_during_run[0]
        assert session_during_run is not None
        assert session_during_run["query_id"] == query.query_id

    @pytest.mark.asyncio
    async def test_no_query_id_for_pure_event_first_flow(self, clean_agent_state):
        """Pure event-first flow has query_id=None in session."""
        from langbot.pkg.agent.runner.host_models import AgentEventEnvelope, AgentBinding, BindingScope, StatePolicy, DeliveryPolicy, ResourcePolicy
        from langbot_plugin.api.entities.builtin.agent_runner.input import AgentInput
        from langbot_plugin.api.entities.builtin.agent_runner.delivery import DeliveryContext

        db_engine = clean_agent_state
        descriptor = make_descriptor()
        plugin_connector = FakePluginConnector(
            results=[
                {
                    "type": "message.completed",
                    "data": {"message": {"role": "assistant", "content": "response"}},
                }
            ]
        )
        ap = FakeApplication(plugin_connector, db_engine)
        orchestrator = AgentRunOrchestrator(ap, FakeRegistry(descriptor))

        # Create event and binding directly (not from Query)
        event = AgentEventEnvelope(
            event_id="evt_001",
            event_type="message.received",
            event_time=1234567890,
            source="test",
            bot_id="bot_001",
            workspace_id=None,
            conversation_id="conv_001",
            thread_id=None,
            actor=None,
            subject=None,
            input=AgentInput(text="hello", contents=[], attachments=[]),
            delivery=DeliveryContext(surface="test", supports_streaming=True),
        )
        binding = AgentBinding(
            binding_id="binding_001",
            scope=BindingScope(scope_type="agent", scope_id="pipeline_001"),
            event_types=["message.received"],
            runner_id=RUNNER_ID,
            runner_config={},
            resource_policy=ResourcePolicy(),
            state_policy=StatePolicy(enable_state=False, state_scopes=[]),
            delivery_policy=DeliveryPolicy(enable_streaming=True, enable_reply=True),
            enabled=True,
        )

        messages = [message async for message in orchestrator.run(event, binding)]

        assert len(messages) == 1
        # Verify session during run has query_id=None
        session_during_run = plugin_connector.sessions_during_run[0]
        assert session_during_run is not None
        assert session_during_run["query_id"] is None


class TestQueryEntryAdapterParams:
    """Tests for params handling in Query entry adapter."""

    @pytest.mark.asyncio
    async def test_prompt_not_pushed_into_adapter_extra(self, clean_agent_state):
        """Pipeline prompt is not pushed into adapter.extra."""
        from langbot_plugin.api.entities.builtin.provider import prompt as provider_prompt

        db_engine = clean_agent_state
        descriptor = make_descriptor()
        plugin_connector = FakePluginConnector(
            results=[
                {
                    "type": "message.completed",
                    "data": {"message": {"role": "assistant", "content": "response"}},
                }
            ]
        )
        ap = FakeApplication(plugin_connector, db_engine)
        orchestrator = AgentRunOrchestrator(ap, FakeRegistry(descriptor))
        query = make_query()

        # Add prompt to query
        query.prompt = provider_prompt.Prompt(
            name="test_prompt",
            messages=[
                provider_message.Message(role="system", content="You are a helpful assistant."),
            ],
        )

        _messages = [message async for message in orchestrator.run_from_query(query)]

        context = plugin_connector.contexts[0]
        assert "prompt" not in context
        assert "prompt" not in context["adapter"]["extra"]
        assert context["context"]["available_apis"]["prompt_get"] is True

    @pytest.mark.asyncio
    async def test_params_filtering_keeps_public_param(self, clean_agent_state):
        """Public params are kept."""
        db_engine = clean_agent_state
        descriptor = make_descriptor()
        plugin_connector = FakePluginConnector(
            results=[
                {
                    "type": "message.completed",
                    "data": {"message": {"role": "assistant", "content": "response"}},
                }
            ]
        )
        ap = FakeApplication(plugin_connector, db_engine)
        orchestrator = AgentRunOrchestrator(ap, FakeRegistry(descriptor))
        query = make_query()
        query.variables = {
            "public_param": "visible",
            "another_param": 123,
        }

        _messages = [message async for message in orchestrator.run_from_query(query)]

        context = plugin_connector.contexts[0]
        assert context["adapter"]["extra"]["params"] == {
            "public_param": "visible",
            "another_param": 123,
        }

    @pytest.mark.asyncio
    async def test_params_filtering_removes_internal_vars(self, clean_agent_state):
        """Internal variables (starting with _) are filtered."""
        db_engine = clean_agent_state
        descriptor = make_descriptor()
        plugin_connector = FakePluginConnector(
            results=[
                {
                    "type": "message.completed",
                    "data": {"message": {"role": "assistant", "content": "response"}},
                }
            ]
        )
        ap = FakeApplication(plugin_connector, db_engine)
        orchestrator = AgentRunOrchestrator(ap, FakeRegistry(descriptor))
        query = make_query()
        query.variables = {
            "public_param": "visible",
            "_internal_var": "should_be_filtered",
            "_pipeline_bound_plugins": ["plugin1"],
        }

        _messages = [message async for message in orchestrator.run_from_query(query)]

        context = plugin_connector.contexts[0]
        params = context["adapter"]["extra"]["params"]
        assert "public_param" in params
        assert "_internal_var" not in params
        assert "_pipeline_bound_plugins" not in params

    @pytest.mark.asyncio
    async def test_params_filtering_removes_sensitive_patterns(self, clean_agent_state):
        """Sensitive naming patterns are filtered."""
        db_engine = clean_agent_state
        descriptor = make_descriptor()
        plugin_connector = FakePluginConnector(
            results=[
                {
                    "type": "message.completed",
                    "data": {"message": {"role": "assistant", "content": "response"}},
                }
            ]
        )
        ap = FakeApplication(plugin_connector, db_engine)
        orchestrator = AgentRunOrchestrator(ap, FakeRegistry(descriptor))
        query = make_query()
        query.variables = {
            "public_param": "visible",
            "api_token": "secret123",
            "secret_key": "secret456",
            "password": "secret789",
            "credential": "secret000",
        }

        _messages = [message async for message in orchestrator.run_from_query(query)]

        context = plugin_connector.contexts[0]
        params = context["adapter"]["extra"]["params"]
        assert "public_param" in params
        assert "api_token" not in params
        assert "secret_key" not in params
        assert "password" not in params
        assert "credential" not in params

    @pytest.mark.asyncio
    async def test_params_filtering_removes_non_json_serializable(self, clean_agent_state):
        """Non-JSON-serializable values are filtered."""
        db_engine = clean_agent_state
        descriptor = make_descriptor()
        plugin_connector = FakePluginConnector(
            results=[
                {
                    "type": "message.completed",
                    "data": {"message": {"role": "assistant", "content": "response"}},
                }
            ]
        )
        ap = FakeApplication(plugin_connector, db_engine)
        orchestrator = AgentRunOrchestrator(ap, FakeRegistry(descriptor))
        query = make_query()
        query.variables = {
            "public_param": "visible",
            "a_set": {1, 2, 3},  # set is not JSON-serializable
            "a_lambda": lambda x: x,  # function is not JSON-serializable
        }

        _messages = [message async for message in orchestrator.run_from_query(query)]

        context = plugin_connector.contexts[0]
        params = context["adapter"]["extra"]["params"]
        assert "public_param" in params
        assert "a_set" not in params
        assert "a_lambda" not in params


class TestQueryEntryAdapterHostCapabilities:
    """Tests for event-first host capabilities via Query entry adapter path."""

    @pytest.mark.asyncio
    async def test_state_updated_writes_to_persistent_store(self, clean_agent_state):
        """state.updated via Pipeline path writes to PersistentStateStore."""
        from langbot.pkg.agent.runner.persistent_state_store import get_persistent_state_store

        db_engine = clean_agent_state
        descriptor = make_descriptor()
        plugin_connector = FakePluginConnector(
            results=[
                {
                    "type": "state.updated",
                    "data": {
                        "scope": "conversation",
                        "key": "external.test_key",
                        "value": "test_value",
                    },
                },
                {
                    "type": "message.completed",
                    "data": {"message": {"role": "assistant", "content": "state saved"}},
                },
            ]
        )
        ap = FakeApplication(plugin_connector, db_engine)
        orchestrator = AgentRunOrchestrator(ap, FakeRegistry(descriptor))
        query = make_query()

        messages = [message async for message in orchestrator.run_from_query(query)]

        assert len(messages) == 1
        assert messages[0].content == "state saved"

        # Verify state was written to PersistentStateStore
        persistent_store = get_persistent_state_store(db_engine)
        # Build snapshot to check if state was written
        # Note: We need to rebuild the event and binding to query the store
        from langbot.pkg.agent.runner.query_entry_adapter import QueryEntryAdapter
        event = QueryEntryAdapter.query_to_event(query)
        agent_config = QueryEntryAdapter.config_to_agent_config(query, RUNNER_ID)
        binding = AgentBindingResolver().resolve_one(event, [agent_config])

        snapshot = await persistent_store.build_snapshot_from_event(event, binding, descriptor)
        assert snapshot["conversation"]["external.test_key"] == "test_value"

    @pytest.mark.asyncio
    async def test_run_from_query_restores_activated_skills_from_state(self, clean_agent_state):
        """Persisted activated skill names are restored into the next Query run."""
        from langbot.pkg.agent.runner.persistent_state_store import get_persistent_state_store
        from langbot.pkg.provider.tools.loaders.skill import (
            ACTIVATED_SKILL_NAMES_STATE_KEY,
            ACTIVATED_SKILLS_KEY,
        )

        db_engine = clean_agent_state
        descriptor = make_descriptor()
        plugin_connector = FakePluginConnector(
            results=[
                {
                    "type": "message.completed",
                    "data": {"message": {"role": "assistant", "content": "restored"}},
                }
            ]
        )
        ap = FakeApplication(plugin_connector, db_engine)
        orchestrator = AgentRunOrchestrator(ap, FakeRegistry(descriptor))
        query = make_query()

        persistent_store = get_persistent_state_store(db_engine)
        event = QueryEntryAdapter.query_to_event(query)
        agent_config = QueryEntryAdapter.config_to_agent_config(query, RUNNER_ID)
        binding = AgentBindingResolver().resolve_one(event, [agent_config])
        success, error = await persistent_store.apply_update_from_event(
            event,
            binding,
            descriptor,
            "conversation",
            ACTIVATED_SKILL_NAMES_STATE_KEY,
            ["demo"],
            None,
        )
        assert success is True
        assert error is None

        messages = [message async for message in orchestrator.run_from_query(query)]

        assert len(messages) == 1
        assert query.variables[ACTIVATED_SKILLS_KEY]["demo"]["name"] == "demo"

    @pytest.mark.asyncio
    async def test_event_log_and_transcript_written(self, clean_agent_state):
        """EventLog and Transcript are written via Pipeline path."""
        from langbot.pkg.agent.runner.event_log_store import EventLogStore
        from langbot.pkg.agent.runner.transcript_store import TranscriptStore

        db_engine = clean_agent_state
        descriptor = make_descriptor()
        plugin_connector = FakePluginConnector(
            results=[
                {
                    "type": "message.completed",
                    "data": {"message": {"role": "assistant", "content": "assistant response"}},
                },
            ]
        )
        ap = FakeApplication(plugin_connector, db_engine)
        orchestrator = AgentRunOrchestrator(ap, FakeRegistry(descriptor))
        query = make_query()

        messages = [message async for message in orchestrator.run_from_query(query)]

        assert len(messages) == 1

        # Check EventLog has incoming event
        event_log_store = EventLogStore(db_engine)
        event_logs, _, _ = await event_log_store.page_events(
            conversation_id=query.session.using_conversation.uuid,
            limit=10,
        )
        assert len(event_logs) >= 1
        # First event should be the incoming message.received
        assert event_logs[0]["event_type"] == "message.received"

        # Check Transcript has user and assistant messages
        transcript_store = TranscriptStore(db_engine)
        transcripts, _, _, _ = await transcript_store.page_transcript(
            conversation_id=query.session.using_conversation.uuid,
            limit=10,
        )
        assert len(transcripts) >= 2
        # Find user and assistant messages
        roles = [t["role"] for t in transcripts]
        assert "user" in roles
        assert "assistant" in roles

    @pytest.mark.asyncio
    async def test_artifact_created_via_event_first_path(self, clean_agent_state):
        """artifact.created via Pipeline path uses event-first ArtifactStore and EventLog."""
        import base64
        from langbot.pkg.agent.runner.artifact_store import ArtifactStore
        from langbot.pkg.agent.runner.event_log_store import EventLogStore

        db_engine = clean_agent_state
        descriptor = make_descriptor()
        artifact_id = "artifact_001"
        content = b"test artifact content"
        content_base64 = base64.b64encode(content).decode('utf-8')
        plugin_connector = FakePluginConnector(
            results=[
                {
                    "type": "artifact.created",
                    "data": {
                        "artifact_id": artifact_id,
                        "artifact_type": "file",
                        "mime_type": "text/plain",
                        "name": "test.txt",
                        "content_base64": content_base64,
                    },
                },
                {
                    "type": "message.completed",
                    "data": {"message": {"role": "assistant", "content": "artifact created"}},
                },
            ]
        )
        ap = FakeApplication(plugin_connector, db_engine)
        orchestrator = AgentRunOrchestrator(ap, FakeRegistry(descriptor))
        query = make_query()

        messages = [message async for message in orchestrator.run_from_query(query)]

        assert len(messages) == 1
        assert messages[0].content == "artifact created"

        # Verify artifact was registered in ArtifactStore
        artifact_store = ArtifactStore(db_engine)
        artifact = await artifact_store.get_metadata(artifact_id)
        assert artifact is not None
        assert artifact["artifact_type"] == "file"
        assert artifact["name"] == "test.txt"

        # Verify artifact.created event was written to EventLog
        event_log_store = EventLogStore(db_engine)
        event_logs, _, _ = await event_log_store.page_events(
            conversation_id=query.session.using_conversation.uuid,
            limit=10,
        )
        artifact_events = [e for e in event_logs if e["event_type"] == "artifact.created"]
        assert len(artifact_events) >= 1
