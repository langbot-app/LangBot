from __future__ import annotations

import datetime
import asyncio
import typing

import pydantic

from ..sysprompt import entities as sysprompt_entities
from .. import entities as llm_entities
from ..requester import entities
from ...core import entities as core_entities


class Conversation(pydantic.BaseModel):
    """对话"""

    prompt: sysprompt_entities.Prompt

    messages: list[llm_entities.Message]

    create_time: typing.Optional[datetime.datetime] = pydantic.Field(default_factory=datetime.datetime.now)

    update_time: typing.Optional[datetime.datetime] = pydantic.Field(default_factory=datetime.datetime.now)

    use_model: entities.LLMModelInfo


class Session(pydantic.BaseModel):
    """会话"""
    launcher_type: core_entities.LauncherTypes

    launcher_id: int

    sender_id: typing.Optional[int] = 0

    use_prompt_name: typing.Optional[str] = 'default'

    using_conversation: typing.Optional[Conversation] = None

    conversations: typing.Optional[list[Conversation]] = []

    create_time: typing.Optional[datetime.datetime] = pydantic.Field(default_factory=datetime.datetime.now)

    update_time: typing.Optional[datetime.datetime] = pydantic.Field(default_factory=datetime.datetime.now)

    semaphore: typing.Optional[asyncio.Semaphore] = None

    class Config:
        arbitrary_types_allowed = True
