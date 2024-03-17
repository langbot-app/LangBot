from __future__ import annotations

import typing

import anthropic

from .. import api, entities, errors

from .. import api, entities, errors
from ....core import entities as core_entities
from ... import entities as llm_entities
from ...tools import entities as tools_entities


@api.requester_class("anthropic-messages")
class AnthropicMessages(api.LLMAPIRequester):
    """Anthropic Messages API 请求器"""

    client: anthropic.AsyncAnthropic

    async def initialize(self):
        self.client = anthropic.AsyncAnthropic(
            api_key="",
            base_url=self.ap.provider_cfg.data['requester']['anthropic-messages']['base-url'],
            timeout=self.ap.provider_cfg.data['requester']['anthropic-messages']['timeout'],
            proxies=self.ap.proxy_mgr.get_forward_proxies()
        )

    async def request(
        self,
        query: core_entities.Query,
    ) -> typing.AsyncGenerator[llm_entities.Message, None]:
        self.client.api_key = query.use_model.token_mgr.get_token()

        args = self.ap.provider_cfg.data['requester']['anthropic-messages']['args'].copy()
        args["model"] = query.use_model.name if query.use_model.model_name is None else query.use_model.model_name

        req_messages = [  # req_messages 仅用于类内，外部同步由 query.messages 进行
            m.dict(exclude_none=True) for m in query.prompt.messages
        ] + [m.dict(exclude_none=True) for m in query.messages]

        # 删除所有 role=system & content='' 的消息
        req_messages = [
            m for m in req_messages if not (m["role"] == "system" and m["content"].strip() == "")
        ]

        # 检查是否有 role=system 的消息，若有，改为 role=user，并在后面加一个 role=assistant 的消息
        system_role_index = []
        for i, m in enumerate(req_messages):
            if m["role"] == "system":
                system_role_index.append(i)
                m["role"] = "user"

        if system_role_index:
            for i in system_role_index[::-1]:
                req_messages.insert(i + 1, {"role": "assistant", "content": "Okay, I'll follow."})

        args["messages"] = req_messages

        resp = await self.client.messages.create(**args)

        yield llm_entities.Message(
            content=resp.content[0].text,
            role=resp.role
        )