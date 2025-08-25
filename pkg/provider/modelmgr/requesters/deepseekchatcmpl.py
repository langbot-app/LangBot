from __future__ import annotations

import typing

from . import chatcmpl
from .. import errors, requester
import langbot_plugin.api.entities.builtin.resource.tool as resource_tool
import langbot_plugin.api.entities.builtin.pipeline.query as pipeline_query
import langbot_plugin.api.entities.builtin.provider.message as provider_message


class DeepseekChatCompletions(chatcmpl.OpenAIChatCompletions):
    """Deepseek ChatCompletion API 请求器"""

    default_config: dict[str, typing.Any] = {
        'base_url': 'https://api.deepseek.com',
        'timeout': 120,
    }

    async def _closure(
        self,
        query: pipeline_query.Query,
        req_messages: list[dict],
        use_model: requester.RuntimeLLMModel,
        use_funcs: list[resource_tool.LLMTool] = None,
        extra_args: dict[str, typing.Any] = {},
        remove_think: bool = False,
    ) -> provider_message.Message:
        self.client.api_key = use_model.token_mgr.get_token()

        args = {}
        args['model'] = use_model.model_entity.name

        if use_funcs:
            tools = await self.ap.tool_mgr.generate_tools_for_openai(use_funcs)

            if tools:
                args['tools'] = tools

        # 设置此次请求中的messages
        messages = req_messages

        # deepseek 不支持多模态，把content都转换成纯文字
        for m in messages:
            if 'content' in m and isinstance(m['content'], list):
                m['content'] = ' '.join([c['text'] for c in m['content']])

        args['messages'] = messages

        # 发送请求
        resp = await self._req(args, extra_body=extra_args)

        # print(resp)

        if resp is None:
            raise errors.RequesterError('接口返回为空，请确定模型提供商服务是否正常')
        # 处理请求结果
        message = await self._make_msg(resp, remove_think)

        return message
