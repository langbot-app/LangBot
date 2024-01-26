from __future__ import annotations

from . import entities
from ...core import app

from .apis import chatcmpl
from . import token


class ModelManager:

    ap: app.Application

    model_list: list[entities.LLMModelInfo]
    
    def __init__(self, ap: app.Application):
        self.ap = ap
        self.model_list = []

    async def initialize(self):
        openai_chat_completion = chatcmpl.OpenAIChatCompletion(self.ap)
        openai_token_mgr = token.TokenManager(self.ap, self.ap.cfg_mgr.data['openai_config']['api_key'].values())

        self.model_list.append(
            entities.LLMModelInfo(
                name="gpt-3.5-turbo",
                provider="openai",
                token_mgr=openai_token_mgr,
                requester=openai_chat_completion,
                function_call_supported=True
            )
        )

    async def get_model_by_name(self, name: str) -> entities.LLMModelInfo:
        """通过名称获取模型
        """
        for model in self.model_list:
            if model.name == name:
                return model
        raise ValueError(f"Model {name} not found")