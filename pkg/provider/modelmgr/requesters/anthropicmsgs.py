from __future__ import annotations

import typing
import json
import traceback
import base64

import anthropic
import httpx

from .. import entities, errors, requester

from .. import entities, errors
from ....core import entities as core_entities
from ... import entities as llm_entities
from ...tools import entities as tools_entities
from ....utils import image


class AnthropicMessages(requester.LLMAPIRequester):
    """Anthropic Messages API 请求器"""

    client: anthropic.AsyncAnthropic

    async def initialize(self):

        httpx_client = anthropic._base_client.AsyncHttpxClientWrapper(
            base_url=self.ap.provider_cfg.data['requester']['anthropic-messages']['base-url'],
            # cast to a valid type because mypy doesn't understand our type narrowing
            timeout=typing.cast(httpx.Timeout, self.ap.provider_cfg.data['requester']['anthropic-messages']['timeout']),
            limits=anthropic._constants.DEFAULT_CONNECTION_LIMITS,
            follow_redirects=True,
            trust_env=True,
        )

        self.client = anthropic.AsyncAnthropic(
            api_key="",
            http_client=httpx_client,
        )

    async def call(
        self,
        query: core_entities.Query,
        model: entities.LLMModelInfo,
        messages: typing.List[llm_entities.Message],
        funcs: typing.List[tools_entities.LLMFunction] = None,
    ) -> llm_entities.Message:
        self.client.api_key = model.token_mgr.get_token()

        args = self.ap.provider_cfg.data['requester']['anthropic-messages']['args'].copy()
        args["model"] = model.name if model.model_name is None else model.model_name

        # 处理消息

        # system
        system_role_message = None

        for i, m in enumerate(messages):
            if m.role == "system":
                system_role_message = m

                messages.pop(i)
                break

        if isinstance(system_role_message, llm_entities.Message) \
            and isinstance(system_role_message.content, str):
            args['system'] = system_role_message.content

        req_messages = []

        for m in messages:
            if m.role == 'tool':
                tool_call_id = m.tool_call_id

                req_messages.append({
                    "role": "user",
                    "content": [
                        {
                            "type": "tool_result",
                            "tool_use_id": tool_call_id,
                            "content": m.content
                        }
                    ]
                })

                continue

            msg_dict = m.dict(exclude_none=True)

            if isinstance(m.content, str) and m.content.strip() != "":
                msg_dict["content"] = [
                    {
                        "type": "text",
                        "text": m.content
                    }
                ]
            elif isinstance(m.content, list):

                for i, ce in enumerate(m.content):

                    if ce.type == "image_base64":
                        image_b64, image_format = await image.extract_b64_and_format(ce.image_base64)

                        alter_image_ele = {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": f"image/{image_format}",
                                "data": image_b64
                            }
                        }
                        msg_dict["content"][i] = alter_image_ele

            if m.tool_calls:

                for tool_call in m.tool_calls:
                    msg_dict["content"].append({
                        "type": "tool_use",
                        "id": tool_call.id,
                        "name": tool_call.function.name,
                        "input": json.loads(tool_call.function.arguments)
                    })

                del msg_dict["tool_calls"]

            req_messages.append(msg_dict)
                

        args["messages"] = req_messages
        
        if funcs:
            tools = await self.ap.tool_mgr.generate_tools_for_anthropic(funcs)

            if tools:
                args["tools"] = tools

        try:
            # print(json.dumps(args, indent=4, ensure_ascii=False))
            resp = await self.client.messages.create(**args)

            args = {
                'content': '',
                'role': resp.role,
            }
            
            assert type(resp) is anthropic.types.message.Message

            for block in resp.content:
                if block.type == 'thinking':
                    args['content'] = '<think>' + block.thinking + '</think>\n' + args['content']
                elif block.type == 'text':
                    args['content'] += block.text
                elif block.type == 'tool_use':
                    assert type(block) is anthropic.types.tool_use_block.ToolUseBlock
                    tool_call = llm_entities.ToolCall(
                        id=block.id,
                        type="function",
                        function=llm_entities.FunctionCall(
                            name=block.name,
                            arguments=json.dumps(block.input)
                        )
                    )
                    if 'tool_calls' not in args:
                        args['tool_calls'] = []
                    args['tool_calls'].append(tool_call)

            return llm_entities.Message(**args)
        except anthropic.AuthenticationError as e:
            raise errors.RequesterError(f'api-key 无效: {e.message}')
        except anthropic.BadRequestError as e:
            raise errors.RequesterError(str(e.message))
        except anthropic.NotFoundError as e:
            if 'model: ' in str(e):
                raise errors.RequesterError(f'模型无效: {e.message}')
            else:
                raise errors.RequesterError(f'请求地址无效: {e.message}')
