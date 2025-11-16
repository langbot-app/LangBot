from __future__ import annotations

import abc
import typing

from ...core import app
from ...entity.persistence import model as persistence_model
import langbot_plugin.api.entities.builtin.resource.tool as resource_tool
from . import token
import langbot_plugin.api.entities.builtin.pipeline.query as pipeline_query
import langbot_plugin.api.entities.builtin.provider.message as provider_message


class RuntimeLLMModel:
    """运行时模型"""

    model_entity: persistence_model.LLMModel
    """模型数据"""

    token_mgr: token.TokenManager
    """api key管理器"""

    requester: ProviderAPIRequester
    """请求器实例"""

    def __init__(
        self,
        model_entity: persistence_model.LLMModel,
        token_mgr: token.TokenManager,
        requester: ProviderAPIRequester,
    ):
        self.model_entity = model_entity
        self.token_mgr = token_mgr
        self.requester = requester


class RuntimeEmbeddingModel:
    """运行时 Embedding 模型"""

    model_entity: persistence_model.EmbeddingModel
    """模型数据"""

    token_mgr: token.TokenManager
    """api key管理器"""

    requester: ProviderAPIRequester
    """请求器实例"""

    def __init__(
        self,
        model_entity: persistence_model.EmbeddingModel,
        token_mgr: token.TokenManager,
        requester: ProviderAPIRequester,
    ):
        self.model_entity = model_entity
        self.token_mgr = token_mgr
        self.requester = requester


class ProviderAPIRequester(metaclass=abc.ABCMeta):
    """Provider API请求器"""

    name: str = None

    ap: app.Application

    default_config: dict[str, typing.Any] = {}

    requester_cfg: dict[str, typing.Any] = {}

    def __init__(self, ap: app.Application, config: dict[str, typing.Any]):
        self.ap = ap
        self.requester_cfg = {**self.default_config}
        self.requester_cfg.update(config)

    async def initialize(self):
        pass

    @abc.abstractmethod
    async def invoke_llm(
        self,
        query: pipeline_query.Query,
        model: RuntimeLLMModel,
        messages: typing.List[provider_message.Message],
        funcs: typing.List[resource_tool.LLMTool] = None,
        extra_args: dict[str, typing.Any] = {},
        remove_think: bool = False,
    ) -> provider_message.Message:
        """调用API

        Args:
            model (RuntimeLLMModel): 使用的模型信息
            messages (typing.List[llm_entities.Message]): 消息对象列表
            funcs (typing.List[tools_entities.LLMFunction], optional): 使用的工具函数列表. Defaults to None.
            extra_args (dict[str, typing.Any], optional): 额外的参数. Defaults to {}.
            remove_think (bool, optional): 是否移思考中的消息. Defaults to False.

        Returns:
            llm_entities.Message: 返回消息对象
        """
        pass

    async def invoke_llm_stream(
        self,
        query: pipeline_query.Query,
        model: RuntimeLLMModel,
        messages: typing.List[provider_message.Message],
        funcs: typing.List[resource_tool.LLMTool] = None,
        extra_args: dict[str, typing.Any] = {},
        remove_think: bool = False,
    ) -> provider_message.MessageChunk:
        """调用API

        Args:
            model (RuntimeLLMModel): 使用的模型信息
            messages (typing.List[provider_message.Message]): 消息对象列表
            funcs (typing.List[resource_tool.LLMTool], optional): 使用的工具函数列表. Defaults to None.
            extra_args (dict[str, typing.Any], optional): 额外的参数. Defaults to {}.
            remove_think (bool, optional): 是否移除思考中的消息. Defaults to False.

        Returns:
            typing.AsyncGenerator[provider_message.MessageChunk]: 返回消息对象
        """
        pass

    async def invoke_embedding(
        self,
        model: RuntimeEmbeddingModel,
        input_text: typing.List[str],
        extra_args: dict[str, typing.Any] = {},
    ) -> typing.List[typing.List[float]]:
        """调用 Embedding API

        Args:
            model (RuntimeEmbeddingModel): 使用的模型信息
            input_text (typing.List[str]): 输入文本
            extra_args (dict[str, typing.Any], optional): 额外的参数. Defaults to {}.

        Returns:
            typing.List[typing.List[float]]: 返回的 embedding 向量
        """
        pass
