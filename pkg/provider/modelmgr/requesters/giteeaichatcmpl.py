from __future__ import annotations


import typing

from . import chatcmpl
from .. import requester
from ... import entities as llm_entities
import langbot_plugin.api.entities.builtin.resource.tool as resource_tool
import langbot_plugin.api.entities.builtin.pipeline.query as pipeline_query


class GiteeAIChatCompletions(chatcmpl.OpenAIChatCompletions):
    """Gitee AI ChatCompletions API 请求器"""

    default_config: dict[str, typing.Any] = {
        'base_url': 'https://ai.gitee.com/v1',
        'timeout': 120,
    }

    async def _closure(
        self,
        query: pipeline_query.Query,
        req_messages: list[dict],
        use_model: requester.RuntimeLLMModel,
        use_funcs: list[resource_tool.LLMTool] = None,
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
