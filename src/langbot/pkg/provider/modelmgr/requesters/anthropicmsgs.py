from __future__ import annotations

import typing
import json
import platform
import socket
import anthropic
import httpx

from .. import errors, requester

from ....utils import image
import langbot_plugin.api.entities.builtin.resource.tool as resource_tool
import langbot_plugin.api.entities.builtin.pipeline.query as pipeline_query
import langbot_plugin.api.entities.builtin.provider.message as provider_message


class AnthropicMessages(requester.ProviderAPIRequester):
    """Anthropic Messages API 请求器"""

    client: anthropic.AsyncAnthropic

    default_config: dict[str, typing.Any] = {
        'base_url': 'https://api.anthropic.com',
        'timeout': 120,
    }

    async def initialize(self):
        # 兼容 Windows 缺失 TCP_KEEPINTVL 和 TCP_KEEPCNT 的问题
        if platform.system() == 'Windows':
            if not hasattr(socket, 'TCP_KEEPINTVL'):
                socket.TCP_KEEPINTVL = 0
            if not hasattr(socket, 'TCP_KEEPCNT'):
                socket.TCP_KEEPCNT = 0
        httpx_client = anthropic._base_client.AsyncHttpxClientWrapper(
            base_url=self.requester_cfg['base_url'],
            # cast to a valid type because mypy doesn't understand our type narrowing
            timeout=typing.cast(httpx.Timeout, self.requester_cfg['timeout']),
            limits=anthropic._constants.DEFAULT_CONNECTION_LIMITS,
            follow_redirects=True,
            trust_env=True,
        )

        self.client = anthropic.AsyncAnthropic(
            api_key='',
            http_client=httpx_client,
            base_url=self.requester_cfg['base_url'],
        )

    async def invoke_llm(
        self,
        query: pipeline_query.Query,
        model: requester.RuntimeLLMModel,
        messages: typing.List[provider_message.Message],
        funcs: typing.List[resource_tool.LLMTool] = None,
        extra_args: dict[str, typing.Any] = {},
        remove_think: bool = False,
    ) -> provider_message.Message:
        self.client.api_key = model.token_mgr.get_token()

        args = extra_args.copy()
        args['model'] = model.model_entity.name

        # 处理消息

        # system
        system_role_message = None

        for i, m in enumerate(messages):
            if m.role == 'system':
                system_role_message = m

                break

        if system_role_message:
            messages.pop(i)

        if isinstance(system_role_message, provider_message.Message) and isinstance(system_role_message.content, str):
            args['system'] = system_role_message.content

        req_messages = []

        for m in messages:
            if m.role == 'tool':
                tool_call_id = m.tool_call_id

                req_messages.append(
                    {
                        'role': 'user',
                        'content': [
                            {
                                'type': 'tool_result',
                                'tool_use_id': tool_call_id,
                                'is_error': False,
                                'content': [{'type': 'text', 'text': m.content}],
                            }
                        ],
                    }
                )

                continue

            msg_dict = m.dict(exclude_none=True)

            if isinstance(m.content, str) and m.content.strip() != '':
                msg_dict['content'] = [{'type': 'text', 'text': m.content}]
            elif isinstance(m.content, list):
                for i, ce in enumerate(m.content):
                    if ce.type == 'image_base64':
                        image_b64, image_format = await image.extract_b64_and_format(ce.image_base64)

                        alter_image_ele = {
                            'type': 'image',
                            'source': {
                                'type': 'base64',
                                'media_type': f'image/{image_format}',
                                'data': image_b64,
                            },
                        }
                        msg_dict['content'][i] = alter_image_ele

            if m.tool_calls:
                for tool_call in m.tool_calls:
                    msg_dict['content'].append(
                        {
                            'type': 'tool_use',
                            'id': tool_call.id,
                            'name': tool_call.function.name,
                            'input': json.loads(tool_call.function.arguments),
                        }
                    )

                del msg_dict['tool_calls']

            req_messages.append(msg_dict)

        args['messages'] = req_messages

        if 'thinking' in args:
            args['thinking'] = {'type': 'enabled', 'budget_tokens': 10000}

        if funcs:
            tools = await self.ap.tool_mgr.generate_tools_for_anthropic(funcs)

            if tools:
                args['tools'] = tools

        try:
            resp = await self.client.messages.create(**args)

            args = {
                'content': '',
                'role': resp.role,
            }
            assert type(resp) is anthropic.types.message.Message

            for block in resp.content:
                if not remove_think and block.type == 'thinking':
                    args['content'] = '<think>\n' + block.thinking + '\n</think>\n' + args['content']
                elif block.type == 'text':
                    args['content'] += block.text
                elif block.type == 'tool_use':
                    assert type(block) is anthropic.types.tool_use_block.ToolUseBlock
                    tool_call = provider_message.ToolCall(
                        id=block.id,
                        type='function',
                        function=provider_message.FunctionCall(name=block.name, arguments=json.dumps(block.input)),
                    )
                    if 'tool_calls' not in args:
                        args['tool_calls'] = []
                    args['tool_calls'].append(tool_call)

            return provider_message.Message(**args)
        except anthropic.AuthenticationError as e:
            raise errors.RequesterError(f'api-key 无效: {e.message}')
        except anthropic.BadRequestError as e:
            raise errors.RequesterError(str(e.message))
        except anthropic.NotFoundError as e:
            if 'model: ' in str(e):
                raise errors.RequesterError(f'模型无效: {e.message}')
            else:
                raise errors.RequesterError(f'请求地址无效: {e.message}')

    async def invoke_llm_stream(
        self,
        query: pipeline_query.Query,
        model: requester.RuntimeLLMModel,
        messages: typing.List[provider_message.Message],
        funcs: typing.List[resource_tool.LLMTool] = None,
        extra_args: dict[str, typing.Any] = {},
        remove_think: bool = False,
    ) -> provider_message.Message:
        self.client.api_key = model.token_mgr.get_token()

        args = extra_args.copy()
        args['model'] = model.model_entity.name
        args['stream'] = True

        # 处理消息

        # system
        system_role_message = None

        for i, m in enumerate(messages):
            if m.role == 'system':
                system_role_message = m

                break

        if system_role_message:
            messages.pop(i)

        if isinstance(system_role_message, provider_message.Message) and isinstance(system_role_message.content, str):
            args['system'] = system_role_message.content

        req_messages = []

        for m in messages:
            if m.role == 'tool':
                tool_call_id = m.tool_call_id

                req_messages.append(
                    {
                        'role': 'user',
                        'content': [
                            {
                                'type': 'tool_result',
                                'tool_use_id': tool_call_id,
                                'is_error': False,  # 暂时直接写false
                                'content': [
                                    {'type': 'text', 'text': m.content}
                                ],  # 这里要是list包裹，应该是多个返回的情况？type类型好像也可以填其他的，暂时只写text
                            }
                        ],
                    }
                )

                continue

            msg_dict = m.dict(exclude_none=True)

            if isinstance(m.content, str) and m.content.strip() != '':
                msg_dict['content'] = [{'type': 'text', 'text': m.content}]
            elif isinstance(m.content, list):
                for i, ce in enumerate(m.content):
                    if ce.type == 'image_base64':
                        image_b64, image_format = await image.extract_b64_and_format(ce.image_base64)

                        alter_image_ele = {
                            'type': 'image',
                            'source': {
                                'type': 'base64',
                                'media_type': f'image/{image_format}',
                                'data': image_b64,
                            },
                        }
                        msg_dict['content'][i] = alter_image_ele
            if isinstance(msg_dict['content'], str) and msg_dict['content'] == '':
                msg_dict['content'] = []  # 这里不知道为什么会莫名有个空导致content为字符
            if m.tool_calls:
                for tool_call in m.tool_calls:
                    msg_dict['content'].append(
                        {
                            'type': 'tool_use',
                            'id': tool_call.id,
                            'name': tool_call.function.name,
                            'input': json.loads(tool_call.function.arguments),
                        }
                    )

                del msg_dict['tool_calls']

            req_messages.append(msg_dict)
        if 'thinking' in args:
            args['thinking'] = {'type': 'enabled', 'budget_tokens': 10000}

        args['messages'] = req_messages

        if funcs:
            tools = await self.ap.tool_mgr.generate_tools_for_anthropic(funcs)

            if tools:
                args['tools'] = tools

        try:
            role = 'assistant'  # 默认角色
            # chunk_idx = 0
            think_started = False
            think_ended = False
            finish_reason = False
            content = ''
            tool_name = ''
            tool_id = ''
            async for chunk in await self.client.messages.create(**args):
                tool_call = {'id': None, 'function': {'name': None, 'arguments': None}, 'type': 'function'}
                if isinstance(
                    chunk, anthropic.types.raw_content_block_start_event.RawContentBlockStartEvent
                ):  # 记录开始
                    if chunk.content_block.type == 'tool_use':
                        if chunk.content_block.name is not None:
                            tool_name = chunk.content_block.name
                        if chunk.content_block.id is not None:
                            tool_id = chunk.content_block.id

                        tool_call['function']['name'] = tool_name
                        tool_call['function']['arguments'] = ''
                        tool_call['id'] = tool_id

                    if not remove_think:
                        if chunk.content_block.type == 'thinking' and not remove_think:
                            think_started = True
                        elif chunk.content_block.type == 'text' and chunk.index != 0 and not remove_think:
                            think_ended = True
                        continue
                elif isinstance(chunk, anthropic.types.raw_content_block_delta_event.RawContentBlockDeltaEvent):
                    if chunk.delta.type == 'thinking_delta':
                        if think_started:
                            think_started = False
                            content = '<think>\n' + chunk.delta.thinking
                        elif remove_think:
                            continue
                        else:
                            content = chunk.delta.thinking
                    elif chunk.delta.type == 'text_delta':
                        if think_ended:
                            think_ended = False
                            content = '\n</think>\n' + chunk.delta.text
                        else:
                            content = chunk.delta.text
                    elif chunk.delta.type == 'input_json_delta':
                        tool_call['function']['arguments'] = chunk.delta.partial_json
                        tool_call['function']['name'] = tool_name
                        tool_call['id'] = tool_id
                elif isinstance(chunk, anthropic.types.raw_content_block_stop_event.RawContentBlockStopEvent):
                    continue  # 记录raw_content_block结束的

                elif isinstance(chunk, anthropic.types.raw_message_delta_event.RawMessageDeltaEvent):
                    if chunk.delta.stop_reason == 'end_turn':
                        finish_reason = True
                elif isinstance(chunk, anthropic.types.raw_message_stop_event.RawMessageStopEvent):
                    continue  # 这个好像是完全结束
                else:
                    # print(chunk)
                    self.ap.logger.debug(f'anthropic chunk: {chunk}')
                    continue

                args = {
                    'content': content,
                    'role': role,
                    'is_final': finish_reason,
                    'tool_calls': None if tool_call['id'] is None else [tool_call],
                }
                # if chunk_idx == 0:
                #     chunk_idx += 1
                #     continue

                # assert type(chunk) is anthropic.types.message.Chunk

                yield provider_message.MessageChunk(**args)

            # return llm_entities.Message(**args)
        except anthropic.AuthenticationError as e:
            raise errors.RequesterError(f'api-key 无效: {e.message}')
        except anthropic.BadRequestError as e:
            raise errors.RequesterError(str(e.message))
        except anthropic.NotFoundError as e:
            if 'model: ' in str(e):
                raise errors.RequesterError(f'模型无效: {e.message}')
            else:
                raise errors.RequesterError(f'请求地址无效: {e.message}')
