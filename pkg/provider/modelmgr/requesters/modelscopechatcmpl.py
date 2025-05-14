from __future__ import annotations

import asyncio
import typing

import openai
import openai.types.chat.chat_completion as chat_completion
import openai.types.chat.chat_completion_message_tool_call as chat_completion_message_tool_call
import httpx

from .. import entities, errors, requester
from ....core import entities as core_entities
from ... import entities as llm_entities
from ...tools import entities as tools_entities


class ModelScopeChatCompletions(requester.LLMAPIRequester):
    """ModelScope ChatCompletion API 请求器"""

    client: openai.AsyncClient

    default_config: dict[str, typing.Any] = {
        'base_url': 'https://api-inference.modelscope.cn/v1',
        'timeout': 120,
    }

    async def initialize(self):
        self.client = openai.AsyncClient(
            api_key='',
            base_url=self.requester_cfg['base_url'],
            timeout=self.requester_cfg['timeout'],
            http_client=httpx.AsyncClient(trust_env=True, timeout=self.requester_cfg['timeout']),
        )

    async def _req(
        self,
        args: dict,
        extra_body: dict = {},
    ) -> chat_completion.ChatCompletion:
        args['stream'] = True

        chunk = None

        pending_content = ''

        tool_calls = []

        resp_gen: openai.AsyncStream = await self.client.chat.completions.create(**args, extra_body=extra_body)

        async for chunk in resp_gen:
            # print(chunk)
            if not chunk or not chunk.id or not chunk.choices or not chunk.choices[0] or not chunk.choices[0].delta:
                continue

            if chunk.choices[0].delta.content is not None:
                pending_content += chunk.choices[0].delta.content

            if chunk.choices[0].delta.tool_calls is not None:
                for tool_call in chunk.choices[0].delta.tool_calls:
                    for tc in tool_calls:
                        if tc.index == tool_call.index:
                            tc.function.arguments += tool_call.function.arguments
                            break
                    else:
                        tool_calls.append(tool_call)

            if chunk.choices[0].finish_reason is not None:
                break

        real_tool_calls = []

        for tc in tool_calls:
            function = chat_completion_message_tool_call.Function(
                name=tc.function.name, arguments=tc.function.arguments
            )
            real_tool_calls.append(
                chat_completion_message_tool_call.ChatCompletionMessageToolCall(
                    id=tc.id, function=function, type='function'
                )
            )

        return (
            chat_completion.ChatCompletion(
                id=chunk.id,
                object='chat.completion',
                created=chunk.created,
                choices=[
                    chat_completion.Choice(
                        index=0,
                        message=chat_completion.ChatCompletionMessage(
                            role='assistant',
                            content=pending_content,
                            tool_calls=real_tool_calls if len(real_tool_calls) > 0 else None,
                        ),
                        finish_reason=chunk.choices[0].finish_reason
                        if hasattr(chunk.choices[0], 'finish_reason') and chunk.choices[0].finish_reason is not None
                        else 'stop',
                        logprobs=chunk.choices[0].logprobs,
                    )
                ],
                model=chunk.model,
                service_tier=chunk.service_tier if hasattr(chunk, 'service_tier') else None,
                system_fingerprint=chunk.system_fingerprint if hasattr(chunk, 'system_fingerprint') else None,
                usage=chunk.usage if hasattr(chunk, 'usage') else None,
            )
            if chunk
            else None
        )

    async def _make_msg(
        self,
        chat_completion: chat_completion.ChatCompletion,
    ) -> llm_entities.Message:
        chatcmpl_message = chat_completion.choices[0].message.dict()

        # 确保 role 字段存在且不为 None
        if 'role' not in chatcmpl_message or chatcmpl_message['role'] is None:
            chatcmpl_message['role'] = 'assistant'

        message = llm_entities.Message(**chatcmpl_message)

        return message

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

        # 设置此次请求中的messages
        messages = req_messages.copy()

        # 检查vision
        for msg in messages:
            if 'content' in msg and isinstance(msg['content'], list):
                for me in msg['content']:
                    if me['type'] == 'image_base64':
                        me['image_url'] = {'url': me['image_base64']}
                        me['type'] = 'image_url'
                        del me['image_base64']

        args['messages'] = messages

        # 发送请求
        resp = await self._req(args, extra_body=extra_args)

        # 处理请求结果
        message = await self._make_msg(resp)

        return message

    async def invoke_llm(
        self,
        query: core_entities.Query,
        model: entities.LLMModelInfo,
        messages: typing.List[llm_entities.Message],
        funcs: typing.List[tools_entities.LLMFunction] = None,
        extra_args: dict[str, typing.Any] = {},
    ) -> llm_entities.Message:
        req_messages = []  # req_messages 仅用于类内，外部同步由 query.messages 进行
        for m in messages:
            msg_dict = m.dict(exclude_none=True)
            content = msg_dict.get('content')
            if isinstance(content, list):
                # 检查 content 列表中是否每个部分都是文本
                if all(isinstance(part, dict) and part.get('type') == 'text' for part in content):
                    # 将所有文本部分合并为一个字符串
                    msg_dict['content'] = '\n'.join(part['text'] for part in content)
            req_messages.append(msg_dict)

        try:
            return await self._closure(
                query=query, req_messages=req_messages, use_model=model, use_funcs=funcs, extra_args=extra_args
            )
        except asyncio.TimeoutError:
            raise errors.RequesterError('请求超时')
        except openai.BadRequestError as e:
            if 'context_length_exceeded' in e.message:
                raise errors.RequesterError(f'上文过长，请重置会话: {e.message}')
            else:
                raise errors.RequesterError(f'请求参数错误: {e.message}')
        except openai.AuthenticationError as e:
            raise errors.RequesterError(f'无效的 api-key: {e.message}')
        except openai.NotFoundError as e:
            raise errors.RequesterError(f'请求路径错误: {e.message}')
        except openai.RateLimitError as e:
            raise errors.RequesterError(f'请求过于频繁或余额不足: {e.message}')
        except openai.APIError as e:
            raise errors.RequesterError(f'请求错误: {e.message}')
