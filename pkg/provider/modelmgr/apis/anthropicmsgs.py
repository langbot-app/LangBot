from __future__ import annotations

import typing
import traceback

import anthropic

from .. import api, entities, errors

from .. import api, entities, errors
from ....core import entities as core_entities
from ... import entities as llm_entities
from ...tools import entities as tools_entities
from ....utils import image


@api.requester_class("anthropic-messages")
class AnthropicMessages(api.LLMAPIRequester):
    """Anthropic Messages API 请求器"""

    client: anthropic.AsyncAnthropic

    async def initialize(self):
        self.client = anthropic.AsyncAnthropic(
            api_key="",
            base_url=self.ap.provider_cfg.data['requester']['anthropic-messages']['base-url'],
            timeout=self.ap.provider_cfg.data['requester']['anthropic-messages']['timeout'],
            proxies=self.ap.proxy_mgr.get_forward_proxies()
        )

    async def call(
        self,
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
            if isinstance(m.content, str) and m.content.strip() != "":
                req_messages.append(m.dict(exclude_none=True))
            elif isinstance(m.content, list):
                # m.content = [
                #     c for c in m.content if c.type == "text"
                # ]

                # if len(m.content) > 0:
                #     req_messages.append(m.dict(exclude_none=True))

                msg_dict = m.dict(exclude_none=True)

                for i, ce in enumerate(m.content):
                    if ce.type == "image_url":
                        base64_image, image_format = await image.qq_image_url_to_base64(ce.image_url.url)
                        alter_image_ele = {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": f"image/{image_format}",
                                "data": base64_image
                            }
                        }
                        msg_dict["content"][i] = alter_image_ele

                req_messages.append(msg_dict)

        args["messages"] = req_messages

        # anthropic的tools处在beta阶段，sdk不稳定，故暂时不支持
        #
        # if funcs:
        #     tools = await self.ap.tool_mgr.generate_tools_for_openai(funcs)

        #     if tools:
        #         args["tools"] = tools

        try:
            resp = await self.client.messages.create(**args)

            return llm_entities.Message(
                content=resp.content[0].text,
                role=resp.role
            )
        except anthropic.AuthenticationError as e:
            raise errors.RequesterError(f'api-key 无效: {e.message}')
        except anthropic.BadRequestError as e:
            raise errors.RequesterError(str(e.message))
        except anthropic.NotFoundError as e:
            if 'model: ' in str(e):
                raise errors.RequesterError(f'模型无效: {e.message}')
            else:
                raise errors.RequesterError(f'请求地址无效: {e.message}')
