from __future__ import annotations

from . import entities
from ...core import app

from .apis import chatcmpl
from . import token
from .tokenizers import tiktoken


class ModelManager:

    ap: app.Application

    model_list: list[entities.LLMModelInfo]
    
    def __init__(self, ap: app.Application):
        self.ap = ap
        self.model_list = []

    async def get_model_by_name(self, name: str) -> entities.LLMModelInfo:
        """通过名称获取模型
        """
        for model in self.model_list:
            if model.name == name:
                return model
        raise ValueError(f"Model {name} not found")

    async def initialize(self):
        openai_chat_completion = chatcmpl.OpenAIChatCompletion(self.ap)
        await openai_chat_completion.initialize()
        openai_token_mgr = token.TokenManager(self.ap, list(self.ap.provider_cfg.data['openai-config']['api-keys']))

        tiktoken_tokenizer = tiktoken.Tiktoken(self.ap)

        model_list = [
            entities.LLMModelInfo(
                name="gpt-3.5-turbo",
                token_mgr=openai_token_mgr,
                requester=openai_chat_completion,
                tool_call_supported=True,
                tokenizer=tiktoken_tokenizer,
                max_tokens=4096
            ),
            entities.LLMModelInfo(
                name="gpt-3.5-turbo-1106",
                token_mgr=openai_token_mgr,
                requester=openai_chat_completion,
                tool_call_supported=True,
                tokenizer=tiktoken_tokenizer,
                max_tokens=16385
            ),
            entities.LLMModelInfo(
                name="gpt-3.5-turbo-16k",
                token_mgr=openai_token_mgr,
                requester=openai_chat_completion,
                tool_call_supported=True,
                tokenizer=tiktoken_tokenizer,
                max_tokens=16385
            ),
            entities.LLMModelInfo(
                name="gpt-3.5-turbo-0613",
                token_mgr=openai_token_mgr,
                requester=openai_chat_completion,
                tool_call_supported=True,
                tokenizer=tiktoken_tokenizer,
                max_tokens=4096
            ),
            entities.LLMModelInfo(
                name="gpt-3.5-turbo-16k-0613",
                token_mgr=openai_token_mgr,
                requester=openai_chat_completion,
                tool_call_supported=True,
                tokenizer=tiktoken_tokenizer,
                max_tokens=16385
            ),
            entities.LLMModelInfo(
                name="gpt-3.5-turbo-0301",
                token_mgr=openai_token_mgr,
                requester=openai_chat_completion,
                tool_call_supported=True,
                tokenizer=tiktoken_tokenizer,
                max_tokens=4096
            )
        ]

        self.model_list.extend(model_list)

        gpt4_model_list = [
            entities.LLMModelInfo(
                name="gpt-4-0125-preview",
                token_mgr=openai_token_mgr,
                requester=openai_chat_completion,
                tool_call_supported=True,
                tokenizer=tiktoken_tokenizer,
                max_tokens=128000
            ),
            entities.LLMModelInfo(
                name="gpt-4-turbo-preview",
                token_mgr=openai_token_mgr,
                requester=openai_chat_completion,
                tool_call_supported=True,
                tokenizer=tiktoken_tokenizer,
                max_tokens=128000
            ),
            entities.LLMModelInfo(
                name="gpt-4-1106-preview",
                token_mgr=openai_token_mgr,
                requester=openai_chat_completion,
                tool_call_supported=True,
                tokenizer=tiktoken_tokenizer,
                max_tokens=128000
            ),
            entities.LLMModelInfo(
                name="gpt-4-vision-preview",
                token_mgr=openai_token_mgr,
                requester=openai_chat_completion,
                tool_call_supported=True,
                tokenizer=tiktoken_tokenizer,
                max_tokens=128000
            ),
            entities.LLMModelInfo(
                name="gpt-4",
                token_mgr=openai_token_mgr,
                requester=openai_chat_completion,
                tool_call_supported=True,
                tokenizer=tiktoken_tokenizer,
                max_tokens=8192
            ),
            entities.LLMModelInfo(
                name="gpt-4-0613",
                token_mgr=openai_token_mgr,
                requester=openai_chat_completion,
                tool_call_supported=True,
                tokenizer=tiktoken_tokenizer,
                max_tokens=8192
            ),
            entities.LLMModelInfo(
                name="gpt-4-32k",
                token_mgr=openai_token_mgr,
                requester=openai_chat_completion,
                tool_call_supported=True,
                tokenizer=tiktoken_tokenizer,
                max_tokens=32768
            ),
            entities.LLMModelInfo(
                name="gpt-4-32k-0613",
                token_mgr=openai_token_mgr,
                requester=openai_chat_completion,
                tool_call_supported=True,
                tokenizer=tiktoken_tokenizer,
                max_tokens=32768
            )
        ]

        self.model_list.extend(gpt4_model_list)

        one_api_model_list = [
            entities.LLMModelInfo(
                name="OneAPI/SparkDesk",
                model_name='SparkDesk',
                token_mgr=openai_token_mgr,
                requester=openai_chat_completion,
                tool_call_supported=False,
                tokenizer=tiktoken_tokenizer,
                max_tokens=8192
            ),
            entities.LLMModelInfo(
                name="OneAPI/chatglm_pro",
                model_name='chatglm_pro',
                token_mgr=openai_token_mgr,
                requester=openai_chat_completion,
                tool_call_supported=False,
                tokenizer=tiktoken_tokenizer,
                max_tokens=128000
            ),
            entities.LLMModelInfo(
                name="OneAPI/chatglm_std",
                model_name='chatglm_std',
                token_mgr=openai_token_mgr,
                requester=openai_chat_completion,
                tool_call_supported=False,
                tokenizer=tiktoken_tokenizer,
                max_tokens=128000
            ),
            entities.LLMModelInfo(
                name="OneAPI/chatglm_lite",
                model_name='chatglm_lite',
                token_mgr=openai_token_mgr,
                requester=openai_chat_completion,
                tool_call_supported=False,
                tokenizer=tiktoken_tokenizer,
                max_tokens=128000
            ),
            entities.LLMModelInfo(
                name="OneAPI/qwen-v1",
                model_name='qwen-v1',
                token_mgr=openai_token_mgr,
                requester=openai_chat_completion,
                tool_call_supported=False,
                tokenizer=tiktoken_tokenizer,
                max_tokens=6000
            ),
            entities.LLMModelInfo(
                name="OneAPI/qwen-plus-v1",
                model_name='qwen-plus-v1',
                token_mgr=openai_token_mgr,
                requester=openai_chat_completion,
                tool_call_supported=False,
                tokenizer=tiktoken_tokenizer,
                max_tokens=30000
            ),
            entities.LLMModelInfo(
                name="OneAPI/ERNIE-Bot",
                model_name='ERNIE-Bot',
                token_mgr=openai_token_mgr,
                requester=openai_chat_completion,
                tool_call_supported=False,
                tokenizer=tiktoken_tokenizer,
                max_tokens=2000
            ),
            entities.LLMModelInfo(
                name="OneAPI/ERNIE-Bot-turbo",
                model_name='ERNIE-Bot-turbo',
                token_mgr=openai_token_mgr,
                requester=openai_chat_completion,
                tool_call_supported=False,
                tokenizer=tiktoken_tokenizer,
                max_tokens=7000
            ),
            entities.LLMModelInfo(
                name="OneAPI/gemini-pro",
                model_name='gemini-pro',
                token_mgr=openai_token_mgr,
                requester=openai_chat_completion,
                tool_call_supported=False,
                tokenizer=tiktoken_tokenizer,
                max_tokens=30720
            ),
        ]

        self.model_list.extend(one_api_model_list)
