from __future__ import annotations


import typing

from . import chatcmpl
from .. import requester
from ....core import entities as core_entities
from ... import entities as llm_entities
from ...tools import entities as tools_entities


class GiteeAIChatCompletions(chatcmpl.OpenAIChatCompletions):
    """Gitee AI ChatCompletions API 请求器"""

    default_config: dict[str, typing.Any] = {
        'base_url': 'https://ai.gitee.com/v1',
        'timeout': 120,
    }

    async def _closure(
        self,
        query: core_entities.Query,
        req_messages: list[dict],
        use_model: requester.RuntimeLLMModel,
        use_funcs: list[tools_entities.LLMFunction] = None,
        extra_args: dict[str, typing.Any] = {},
    ) -> llm_entities.Message:
        self.client.api_key = use_model.token_mgr.get_token()

        args = {}
        args['model'] = use_model.model_entity.name

        if use_funcs:
            tools = await self.ap.tool_mgr.generate_tools_for_openai(use_funcs)

            if tools:
                args['tools'] = tools

        # gitee 不支持多模态，把content都转换成纯文字
        for m in req_messages:
            if 'content' in m and isinstance(m['content'], list):
                m['content'] = ' '.join([c['text'] for c in m['content']])

        args['messages'] = req_messages

        resp = await self._req(args, extra_body=extra_args)

        message = await self._make_msg(resp)

        return message
