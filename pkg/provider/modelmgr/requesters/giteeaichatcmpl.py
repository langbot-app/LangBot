from __future__ import annotations

import json

import asyncio
import aiohttp
import typing

from . import chatcmpl
from .. import entities, errors, requester
from ....core import app, entities as core_entities
from ... import entities as llm_entities
from ...tools import entities as tools_entities
from .. import entities as modelmgr_entities


class GiteeAIChatCompletions(chatcmpl.OpenAIChatCompletions):
    """Gitee AI ChatCompletions API 请求器"""

    def __init__(self, ap: app.Application):
        self.ap = ap
        self.requester_cfg = ap.provider_cfg.data['requester']['gitee-ai-chat-completions'].copy()

    async def _closure(
        self,
        query: core_entities.Query,
        req_messages: list[dict],
        use_model: entities.LLMModelInfo,
        use_funcs: list[tools_entities.LLMFunction] = None,
    ) -> llm_entities.Message:
        self.client.api_key = use_model.token_mgr.get_token()

        args = self.requester_cfg['args'].copy()
        args["model"] = use_model.name if use_model.model_name is None else use_model.model_name

        if use_funcs:
            tools = await self.ap.tool_mgr.generate_tools_for_openai(use_funcs)

            if tools:
                args["tools"] = tools

        # gitee 不支持多模态，把content都转换成纯文字
        for m in req_messages:
            if 'content' in m and isinstance(m["content"], list):
                m["content"] = " ".join([c["text"] for c in m["content"]])

        args["messages"] = req_messages

        resp = await self._req(args)

        message = await self._make_msg(resp)

        return message
