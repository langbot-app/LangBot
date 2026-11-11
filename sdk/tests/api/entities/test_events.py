import pytest
import asyncio
from langbot_plugin.api.entities.events import (
    BaseEventModel,
    BotInvitedToGroup,
    FeedbackReceived,
    GroupMemberBanned,
    GroupMemberJoined,
    GroupMemberLeft,
    MessageEdited,
    MessageReactionReceived,
    MessageReceived,
    PlatformSpecificEventReceived,
    PersonMessageReceived,
    GroupMessageReceived,
    PersonNormalMessageReceived,
    PersonCommandSent,
    GroupNormalMessageReceived,
    GroupCommandSent,
    NormalMessageResponded,
    PromptPreProcessing,
)
from langbot_plugin.api.entities.builtin.platform.message import (
    MessageChain,
    Plain,
    Image,
)
from langbot_plugin.api.entities.builtin.provider.session import Session, LauncherTypes
from langbot_plugin.api.entities.builtin.provider.message import Message
from langbot_plugin.api.entities.builtin.pipeline.query import Query
from langbot_plugin.api.entities.builtin.platform.events import (
    BotInvitedToGroupEvent,
    FeedbackEvent,
    FeedbackReceivedEvent,
    FriendMessage,
    GroupMessage,
    MemberBannedEvent,
    MemberJoinedEvent,
    MemberLeftEvent,
    MessageEditedEvent,
    MessageReactionEvent,
    MessageReceivedEvent,
    PlatformSpecificEvent,
)
from langbot_plugin.api.entities.builtin.platform.entities import (
    ChatType,
    Friend,
    Group,
    GroupMember,
    Permission,
    User,
    UserGroup,
)
from langbot_plugin.api.entities.context import EventContext
from langbot_plugin.api.definition.components.common.event_listener import EventListener
from langbot_plugin.api.definition.abstract.platform.adapter import (
    AbstractMessagePlatformAdapter,
)
from langbot_plugin.api.definition.abstract.platform.event_logger import (
    AbstractEventLogger,
)
from typing import Optional, List


class MockLogger(AbstractEventLogger):
    async def info(
        self,
        text: str,
        images: Optional[List[Image]] = None,
        message_session_id: Optional[str] = None,
        no_throw: bool = True,
    ):
        pass

    async def debug(
        self,
        text: str,
        images: Optional[List[Image]] = None,
        message_session_id: Optional[str] = None,
        no_throw: bool = True,
    ):
        pass

    async def warning(
        self,
        text: str,
        images: Optional[List[Image]] = None,
        message_session_id: Optional[str] = None,
        no_throw: bool = True,
    ):
        pass

    async def error(
        self,
        text: str,
        images: Optional[List[Image]] = None,
        message_session_id: Optional[str] = None,
        no_throw: bool = True,
    ):
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


def _make_friend_message(mc=None):
    if mc is None:
        mc = MessageChain([Plain(text="hi")])
    return FriendMessage(
        sender=Friend(id="789012", nickname="Test", remark=""),
        message_chain=mc,
    )


def _make_group_message(mc=None):
    if mc is None:
        mc = MessageChain([Plain(text="hi")])
    return GroupMessage(
        sender=GroupMember(
            id="789012",
            member_name="Test",
            permission=Permission.Member,
            group=Group(id="123456", name="TestGroup", permission=Permission.Member),
        ),
        message_chain=mc,
    )


def make_mock_query():
    # 构造最小可用 Query 实例
    return Query(
        query_id=1,
        launcher_type=LauncherTypes.PERSON,
        launcher_id="test_launcher",
        sender_id="test_sender",
        message_event=_make_friend_message(),
        message_chain=MessageChain([Plain(text="hi")]),
        adapter=MockAdapter(bot_account_id="bot", config={}, logger=MockLogger()),
        session=None,
    )


def test_base_event_model():
    data = {"query": make_mock_query()}
    model = BaseEventModel(**data)
    assert model.query is not None
    # query is excluded from serialization (exclude=True in field definition)
    # so we verify it's accessible on the model directly
    assert model.query.query_id == 1
    assert model.query.launcher_type == LauncherTypes.PERSON


def test_person_message_received():
    mc = MessageChain([Plain(text="Hello")])
    data = {
        "query": make_mock_query(),
        "launcher_type": "person",
        "launcher_id": "123456",
        "sender_id": "789012",
        "message_chain": mc,
        "message_event": _make_friend_message(mc),
    }
    model = PersonMessageReceived(**data)
    assert isinstance(model.message_chain, MessageChain)
    # 测试序列化
    serialized = model.model_dump()
    # query is excluded from serialization, verify it's not in the output
    assert "query" not in serialized
    assert serialized["launcher_type"] == "person"
    assert isinstance(serialized["message_chain"], list)


def test_group_message_received():
    mc = MessageChain([Plain(text="Hello")])
    data = {
        "query": make_mock_query(),
        "launcher_type": "group",
        "launcher_id": "123456",
        "sender_id": "789012",
        "message_chain": mc,
        "message_event": _make_group_message(mc),
    }
    model = GroupMessageReceived(**data)
    assert isinstance(model.message_chain, MessageChain)
    serialized = model.model_dump()
    assert "query" not in serialized
    assert serialized["launcher_type"] == "group"
    assert isinstance(serialized["message_chain"], list)


def test_person_normal_message_received():
    mc = MessageChain([Plain(text="Hello")])
    data = {
        "query": make_mock_query(),
        "launcher_type": "person",
        "launcher_id": "123456",
        "sender_id": "789012",
        "text_message": "Hello",
        "alter": "Modified Hello",
        "reply": [],
        "message_chain": mc,
        "message_event": _make_friend_message(mc),
    }

    model = PersonNormalMessageReceived(**data)
    assert model.text_message == "Hello"


def test_person_command_sent():
    data = {
        "query": make_mock_query(),
        "launcher_type": "person",
        "launcher_id": "123456",
        "sender_id": "789012",
        "command": "test",
        "params": ["param1", "param2"],
        "text_message": "/test param1 param2",
        "is_admin": True,
        "alter": "/test param1 param2",
        "reply": [],
    }

    model = PersonCommandSent(**data)
    assert model.command == "test"
    assert model.params == ["param1", "param2"]
    assert model.is_admin is True


def test_group_normal_message_received():
    mc = MessageChain([Plain(text="Hello Group")])
    data = {
        "query": make_mock_query(),
        "launcher_type": "group",
        "launcher_id": "123456",
        "sender_id": "789012",
        "text_message": "Hello Group",
        "alter": "Modified Hello Group",
        "reply": [],
        "message_chain": mc,
        "message_event": _make_group_message(mc),
    }

    model = GroupNormalMessageReceived(**data)
    assert model.text_message == "Hello Group"


def test_group_command_sent():
    data = {
        "query": make_mock_query(),
        "launcher_type": "group",
        "launcher_id": "123456",
        "sender_id": "789012",
        "command": "test",
        "params": ["param1", "param2"],
        "text_message": "/test param1 param2",
        "is_admin": True,
        "alter": "/test param1 param2",
        "reply": [],
    }

    model = GroupCommandSent(**data)
    assert model.command == "test"
    assert model.params == ["param1", "param2"]
    assert model.is_admin is True


def test_normal_message_responded():
    data = {
        "query": make_mock_query(),
        "launcher_type": "group",
        "launcher_id": "123456",
        "sender_id": "789012",
        "session": Session(
            launcher_type=LauncherTypes.GROUP, launcher_id="123456"
        ).model_dump(),
        "prefix": "Bot: ",
        "response_text": "Hello",
        "finish_reason": "stop",
        "funcs_called": ["func1", "func2"],
        "reply": [],
    }

    model = NormalMessageResponded(**data)
    assert model.prefix == "Bot: "
    assert model.response_text == "Hello"
    assert model.finish_reason == "stop"
    assert model.funcs_called == ["func1", "func2"]
    assert isinstance(model.session, Session)


def test_prompt_pre_processing():
    data = {
        "query": make_mock_query(),
        "session_name": "test_session",
        "default_prompt": [Message(role="user", content="default").model_dump()],
        "prompt": [Message(role="user", content="test").model_dump()],
    }

    model = PromptPreProcessing(**data)
    assert model.session_name == "test_session"
    assert len(model.default_prompt) == 1
    assert len(model.prompt) == 1
    assert isinstance(model.default_prompt[0], Message)
    assert isinstance(model.prompt[0], Message)


def test_validation_errors():
    # 测试缺少必需字段
    with pytest.raises(Exception):
        PersonMessageReceived(query=None)

    # 测试类型错误
    with pytest.raises(Exception):
        PersonMessageReceived(
            query=make_mock_query(),
            launcher_type=123,  # 应该是字符串
            launcher_id="123456",
            sender_id="789012",
            message_chain=MessageChain([Plain(text="Hello")]).model_dump(),
        )


def test_feedback_received_event_serialization_and_legacy_mapping():
    event = FeedbackReceivedEvent(
        feedback_id="feedback-1",
        feedback_type=2,
        feedback_content="not accurate",
        inaccurate_reasons=["wrong_answer"],
        user_id="user-1",
        session_id="person_user-1",
        message_id="msg-1",
        stream_id="stream-1",
        timestamp=123.0,
        bot_uuid="bot-1",
        adapter_name="wecom",
    )

    serialized = event.model_dump()
    assert serialized["type"] == "feedback.received"
    assert serialized["feedback_type"] == 2
    assert serialized["inaccurate_reasons"] == ["wrong_answer"]

    legacy_event = event.to_legacy_event()
    assert isinstance(legacy_event, FeedbackEvent)
    assert legacy_event.type == "FeedbackEvent"
    assert legacy_event.feedback_id == event.feedback_id
    assert legacy_event.feedback_type == event.feedback_type
    assert legacy_event.feedback_content == event.feedback_content
    assert legacy_event.inaccurate_reasons == event.inaccurate_reasons
    assert legacy_event.user_id == event.user_id
    assert legacy_event.session_id == event.session_id
    assert legacy_event.message_id == event.message_id
    assert legacy_event.stream_id == event.stream_id


def test_eba_plugin_event_models_convert_from_platform_events():
    group = UserGroup(id="group-1", name="Test Group")
    user = User(id="user-1", nickname="Tester")
    message_chain = MessageChain([Plain(text="hello eba")])

    cases = [
        (
            MessageReceived,
            MessageReceivedEvent(
                bot_uuid="bot-1",
                adapter_name="discord",
                message_id="msg-1",
                message_chain=message_chain,
                sender=user,
                chat_type=ChatType.GROUP,
                chat_id="group-1",
                group=group,
            ),
            {
                "message_id": "msg-1",
                "chat_id": "group-1",
                "bot_uuid": "bot-1",
                "adapter_name": "discord",
            },
        ),
        (
            MessageEdited,
            MessageEditedEvent(
                message_id="msg-2",
                new_content=message_chain,
                editor=user,
                chat_type=ChatType.PRIVATE,
                chat_id="user-1",
            ),
            {"message_id": "msg-2", "chat_id": "user-1"},
        ),
        (
            MessageReactionReceived,
            MessageReactionEvent(
                message_id="msg-3",
                user=user,
                reaction="👍",
                chat_id="group-1",
                group=group,
            ),
            {"message_id": "msg-3", "reaction": "👍"},
        ),
        (
            FeedbackReceived,
            FeedbackReceivedEvent(
                feedback_id="fb-1", feedback_type=2, feedback_content="bad"
            ),
            {"feedback_id": "fb-1", "feedback_type": 2},
        ),
        (
            GroupMemberJoined,
            MemberJoinedEvent(
                group=group, member=user, inviter=user, join_type="invite"
            ),
            {"join_type": "invite"},
        ),
        (
            GroupMemberLeft,
            MemberLeftEvent(group=group, member=user, is_kicked=True, operator=user),
            {"is_kicked": True},
        ),
        (
            GroupMemberBanned,
            MemberBannedEvent(group=group, member=user, operator=user, duration=60),
            {"duration": 60},
        ),
        (
            BotInvitedToGroup,
            BotInvitedToGroupEvent(group=group, inviter=user, request_id="req-1"),
            {"request_id": "req-1"},
        ),
        (
            PlatformSpecificEventReceived,
            PlatformSpecificEvent(
                adapter_name="telegram", action="callback_query", data={"data": "ok"}
            ),
            {"adapter_name": "telegram", "action": "callback_query"},
        ),
    ]

    for plugin_event_type, platform_event, expected_fields in cases:
        plugin_event = plugin_event_type.from_platform_event(platform_event)
        serialized = plugin_event.model_dump()
        assert serialized["event_name"] == plugin_event_type.__name__
        assert "query" not in serialized
        assert "platform_event" not in serialized
        for field, value in expected_fields.items():
            assert serialized[field] == value

        event_context = EventContext.from_event(plugin_event)
        assert event_context.query_id == 0
        assert event_context.event_name == plugin_event_type.__name__


def test_event_listener_can_handle_eba_plugin_events():
    listener = EventListener()
    calls: list[tuple[str, str]] = []

    @listener.handler(MessageReactionReceived)
    async def on_reaction(ctx: EventContext):
        calls.append((ctx.event_name, ctx.event.reaction))

    @listener.handler(PlatformSpecificEventReceived)
    async def on_platform_specific(ctx: EventContext):
        calls.append((ctx.event_name, ctx.event.action))

    reaction_ctx = EventContext.from_event(
        MessageReactionReceived.from_platform_event(
            MessageReactionEvent(message_id="msg-1", user=User(id="u1"), reaction="👍")
        )
    )
    platform_ctx = EventContext.from_event(
        PlatformSpecificEventReceived.from_platform_event(
            PlatformSpecificEvent(
                adapter_name="telegram",
                action="callback_query",
                data={"data": "button"},
            )
        )
    )

    for ctx in (reaction_ctx, platform_ctx):
        for handler in listener.registered_handlers[ctx.event.__class__]:
            asyncio.run(handler(ctx))

    assert calls == [
        ("MessageReactionReceived", "👍"),
        ("PlatformSpecificEventReceived", "callback_query"),
    ]


@pytest.mark.parametrize(
    "event_type", ["wecombot.enter_chat", "wecombot.template_card_event"]
)
def test_wecombot_business_event_public_round_trip(event_type):
    from langbot_plugin.api.entities.builtin.platform.events import parse_eba_event

    payload = {
        "type": event_type,
        "user": {"id": "visitor", "nickname": "Visitor"},
        "chat_id": "visitor",
        "message_id": "callback-1",
        "data": {"event": {"eventtype": event_type.split(".")[1]}},
    }
    if event_type.endswith("template_card_event"):
        payload.update(
            task_id="card-1",
            event_key="approve",
            selected_items=[{"option_ids": ["yes"]}],
        )
    event = parse_eba_event(payload)
    restored = parse_eba_event(event.model_dump(mode="json"))
    assert restored.type == event_type
    assert restored.user.id == "visitor"
    assert restored.data == payload["data"]
    if event_type.endswith("template_card_event"):
        assert restored.event_key == "approve"
        assert restored.selected_items == [{"option_ids": ["yes"]}]
