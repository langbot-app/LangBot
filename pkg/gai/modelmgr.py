"""OpenAI 接口底层封装

目前使用的对话接口有：
ChatCompletion - gpt-3.5-turbo 等模型
Completion - text-davinci-003 等模型
此模块封装此两个接口的请求实现，为上层提供统一的调用方式
"""
import tiktoken
import openai

from ..gai.api import model as api_model
from ..gai.api import completion as api_completion
from ..gai.api import chat_completion as api_chat_completion

COMPLETION_MODELS = {
    "gpt-3.5-turbo-instruct",
}

CHAT_COMPLETION_MODELS = {
    # GPT 4 系列
    "gpt-4-1106-preview",
    "gpt-4-vision-preview",
    "gpt-4",
    "gpt-4-32k",
    "gpt-4-0613",
    "gpt-4-32k-0613",
    "gpt-4-0314", # legacy
    "gpt-4-32k-0314", # legacy
    # GPT 3.5 系列
    "gpt-3.5-turbo-1106",
    "gpt-3.5-turbo",
    "gpt-3.5-turbo-16k",
    "gpt-3.5-turbo-0613", # legacy
    "gpt-3.5-turbo-16k-0613", # legacy
    "gpt-3.5-turbo-0301", # legacy
    # One-API 接入
    "SparkDesk",
    "chatglm_pro",
    "chatglm_std",
    "chatglm_lite",
    "qwen-v1",
    "qwen-plus-v1",
    "ERNIE-Bot",
    "ERNIE-Bot-turbo",
    "gemini-pro",
}

EDIT_MODELS = {

}

IMAGE_MODELS = {

}


def select_request_cls(client: openai.Client, model_name: str, messages: list, args: dict) -> api_model.RequestBase:
    if model_name in CHAT_COMPLETION_MODELS:
        return api_chat_completion.ChatCompletionRequest(client, model_name, messages, **args)
    elif model_name in COMPLETION_MODELS:
        return api_completion.CompletionRequest(client, model_name, messages, **args)
    raise ValueError("不支持模型[{}]，请检查配置文件".format(model_name))


def count_chat_completion_tokens(messages: list, model: str) -> int:
    """Return the number of tokens used by a list of messages."""
    try:
        encoding = tiktoken.encoding_for_model(model)
    except KeyError:
        print("Warning: model not found. Using cl100k_base encoding.")
        encoding = tiktoken.get_encoding("cl100k_base")
    if model in {
        "gpt-3.5-turbo-0613",
        "gpt-3.5-turbo-16k-0613",
        "gpt-4-0314",
        "gpt-4-32k-0314",
        "gpt-4-0613",
        "gpt-4-32k-0613",
        "SparkDesk",
        "chatglm_pro",
        "chatglm_std",
        "chatglm_lite",
        "qwen-v1",
        "qwen-plus-v1",
        "ERNIE-Bot",
        "ERNIE-Bot-turbo",
        "gemini-pro",
        }:
        tokens_per_message = 3
        tokens_per_name = 1
    elif model == "gpt-3.5-turbo-0301":
        tokens_per_message = 4  # every message follows <|start|>{role/name}\n{content}<|end|>\n
        tokens_per_name = -1  # if there's a name, the role is omitted
    elif "gpt-3.5-turbo" in model:
        # print("Warning: gpt-3.5-turbo may update over time. Returning num tokens assuming gpt-3.5-turbo-0613.")
        return count_chat_completion_tokens(messages, model="gpt-3.5-turbo-0613")
    elif "gpt-4" in model:
        # print("Warning: gpt-4 may update over time. Returning num tokens assuming gpt-4-0613.")
        return count_chat_completion_tokens(messages, model="gpt-4-0613")
    else:
        raise NotImplementedError(
            f"""count_chat_completion_tokens() is not implemented for model {model}. See https://github.com/openai/openai-python/blob/main/chatml.md for information on how messages are converted to tokens."""
        )
    num_tokens = 0
    for message in messages:
        num_tokens += tokens_per_message
        for key, value in message.items():
            num_tokens += len(encoding.encode(value))
            if key == "name":
                num_tokens += tokens_per_name
    num_tokens += 3  # every reply is primed with <|start|>assistant<|message|>
    return num_tokens


def count_completion_tokens(messages: list, model: str) -> int:

    try:
        encoding = tiktoken.encoding_for_model(model)
    except KeyError:
        print("Warning: model not found. Using cl100k_base encoding.")
        encoding = tiktoken.get_encoding("cl100k_base")

    text = ""

    for message in messages:
        text += message['role'] + message['content'] + "\n"

    text += "assistant: "

    return len(encoding.encode(text))


def count_tokens(messages: list, model: str):

    if model in CHAT_COMPLETION_MODELS:
        return count_chat_completion_tokens(messages, model)
    elif model in COMPLETION_MODELS:
        return count_completion_tokens(messages, model)
    raise ValueError("不支持模型[{}]，请检查配置文件".format(model))
