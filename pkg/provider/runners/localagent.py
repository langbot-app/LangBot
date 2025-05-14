from __future__ import annotations

import json
import typing

from .. import runner
from ...core import entities as core_entities
from .. import entities as llm_entities


@runner.runner_class('local-agent')
class LocalAgentRunner(runner.RequestRunner):
    """本地Agent请求运行器"""

    async def run(self, query: core_entities.Query) -> typing.AsyncGenerator[llm_entities.Message, None]:
        """运行请求"""
        pending_tool_calls = []

        req_messages = query.prompt.messages.copy() + query.messages.copy() + [query.user_message]

        # 首次请求
        msg = await query.use_llm_model.requester.invoke_llm(
            query,
            query.use_llm_model,
            req_messages,
            query.use_funcs,
            extra_args=query.use_llm_model.model_entity.extra_args,
        )

        yield msg

        pending_tool_calls = msg.tool_calls

        req_messages.append(msg)

        # 持续请求，只要还有待处理的工具调用就继续处理调用
        while pending_tool_calls:
            for tool_call in pending_tool_calls:
                try:
                    func = tool_call.function

                    parameters = json.loads(func.arguments)

                    func_ret = await self.ap.tool_mgr.execute_func_call(query, func.name, parameters)

                    msg = llm_entities.Message(
                        role='tool',
                        content=json.dumps(func_ret, ensure_ascii=False),
                        tool_call_id=tool_call.id,
                    )

                    yield msg

                    req_messages.append(msg)
                except Exception as e:
                    # 工具调用出错，添加一个报错信息到 req_messages
                    err_msg = llm_entities.Message(role='tool', content=f'err: {e}', tool_call_id=tool_call.id)

                    yield err_msg

                    req_messages.append(err_msg)

            # 处理完所有调用，再次请求
            msg = await query.use_llm_model.requester.invoke_llm(
                query,
                query.use_llm_model,
                req_messages,
                query.use_funcs,
                extra_args=query.use_llm_model.model_entity.extra_args,
            )

            yield msg

            pending_tool_calls = msg.tool_calls

            req_messages.append(msg)
