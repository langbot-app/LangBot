from __future__ import annotations

import abc
import typing

from ...core import app
from ...core import entities as core_entities
from .. import entities as llm_entities
from ..tools import entities as tools_entities
from ...entity.persistence import model as persistence_model
from . import token


class RuntimeLLMModel:
    """运行时模型"""

    model_entity: persistence_model.LLMModel
    """模型数据"""

    token_mgr: token.TokenManager
    """api key管理器"""

    requester: LLMAPIRequester
    """请求器实例"""

    def __init__(
        self,
        model_entity: persistence_model.LLMModel,
        token_mgr: token.TokenManager,
        requester: LLMAPIRequester,
    ):
        self.model_entity = model_entity
        self.token_mgr = token_mgr
        self.requester = requester


class LLMAPIRequester(metaclass=abc.ABCMeta):
    """LLM API请求器"""

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
        query: core_entities.Query,
        model: RuntimeLLMModel,
        messages: typing.List[llm_entities.Message],
        funcs: typing.List[tools_entities.LLMFunction] = None,
        extra_args: dict[str, typing.Any] = {},
    ) -> llm_entities.Message:
        """调用API

        Args:
            model (RuntimeLLMModel): 使用的模型信息
            messages (typing.List[llm_entities.Message]): 消息对象列表
            funcs (typing.List[tools_entities.LLMFunction], optional): 使用的工具函数列表. Defaults to None.
            extra_args (dict[str, typing.Any], optional): 额外的参数. Defaults to {}.

        Returns:
            llm_entities.Message: 返回消息对象
        """
        pass
