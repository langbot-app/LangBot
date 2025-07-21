from __future__ import annotations

import json
import copy
import typing
from .. import runner
from ...core import entities as core_entities
from .. import entities as llm_entities


rag_combined_prompt_template = """
The following are relevant context entries retrieved from the knowledge base. 
Please use them to answer the user's message. 
Respond in the same language as the user's input.

<context>
{rag_context}
</context>

<user_message>
{user_message}
</user_message>
"""


@runner.runner_class('local-agent')
class LocalAgentRunner(runner.RequestRunner):
    """本地Agent请求运行器"""

    async def run(self, query: core_entities.Query) -> typing.AsyncGenerator[llm_entities.Message, None]:
        """运行请求"""
        pending_tool_calls = []

        kb_uuid = query.pipeline_config['ai']['local-agent']['knowledge-base']

        if kb_uuid == '__none__':
            kb_uuid = None

        user_message = copy.deepcopy(query.user_message)

        user_message_text = ''

        if isinstance(user_message.content, str):
            user_message_text = user_message.content
        elif isinstance(user_message.content, list):
            for ce in user_message.content:
                if ce.type == 'text':
                    user_message_text += ce.text
                    break

        if kb_uuid and user_message_text:
            # only support text for now
            kb = await self.ap.rag_mgr.get_knowledge_base_by_uuid(kb_uuid)

            if not kb:
                self.ap.logger.warning(f'Knowledge base {kb_uuid} not found')
                raise ValueError(f'Knowledge base {kb_uuid} not found')

            result = await kb.retrieve(user_message_text)

            final_user_message_text = ''

            if result:
                rag_context = '\n\n'.join(
                    f'[{i + 1}] {entry.metadata.get("text", "")}' for i, entry in enumerate(result)
                )
                final_user_message_text = rag_combined_prompt_template.format(
                    rag_context=rag_context, user_message=user_message_text
                )

            else:
                final_user_message_text = user_message_text

            self.ap.logger.debug(f'Final user message text: {final_user_message_text}')

            for ce in user_message.content:
                if ce.type == 'text':
                    ce.text = final_user_message_text
                    break

        req_messages = query.prompt.messages.copy() + query.messages.copy() + [user_message]

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
