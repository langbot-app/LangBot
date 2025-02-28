from __future__ import annotations

from ....core import app

from . import chatcmpl
from .. import entities, errors, requester
from ....core import entities as core_entities, app
from ... import entities as llm_entities
from ...tools import entities as tools_entities


class MoonshotChatCompletions(chatcmpl.OpenAIChatCompletions):
    """Moonshot ChatCompletion API 请求器"""

    def __init__(self, ap: app.Application):
        self.requester_cfg = ap.provider_cfg.data['requester']['moonshot-chat-completions']
        self.ap = ap

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

        # 设置此次请求中的messages
        messages = req_messages

        # deepseek 不支持多模态，把content都转换成纯文字
        for m in messages:
            if 'content' in m and isinstance(m["content"], list):
                m["content"] = " ".join([c["text"] for c in m["content"]])

        # 删除空的
        messages = [m for m in messages if m["content"].strip() != ""]

        args["messages"] = messages

        # 发送请求
        resp = await self._req(args)

        # 处理请求结果
        message = await self._make_msg(resp)

        return message