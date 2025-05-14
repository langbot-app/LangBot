from __future__ import annotations

import typing
import google.generativeai as genai

from .. import errors, requester
from ....core import entities as core_entities
from ... import entities as llm_entities
from ...tools import entities as tools_entities


class GeminiChatCompletions(requester.LLMAPIRequester):
    """Google Gemini API 请求器"""

    default_config: dict[str, typing.Any] = {
        'base_url': 'https://generativelanguage.googleapis.com',
        'timeout': 120,
    }

    async def initialize(self):
        """初始化 Gemini API 客户端"""
        pass

    async def invoke_llm(
        self,
        query: core_entities.Query,
        model: requester.RuntimeLLMModel,
        messages: typing.List[llm_entities.Message],
        funcs: typing.List[tools_entities.LLMFunction] = None,
        extra_args: dict[str, typing.Any] = {},
    ) -> llm_entities.Message:
        """调用 Gemini API 生成回复"""
        try:
            genai.configure(
                api_key=model.token_mgr.get_token(),
                transport='rest',
                client_options={
                    'api_endpoint': self.requester_cfg['base_url'],
                }
            )
            
            generation_model = genai.GenerativeModel(model.model_entity.name)
            
            history = []
            system_content = None
            
            for msg in messages:
                if msg.role == 'system':
                    system_content = msg.content
                    break
            
            for msg in messages:
                if msg.role == 'system':
                    continue  # 系统消息单独处理
                
                role = 'user' if msg.role == 'user' else 'model'
                
                content = msg.content
                if isinstance(content, list):
                    parts = []
                    for part in content:
                        if part.get('type') == 'text':
                            parts.append(part.get('text', ''))
                    content = '\n'.join(parts)
                
                history.append({
                    'role': role,
                    'parts': [content]
                })
            
            if system_content:
                system_msg = {
                    'role': 'user',
                    'parts': [f"System instruction: {system_content}\n\nPlease follow the above instruction for all future interactions."]
                }
                ack_msg = {
                    'role': 'model',
                    'parts': ["I'll follow those instructions."]
                }
                history = [system_msg, ack_msg] + history
            
            chat = generation_model.start_chat(history=history)
            
            message_content = query.content if query.content else "Please continue the conversation."
            response = chat.send_message(message_content)
            
            return llm_entities.Message(
                role='assistant',
                content=response.text
            )
                
        except Exception as e:
            error_message = str(e).lower()
            if 'invalid api key' in error_message:
                raise errors.RequesterError(f'无效的 API 密钥: {str(e)}')
            elif 'not found' in error_message:
                raise errors.RequesterError(f'请求路径错误或模型无效: {str(e)}')
            elif any(keyword in error_message for keyword in ['rate limit', 'quota', 'permission denied']):
                raise errors.RequesterError(f'请求过于频繁或余额不足: {str(e)}')
            elif 'timeout' in error_message:
                raise errors.RequesterError(f'请求超时: {str(e)}')
            else:
                raise errors.RequesterError(f'Gemini API 请求错误: {str(e)}')
