from __future__ import annotations

import gc
import weakref

import pytest

from langbot_plugin.api.entities import context as context_module
from langbot_plugin.api.definition.abstract.platform.adapter import (
    AbstractMessagePlatformAdapter,
)
from langbot_plugin.api.definition.abstract.platform.event_logger import (
    AbstractEventLogger,
)
from langbot_plugin.api.entities.builtin.pipeline.query import Query
from langbot_plugin.api.entities.builtin.platform.message import MessageChain, Plain
from langbot_plugin.api.entities.builtin.platform.events import FriendMessage
from langbot_plugin.api.entities.builtin.platform.entities import Friend
from langbot_plugin.api.entities.builtin.provider.session import LauncherTypes
from langbot_plugin.api.entities.builtin.provider.session import Session
from langbot_plugin.api.entities.events import PersonMessageReceived
from langbot_plugin.api.entities.context import EventContext


class MockLogger(AbstractEventLogger):
    async def info(self, text, images=None, message_session_id=None, no_throw=True):
        pass

    async def debug(self, text, images=None, message_session_id=None, no_throw=True):
        pass

    async def warning(self, text, images=None, message_session_id=None, no_throw=True):
        pass

    async def error(self, text, images=None, message_session_id=None, no_throw=True):
        pass


class MockAdapter(AbstractMessagePlatformAdapter):
    config: dict = {}
    logger: MockLogger

    async def send_message(self, target_type, target_id, message):
        pass

    async def reply_message(self, message_source, message, quote_origin=False):
        pass

    async def is_muted(self, group_id):
        return False

    def register_listener(self, event_type, callback):
        pass

    def unregister_listener(self, event_type, callback):
        pass

    async def run_async(self):
        pass

    async def kill(self) -> bool:
        return True


def _make_friend_message(chain: MessageChain) -> FriendMessage:
    return FriendMessage(
        sender=Friend(id="sender", nickname="Tester", remark=""),
        message_chain=chain,
    )


def _make_query(chain: MessageChain) -> Query:
    return Query(
        query_id=1,
        launcher_type=LauncherTypes.PERSON,
        launcher_id="launcher",
        sender_id="sender",
        message_event=_make_friend_message(chain),
        message_chain=chain,
        adapter=MockAdapter(bot_account_id="bot", config={}, logger=MockLogger()),
        session=None,
    )


def _event():
    chain = MessageChain([Plain(text="hello")])
    return PersonMessageReceived(
        query=_make_query(chain),
        launcher_type="person",
        launcher_id="launcher",
        sender_id="sender",
        message_chain=chain,
        message_event=_make_friend_message(chain),
    )


def test_event_context_from_event_assigns_monotonic_id_and_caches_context():
    context_module.cached_event_contexts.clear()
    context_module.global_eid_index = 0

    first = EventContext.from_event(_event())
    second = EventContext.from_event(_event())

    assert first.eid == 0
    assert second.eid == 1
    assert context_module.cached_event_contexts[0] is first
    assert context_module.cached_event_contexts[1] is second
    assert first.event_name == "PersonMessageReceived"


def test_event_context_cache_does_not_keep_completed_events_alive():
    context_module.cached_event_contexts.clear()
    context_module.global_eid_index = 0

    context = EventContext.from_event(_event())
    context_ref = weakref.ref(context)
    del context
    gc.collect()

    assert context_ref() is None
    assert not context_module.cached_event_contexts


def test_event_context_prevent_flags_are_mutable_runtime_state():
    ctx = EventContext.from_event(_event())

    assert ctx.is_prevented_default() is False
    assert ctx.is_prevented_postorder() is False

    ctx.prevent_default()
    ctx.prevent_postorder()

    assert ctx.is_prevented_default() is True
    assert ctx.is_prevented_postorder() is True


def test_event_context_validates_event_from_serialized_payload():
    event = _event()
    payload = event.model_dump()
    payload["event_name"] = "PersonMessageReceived"

    ctx = EventContext(
        query_id=event.query.query_id,
        eid=99,
        event_name="PersonMessageReceived",
        event=payload,
    )

    assert isinstance(ctx.event, PersonMessageReceived)
    assert ctx.event.sender_id == "sender"


def test_query_variable_helpers_initialize_and_return_runtime_state():
    query = _make_query(MessageChain([Plain(text="hello")]))
    query.variables = None

    assert query.get_variable("missing") is None
    assert query.get_variables() == {}

    query.set_variable("answer", 42)

    assert query.get_variable("answer") == 42
    assert query.get_variables() == {"answer": 42}


def test_query_model_dump_serializes_public_request_payload():
    query = _make_query(MessageChain([Plain(text="hello")]))
    query.bot_uuid = "bot-uuid"
    query.pipeline_uuid = "pipeline-uuid"
    query.pipeline_config = {"enabled": True}

    payload = query.model_dump()

    assert payload["query_id"] == 1
    assert payload["launcher_type"] == "person"
    assert payload["launcher_id"] == "launcher"
    assert payload["sender_id"] == "sender"
    assert payload["bot_uuid"] == "bot-uuid"
    assert payload["pipeline_uuid"] == "pipeline-uuid"
    assert payload["pipeline_config"] == {"enabled": True}
    assert payload["session"] is None
    assert payload["messages"] == []
    assert payload["prompt"] is None
    assert payload["message_chain"][0]["text"] == "hello"


def test_legacy_query_event_and_session_payloads_remain_valid_without_scope():
    query = _make_query(MessageChain([Plain(text="hello")]))
    session = Session.model_validate(
        {
            "launcher_type": "person",
            "launcher_id": "launcher",
        }
    )
    event_context = EventContext.from_event(_event())

    assert query.workspace_uuid is None
    assert session.workspace_uuid is None
    assert event_context.workspace_uuid is None
    assert "workspace_uuid" not in query.model_dump()


def test_query_scope_propagates_to_event_session_and_event_context():
    chain = MessageChain([Plain(text="hello")])
    message_event = _make_friend_message(chain)
    session = Session(
        launcher_type=LauncherTypes.PERSON,
        launcher_id="launcher",
    )
    query = Query(
        instance_uuid="instance-1",
        workspace_uuid="workspace-a",
        placement_generation=8,
        query_id=1,
        query_uuid="query-opaque-1",
        launcher_type=LauncherTypes.PERSON,
        launcher_id="launcher",
        sender_id="sender",
        message_event=message_event,
        message_chain=chain,
        bot_uuid="bot-1",
        session=session,
    )
    event = PersonMessageReceived(
        query=query,
        launcher_type="person",
        launcher_id="launcher",
        sender_id="sender",
        message_chain=chain,
        message_event=message_event,
    )
    event_context = EventContext.from_event(event)

    for scoped in (query.message_event, query.session, event, event_context):
        assert scoped.instance_uuid == "instance-1"
        assert scoped.workspace_uuid == "workspace-a"
        assert scoped.placement_generation == 8
    assert query.session.bot_uuid == "bot-1"
    assert event.query_uuid == "query-opaque-1"
    assert event_context.query_uuid == "query-opaque-1"
    assert query.model_dump()["workspace_uuid"] == "workspace-a"
    assert query.message_event.model_dump()["workspace_uuid"] == "workspace-a"


def test_query_rejects_nested_event_from_another_workspace():
    chain = MessageChain([Plain(text="hello")])
    message_event = _make_friend_message(chain)
    message_event.workspace_uuid = "workspace-b"

    with pytest.raises(
        ValueError,
        match="Execution scope mismatch for workspace_uuid",
    ):
        Query(
            instance_uuid="instance-1",
            workspace_uuid="workspace-a",
            placement_generation=1,
            query_id=1,
            launcher_type=LauncherTypes.PERSON,
            launcher_id="launcher",
            sender_id="sender",
            message_event=message_event,
            message_chain=chain,
        )
