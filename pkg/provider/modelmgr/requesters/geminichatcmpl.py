from __future__ import annotations

import typing
import google.generativeai as genai

from .. import errors, requester
from ....core import entities as core_entities
from ... import entities as llm_entities
from ...tools import entities as tools_entities


class GeminiChatCompletions(requester.LLMAPIRequester):
    """Google Gemini API 请求器"""

    client: genai.GenerativeModel

    default_config: dict[str, typing.Any] = {
        'base_url': 'https://generativelanguage.googleapis.com',
        'timeout': 120,
    }

    async def initialize(self):
        genai.configure(
            api_key='',
            transport='rest',
            client_options={
                'api_endpoint': self.requester_cfg['base_url'],
                'timeout': self.requester_cfg['timeout'],
            },
        )

    async def invoke_llm(
        self,
        query: core_entities.Query,
        model: requester.RuntimeLLMModel,
        messages: typing.List[llm_entities.Message],
        funcs: typing.List[tools_entities.LLMFunction] = None,
        extra_args: dict[str, typing.Any] = {},
    ) -> llm_entities.Message:
        genai.configure(api_key=model.token_mgr.get_token())

        generation_model = genai.GenerativeModel(model.model_entity.name)

        gemini_messages = []
        
        system_content = None
        for i, m in enumerate(messages):
            if m.role == 'system':
                system_content = m.content
                break
        
        for m in messages:
            if m.role == 'system':
                continue  # Skip system message as it's handled separately
            
            if m.role == 'user':
                role = 'user'
            elif m.role == 'assistant':
                role = 'model'
            else:
                continue  # Skip other roles for now
            
            content = m.content
            if isinstance(content, list):
                parts = []
                for part in content:
                    if part.get('type') == 'text':
                        parts.append(part.get('text', ''))
                content = '\n'.join(parts)
            
            gemini_messages.append({'role': role, 'parts': [content]})
        
        try:
            chat_params = extra_args.copy()
            if system_content:
                chat_params['system_instruction'] = system_content
            
            chat = generation_model.start_chat(history=gemini_messages)
            
            response = await chat.send_message_async(
                content="",  # Empty content to get response based on history
                **chat_params
            )
            
            content = response.text
            
            return llm_entities.Message(
                role='assistant',
                content=content
            )
        except Exception as e:
            if 'invalid api key' in str(e).lower():
                raise errors.RequesterError(f'无效的 api-key: {str(e)}')
            elif 'not found' in str(e).lower():
                raise errors.RequesterError(f'请求路径错误或模型无效: {str(e)}')
            elif 'rate limit' in str(e).lower() or 'quota' in str(e).lower():
                raise errors.RequesterError(f'请求过于频繁或余额不足: {str(e)}')
            else:
                raise errors.RequesterError(f'请求错误: {str(e)}')
