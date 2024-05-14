from __future__ import annotations

import typing
import traceback

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

    async def call(
        self,
        model: entities.LLMModelInfo,
        messages: typing.List[llm_entities.Message],
        funcs: typing.List[tools_entities.LLMFunction] = None,
    ) -> llm_entities.Message:
        self.client.api_key = model.token_mgr.get_token()

        args = self.ap.provider_cfg.data['requester']['anthropic-messages']['args'].copy()
        args["model"] = model.name if model.model_name is None else model.model_name

        req_messages = [
            m.dict(exclude_none=True) for m in messages if m.content.strip() != ""
        ]

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

        # 忽略掉空消息，用户可能发送空消息，而上层未过滤
        req_messages = [
            m for m in req_messages if m["content"].strip() != ""
        ]

        args["messages"] = req_messages

        try:
            resp = await self.client.messages.create(**args)

            return llm_entities.Message(
                content=resp.content[0].text,
                role=resp.role
            )
        except anthropic.AuthenticationError as e:
            raise errors.RequesterError(f'api-key 无效: {e.message}')
        except anthropic.BadRequestError as e:
            raise errors.RequesterError(str(e.message))
        except anthropic.NotFoundError as e:
            if 'model: ' in str(e):
                raise errors.RequesterError(f'模型无效: {e.message}')
            else:
                raise errors.RequesterError(f'请求地址无效: {e.message}')
