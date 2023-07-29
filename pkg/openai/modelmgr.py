"""OpenAI 接口底层封装

目前使用的对话接口有：
ChatCompletion - gpt-3.5-turbo 等模型
Completion - text-davinci-003 等模型
此模块封装此两个接口的请求实现，为上层提供统一的调用方式
"""
import openai, logging, threading, asyncio
import openai.error as aiE

from pkg.openai.api.model import RequestBase
from pkg.openai.api.completion import CompletionRequest
from pkg.openai.api.chat_completion import ChatCompletionRequest

COMPLETION_MODELS = {
    'text-davinci-003',
    'text-davinci-002',
    'code-davinci-002',
    'code-cushman-001',
    'text-curie-001',
    'text-babbage-001',
    'text-ada-001',
}

CHAT_COMPLETION_MODELS = {
    'gpt-3.5-turbo',
    'gpt-3.5-turbo-16k',
    'gpt-3.5-turbo-0613',
    'gpt-3.5-turbo-16k-0613',
    # 'gpt-3.5-turbo-0301',
    'gpt-4',
    'gpt-4-0613',
    'gpt-4-32k',
    'gpt-4-32k-0613'
}

EDIT_MODELS = {

}

IMAGE_MODELS = {

}


def select_request_cls(model_name: str, messages: list, args: dict) -> RequestBase:
    if model_name in CHAT_COMPLETION_MODELS:
        return ChatCompletionRequest(model_name, messages, **args)
    elif model_name in COMPLETION_MODELS:
        return CompletionRequest(model_name, messages, **args)
    raise ValueError("不支持模型[{}]，请检查配置文件".format(model_name))