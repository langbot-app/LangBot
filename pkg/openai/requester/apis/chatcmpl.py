from __future__ import annotations

import asyncio
import typing

import openai

from .. import api
from ....core import entities as core_entities
from ... import entities as llm_entities
from ...session import entities as session_entities


class OpenAIChatCompletion(api.LLMAPIRequester):

    client: openai.Client

    async def initialize(self):
        self.client = openai.Client(
            base_url=self.ap.cfg_mgr.data['openai_config']['reverse_proxy'],
            timeout=self.ap.cfg_mgr.data['process_message_timeout']
        )

    async def request(self, query: core_entities.Query, conversation: session_entities.Conversation) -> typing.AsyncGenerator[llm_entities.Message, None]:
        """请求
        """
        await asyncio.sleep(10)

        yield llm_entities.Message(
            role=llm_entities.MessageRole.ASSISTANT,
            content="hello"
        )
