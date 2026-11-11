from __future__ import annotations

import typing
import enum
import datetime
import asyncio

import pydantic

import langbot_plugin.api.entities.builtin.provider.prompt as provider_prompt
import langbot_plugin.api.entities.builtin.provider.message as provider_message
from langbot_plugin.api.entities.execution import WorkspaceExecutionScope


class LauncherTypes(enum.Enum):
    """一个请求的发起者类型"""

    PERSON = "person"
    """私聊"""

    GROUP = "group"
    """群聊"""


class Conversation(pydantic.BaseModel):
    """Conversation, contained in Session, a Session can have multiple historical Conversations, but only one current used Conversation"""

    prompt: provider_prompt.Prompt

    messages: list[provider_message.Message]

    create_time: typing.Optional[datetime.datetime] = pydantic.Field(
        default_factory=datetime.datetime.now
    )

    update_time: typing.Optional[datetime.datetime] = pydantic.Field(
        default_factory=datetime.datetime.now
    )

    pipeline_uuid: str
    """流水线UUID。"""

    bot_uuid: str
    """机器人UUID。"""

    uuid: typing.Optional[str] = None
    """The uuid of the conversation, not automatically generated when created.
    Instead, when using Dify API or other services that manage conversation information externally,
    it is used to bind the external session. The specific usage depends on the Runner."""

    class Config:
        arbitrary_types_allowed = True

    @pydantic.field_serializer("create_time")
    def serialize_create_time(self, v, _info):
        return v.timestamp()

    @pydantic.field_validator("create_time", mode="before")
    def validate_create_time(cls, v):
        return datetime.datetime.fromtimestamp(v)

    @pydantic.field_serializer("update_time")
    def serialize_update_time(self, v, _info):
        return v.timestamp()

    @pydantic.field_validator("update_time", mode="before")
    def validate_update_time(cls, v):
        return datetime.datetime.fromtimestamp(v)


class Session(WorkspaceExecutionScope):
    """Session, one Session corresponds to a {launcher_type.value}_{launcher_id}"""

    launcher_type: LauncherTypes

    launcher_id: typing.Union[int, str]

    sender_id: typing.Optional[typing.Union[int, str]] = 0

    bot_uuid: str | None = None
    """Bot UUID used as part of the Workspace-scoped session key."""

    use_prompt_name: typing.Optional[str] = "default"

    using_conversation: typing.Optional[Conversation] = None

    conversations: typing.Optional[list[Conversation]] = pydantic.Field(
        default_factory=list
    )

    create_time: typing.Optional[datetime.datetime] = pydantic.Field(
        default_factory=datetime.datetime.now
    )

    update_time: typing.Optional[datetime.datetime] = pydantic.Field(
        default_factory=datetime.datetime.now
    )

    _semaphore: typing.Optional[asyncio.Semaphore] = pydantic.PrivateAttr(default=None)
    """The semaphore of the current session, used to limit concurrency"""

    class Config:
        arbitrary_types_allowed = True

    @pydantic.field_serializer("launcher_type")
    def serialize_launcher_type(self, v, _info):
        return v.value

    @pydantic.field_validator("launcher_type", mode="before")
    def validate_launcher_type(cls, v):
        return LauncherTypes(v)

    @pydantic.field_serializer("create_time")
    def serialize_create_time(self, v, _info):
        return v.timestamp()

    @pydantic.field_validator("create_time", mode="before")
    def validate_create_time(cls, v):
        return datetime.datetime.fromtimestamp(v)

    @pydantic.field_serializer("update_time")
    def serialize_update_time(self, v, _info):
        return v.timestamp()

    @pydantic.field_validator("update_time", mode="before")
    def validate_update_time(cls, v):
        return datetime.datetime.fromtimestamp(v)
