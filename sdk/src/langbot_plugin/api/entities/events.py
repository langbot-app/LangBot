from __future__ import annotations

import typing

import pydantic

from langbot_plugin.api.entities.builtin.platform import message as platform_message
from langbot_plugin.api.entities.builtin.platform import events as platform_events
from langbot_plugin.api.entities.builtin.platform import entities as platform_entities
from langbot_plugin.api.entities.builtin.provider import message as provider_message
from langbot_plugin.api.entities.builtin.provider import session as provider_session
from langbot_plugin.api.entities.builtin.pipeline import query as pipeline_query
from langbot_plugin.api.entities.execution import WorkspaceExecutionScope


class BaseEventModel(WorkspaceExecutionScope):
    """事件模型基类"""

    query_uuid: str | None = None

    query: pipeline_query.Query = pydantic.Field(
        exclude=True,
        default=None,
    )
    """Only stored in LangBot process"""

    class Config:
        arbitrary_types_allowed = True

    @pydantic.model_validator(mode="after")
    def inherit_query_execution_scope(self) -> BaseEventModel:
        """Copy the trusted Query scope into the serialized event payload."""

        if self.query is not None:
            self.inherit_execution_scope(self.query)
            if self.query_uuid is None:
                self.query_uuid = self.query.query_uuid
            elif (
                self.query.query_uuid is not None
                and self.query_uuid != self.query.query_uuid
            ):
                raise ValueError("Event query_uuid does not match Query query_uuid")
        return self


class MessageReceived(BaseEventModel):
    """An EBA platform message was received."""

    event_name: str = "MessageReceived"

    bot_uuid: str = ""
    adapter_name: str = ""
    message_id: typing.Union[int, str] = ""
    message_chain: platform_message.MessageChain = pydantic.Field(
        default_factory=platform_message.MessageChain,
        serialization_alias="message_chain",
    )
    sender: platform_entities.User = pydantic.Field(
        default_factory=lambda: platform_entities.User(id="")
    )
    chat_type: platform_entities.ChatType = platform_entities.ChatType.PRIVATE
    chat_id: typing.Union[int, str] = ""
    group: typing.Optional[platform_entities.UserGroup] = None
    platform_event: typing.Optional[platform_events.MessageReceivedEvent] = (
        pydantic.Field(default=None, exclude=True)
    )

    @pydantic.field_serializer("message_chain")
    def serialize_message_chain(self, v, _info):
        return v.model_dump()

    @pydantic.field_validator("message_chain", mode="before")
    def validate_message_chain(cls, v):
        return platform_message.MessageChain.model_validate(v)

    @classmethod
    def from_platform_event(
        cls, event: platform_events.MessageReceivedEvent
    ) -> "MessageReceived":
        return cls(
            bot_uuid=event.bot_uuid,
            adapter_name=event.adapter_name,
            message_id=event.message_id,
            message_chain=event.message_chain,
            sender=event.sender,
            chat_type=event.chat_type,
            chat_id=event.chat_id,
            group=event.group,
            platform_event=event,
        )


class MessageEdited(BaseEventModel):
    """An EBA platform message was edited."""

    event_name: str = "MessageEdited"

    message_id: typing.Union[int, str] = ""
    new_content: platform_message.MessageChain = pydantic.Field(
        default_factory=platform_message.MessageChain,
        serialization_alias="new_content",
    )
    editor: platform_entities.User = pydantic.Field(
        default_factory=lambda: platform_entities.User(id="")
    )
    chat_type: platform_entities.ChatType = platform_entities.ChatType.PRIVATE
    chat_id: typing.Union[int, str] = ""
    group: typing.Optional[platform_entities.UserGroup] = None
    platform_event: typing.Optional[platform_events.MessageEditedEvent] = (
        pydantic.Field(default=None, exclude=True)
    )

    @pydantic.field_serializer("new_content")
    def serialize_new_content(self, v, _info):
        return v.model_dump()

    @pydantic.field_validator("new_content", mode="before")
    def validate_new_content(cls, v):
        return platform_message.MessageChain.model_validate(v)

    @classmethod
    def from_platform_event(
        cls, event: platform_events.MessageEditedEvent
    ) -> "MessageEdited":
        return cls(
            message_id=event.message_id,
            new_content=event.new_content,
            editor=event.editor,
            chat_type=event.chat_type,
            chat_id=event.chat_id,
            group=event.group,
            platform_event=event,
        )


class MessageDeleted(BaseEventModel):
    """An EBA platform message was deleted."""

    event_name: str = "MessageDeleted"

    message_id: typing.Union[int, str] = ""
    operator: typing.Optional[platform_entities.User] = None
    chat_type: platform_entities.ChatType = platform_entities.ChatType.PRIVATE
    chat_id: typing.Union[int, str] = ""
    group: typing.Optional[platform_entities.UserGroup] = None
    platform_event: typing.Optional[platform_events.MessageDeletedEvent] = (
        pydantic.Field(default=None, exclude=True)
    )

    @classmethod
    def from_platform_event(
        cls, event: platform_events.MessageDeletedEvent
    ) -> "MessageDeleted":
        return cls(
            message_id=event.message_id,
            operator=event.operator,
            chat_type=event.chat_type,
            chat_id=event.chat_id,
            group=event.group,
            platform_event=event,
        )


class MessageReactionReceived(BaseEventModel):
    """An EBA platform message reaction was received."""

    event_name: str = "MessageReactionReceived"

    message_id: typing.Union[int, str] = ""
    user: platform_entities.User = pydantic.Field(
        default_factory=lambda: platform_entities.User(id="")
    )
    reaction: str = ""
    is_add: bool = True
    chat_type: platform_entities.ChatType = platform_entities.ChatType.PRIVATE
    chat_id: typing.Union[int, str] = ""
    group: typing.Optional[platform_entities.UserGroup] = None
    platform_event: typing.Optional[platform_events.MessageReactionEvent] = (
        pydantic.Field(default=None, exclude=True)
    )

    @classmethod
    def from_platform_event(
        cls, event: platform_events.MessageReactionEvent
    ) -> "MessageReactionReceived":
        return cls(
            message_id=event.message_id,
            user=event.user,
            reaction=event.reaction,
            is_add=event.is_add,
            chat_type=event.chat_type,
            chat_id=event.chat_id,
            group=event.group,
            platform_event=event,
        )


class FeedbackReceived(BaseEventModel):
    """User feedback was received for a bot response."""

    event_name: str = "FeedbackReceived"

    feedback_id: str
    feedback_type: int
    feedback_content: typing.Optional[str] = None
    inaccurate_reasons: typing.Optional[list[str]] = None
    user_id: typing.Optional[str] = None
    session_id: typing.Optional[str] = None
    message_id: typing.Optional[str] = None
    stream_id: typing.Optional[str] = None
    platform_event: typing.Optional[platform_events.FeedbackReceivedEvent] = (
        pydantic.Field(default=None, exclude=True)
    )

    @classmethod
    def from_platform_event(
        cls, event: platform_events.FeedbackReceivedEvent
    ) -> "FeedbackReceived":
        return cls(
            feedback_id=event.feedback_id,
            feedback_type=event.feedback_type,
            feedback_content=event.feedback_content,
            inaccurate_reasons=event.inaccurate_reasons,
            user_id=event.user_id,
            session_id=event.session_id,
            message_id=event.message_id,
            stream_id=event.stream_id,
            platform_event=event,
        )


class GroupMemberJoined(BaseEventModel):
    """A member joined a group."""

    event_name: str = "GroupMemberJoined"

    group: platform_entities.UserGroup = pydantic.Field(
        default_factory=lambda: platform_entities.UserGroup(id="")
    )
    member: platform_entities.User = pydantic.Field(
        default_factory=lambda: platform_entities.User(id="")
    )
    inviter: typing.Optional[platform_entities.User] = None
    join_type: typing.Optional[str] = None
    platform_event: typing.Optional[platform_events.MemberJoinedEvent] = pydantic.Field(
        default=None, exclude=True
    )

    @classmethod
    def from_platform_event(
        cls, event: platform_events.MemberJoinedEvent
    ) -> "GroupMemberJoined":
        return cls(
            group=event.group,
            member=event.member,
            inviter=event.inviter,
            join_type=event.join_type,
            platform_event=event,
        )


class GroupMemberLeft(BaseEventModel):
    """A member left a group."""

    event_name: str = "GroupMemberLeft"

    group: platform_entities.UserGroup = pydantic.Field(
        default_factory=lambda: platform_entities.UserGroup(id="")
    )
    member: platform_entities.User = pydantic.Field(
        default_factory=lambda: platform_entities.User(id="")
    )
    is_kicked: bool = False
    operator: typing.Optional[platform_entities.User] = None
    platform_event: typing.Optional[platform_events.MemberLeftEvent] = pydantic.Field(
        default=None, exclude=True
    )

    @classmethod
    def from_platform_event(
        cls, event: platform_events.MemberLeftEvent
    ) -> "GroupMemberLeft":
        return cls(
            group=event.group,
            member=event.member,
            is_kicked=event.is_kicked,
            operator=event.operator,
            platform_event=event,
        )


class GroupMemberBanned(BaseEventModel):
    """A member was muted or restricted in a group."""

    event_name: str = "GroupMemberBanned"

    group: platform_entities.UserGroup = pydantic.Field(
        default_factory=lambda: platform_entities.UserGroup(id="")
    )
    member: platform_entities.User = pydantic.Field(
        default_factory=lambda: platform_entities.User(id="")
    )
    operator: typing.Optional[platform_entities.User] = None
    duration: typing.Optional[int] = None
    platform_event: typing.Optional[platform_events.MemberBannedEvent] = pydantic.Field(
        default=None, exclude=True
    )

    @classmethod
    def from_platform_event(
        cls, event: platform_events.MemberBannedEvent
    ) -> "GroupMemberBanned":
        return cls(
            group=event.group,
            member=event.member,
            operator=event.operator,
            duration=event.duration,
            platform_event=event,
        )


class BotInvitedToGroup(BaseEventModel):
    """The bot was invited to a group."""

    event_name: str = "BotInvitedToGroup"

    group: platform_entities.UserGroup = pydantic.Field(
        default_factory=lambda: platform_entities.UserGroup(id="")
    )
    inviter: typing.Optional[platform_entities.User] = None
    request_id: typing.Optional[typing.Union[int, str]] = None
    platform_event: typing.Optional[platform_events.BotInvitedToGroupEvent] = (
        pydantic.Field(default=None, exclude=True)
    )

    @classmethod
    def from_platform_event(
        cls, event: platform_events.BotInvitedToGroupEvent
    ) -> "BotInvitedToGroup":
        return cls(
            group=event.group,
            inviter=event.inviter,
            request_id=event.request_id,
            platform_event=event,
        )


class BotRemovedFromGroup(BaseEventModel):
    """The bot was removed from a group."""

    event_name: str = "BotRemovedFromGroup"

    group: platform_entities.UserGroup = pydantic.Field(
        default_factory=lambda: platform_entities.UserGroup(id="")
    )
    operator: typing.Optional[platform_entities.User] = None
    platform_event: typing.Optional[platform_events.BotRemovedFromGroupEvent] = (
        pydantic.Field(default=None, exclude=True)
    )

    @classmethod
    def from_platform_event(
        cls, event: platform_events.BotRemovedFromGroupEvent
    ) -> "BotRemovedFromGroup":
        return cls(group=event.group, operator=event.operator, platform_event=event)


class BotMuted(BaseEventModel):
    """The bot was muted in a group."""

    event_name: str = "BotMuted"

    group: platform_entities.UserGroup = pydantic.Field(
        default_factory=lambda: platform_entities.UserGroup(id="")
    )
    operator: typing.Optional[platform_entities.User] = None
    duration: typing.Optional[int] = None
    platform_event: typing.Optional[platform_events.BotMutedEvent] = pydantic.Field(
        default=None, exclude=True
    )

    @classmethod
    def from_platform_event(cls, event: platform_events.BotMutedEvent) -> "BotMuted":
        return cls(
            group=event.group,
            operator=event.operator,
            duration=event.duration,
            platform_event=event,
        )


class BotUnmuted(BaseEventModel):
    """The bot was unmuted in a group."""

    event_name: str = "BotUnmuted"

    group: platform_entities.UserGroup = pydantic.Field(
        default_factory=lambda: platform_entities.UserGroup(id="")
    )
    operator: typing.Optional[platform_entities.User] = None
    platform_event: typing.Optional[platform_events.BotUnmutedEvent] = pydantic.Field(
        default=None, exclude=True
    )

    @classmethod
    def from_platform_event(
        cls, event: platform_events.BotUnmutedEvent
    ) -> "BotUnmuted":
        return cls(group=event.group, operator=event.operator, platform_event=event)


class PlatformSpecificEventReceived(BaseEventModel):
    """A platform-specific EBA event was received."""

    event_name: str = "PlatformSpecificEventReceived"

    adapter_name: str = ""
    action: str = ""
    data: dict = pydantic.Field(default_factory=dict)
    platform_event: typing.Optional[platform_events.PlatformSpecificEvent] = (
        pydantic.Field(default=None, exclude=True)
    )

    @classmethod
    def from_platform_event(
        cls, event: platform_events.PlatformSpecificEvent
    ) -> "PlatformSpecificEventReceived":
        return cls(
            adapter_name=event.adapter_name,
            action=event.action,
            data=event.data,
            platform_event=event,
        )


class PersonMessageReceived(BaseEventModel):
    """收到任何私聊消息时"""

    event_name: str = "PersonMessageReceived"

    launcher_type: str
    """发起对象类型(group/person)"""

    launcher_id: typing.Union[int, str]
    """发起对象ID(群号/QQ号)"""

    sender_id: typing.Union[int, str]
    """发送者ID(QQ号)"""

    message_event: platform_events.FriendMessage
    """原始消息事件"""

    message_chain: platform_message.MessageChain = pydantic.Field(
        serialization_alias="message_chain"
    )
    """原始消息链"""

    @pydantic.field_serializer("message_chain")
    def serialize_message_chain(self, v, _info):
        return v.model_dump()

    @pydantic.field_validator("message_chain", mode="before")
    def validate_message_chain(cls, v):
        return platform_message.MessageChain.model_validate(v)

    @pydantic.field_serializer("message_event")
    def serialize_message_event(self, v, _info):
        return v.model_dump()

    @pydantic.field_validator("message_event", mode="before")
    def validate_message_event(cls, v):
        return platform_events.FriendMessage.model_validate(v)


class GroupMessageReceived(BaseEventModel):
    """收到任何群聊消息时"""

    event_name: str = "GroupMessageReceived"

    launcher_type: str

    launcher_id: typing.Union[int, str]

    sender_id: typing.Union[int, str]

    message_event: platform_events.GroupMessage
    """原始消息事件"""

    message_chain: platform_message.MessageChain = pydantic.Field(
        serialization_alias="message_chain"
    )
    """原始消息链"""

    @pydantic.field_serializer("message_chain")
    def serialize_message_chain(self, v, _info):
        return v.model_dump()

    @pydantic.field_validator("message_chain", mode="before")
    def validate_message_chain(cls, v):
        return platform_message.MessageChain.model_validate(v)

    @pydantic.field_serializer("message_event")
    def serialize_message_event(self, v, _info):
        return v.model_dump()

    @pydantic.field_validator("message_event", mode="before")
    def validate_message_event(cls, v):
        return platform_events.GroupMessage.model_validate(v)


class _WithReplyMessageChain(BaseEventModel):
    """事件模型基类，包含回复消息链对象"""

    reply_message_chain: typing.Optional[platform_message.MessageChain] = (
        pydantic.Field(serialization_alias="reply_message_chain", default=None)
    )
    """回复消息链对象，仅在阻止默认行为时有效"""

    @pydantic.field_serializer("reply_message_chain")
    def serialize_reply_message_chain(self, v, _info):
        if v is None:
            return None
        return v.model_dump()

    @pydantic.field_validator("reply_message_chain", mode="before")
    def validate_reply_message_chain(cls, v):
        if v is None:
            return None
        return platform_message.MessageChain.model_validate(v)


class PersonNormalMessageReceived(_WithReplyMessageChain):
    """判断为应该处理的私聊普通消息时触发"""

    event_name: str = "PersonNormalMessageReceived"

    launcher_type: str

    launcher_id: typing.Union[int, str]

    sender_id: typing.Union[int, str]

    text_message: str

    message_event: platform_events.FriendMessage
    """原始消息事件"""

    message_chain: platform_message.MessageChain = pydantic.Field(
        serialization_alias="message_chain"
    )
    """原始消息链"""

    @pydantic.field_serializer("message_chain")
    def serialize_message_chain(self, v, _info):
        return v.model_dump()

    @pydantic.field_validator("message_chain", mode="before")
    def validate_message_chain(cls, v):
        return platform_message.MessageChain.model_validate(v)

    @pydantic.field_serializer("message_event")
    def serialize_message_event(self, v, _info):
        return v.model_dump()

    @pydantic.field_validator("message_event", mode="before")
    def validate_message_event(cls, v):
        return platform_events.FriendMessage.model_validate(v)

    user_message_alter: typing.Optional[
        typing.Union[
            provider_message.ContentElement, list[provider_message.ContentElement], str
        ]
    ] = pydantic.Field(default=None)
    """修改后的 LLM 消息对象，可用于改写用户消息"""


class GroupNormalMessageReceived(_WithReplyMessageChain):
    """判断为应该处理的群聊普通消息时触发"""

    event_name: str = "GroupNormalMessageReceived"

    launcher_type: str

    launcher_id: typing.Union[int, str]

    sender_id: typing.Union[int, str]

    text_message: str

    message_event: platform_events.GroupMessage
    """原始消息事件"""

    message_chain: platform_message.MessageChain = pydantic.Field(
        serialization_alias="message_chain"
    )

    @pydantic.field_serializer("message_chain")
    def serialize_message_chain(self, v, _info):
        return v.model_dump()

    @pydantic.field_validator("message_chain", mode="before")
    def validate_message_chain(cls, v):
        return platform_message.MessageChain.model_validate(v)

    @pydantic.field_serializer("message_event")
    def serialize_message_event(self, v, _info):
        return v.model_dump()

    @pydantic.field_validator("message_event", mode="before")
    def validate_message_event(cls, v):
        return platform_events.GroupMessage.model_validate(v)

    user_message_alter: typing.Optional[
        typing.Union[
            provider_message.ContentElement, list[provider_message.ContentElement], str
        ]
    ] = pydantic.Field(default=None)
    """修改后的 LLM 消息对象，可用于改写用户消息"""


class PersonCommandSent(_WithReplyMessageChain):
    """判断为应该处理的私聊命令时触发"""

    event_name: str = "PersonCommandSent"

    launcher_type: str

    launcher_id: typing.Union[int, str]

    sender_id: typing.Union[int, str]

    command: str

    params: list[str]

    text_message: str

    is_admin: bool


class GroupCommandSent(_WithReplyMessageChain):
    """判断为应该处理的群聊命令时触发"""

    event_name: str = "GroupCommandSent"

    launcher_type: str

    launcher_id: typing.Union[int, str]

    sender_id: typing.Union[int, str]

    command: str

    params: list[str]

    text_message: str

    is_admin: bool


class NormalMessageResponded(_WithReplyMessageChain):
    """回复普通消息时触发"""

    event_name: str = "NormalMessageResponded"

    launcher_type: str

    launcher_id: typing.Union[int, str]

    sender_id: typing.Union[int, str]

    session: provider_session.Session
    """会话对象"""

    prefix: str
    """回复消息的前缀"""

    response_text: str
    """回复消息的文本"""

    finish_reason: str
    """响应结束原因"""

    funcs_called: list[str]
    """调用的函数列表"""


class PromptPreProcessing(BaseEventModel):
    """会话中的Prompt预处理时触发"""

    event_name: str = "PromptPreProcessing"

    session_name: str

    default_prompt: list[
        typing.Union[provider_message.Message, provider_message.MessageChunk]
    ]
    """此对话的情景预设（系统提示词），可修改"""

    prompt: list[typing.Union[provider_message.Message, provider_message.MessageChunk]]
    """此对话现有消息记录，可修改"""
