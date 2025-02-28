from __future__ import annotations

import abc
import typing

from ...core import app
from ...core import entities as core_entities
from .. import entities as llm_entities
from . import entities as modelmgr_entities
from ..tools import entities as tools_entities


class LLMAPIRequester(metaclass=abc.ABCMeta):
    """LLM API请求器
    """
    name: str = None

    ap: app.Application

    def __init__(self, ap: app.Application):
        self.ap = ap

    async def initialize(self):
        pass

    async def preprocess(
        self,
        query: core_entities.Query,
    ):
        """预处理
        
        在这里处理特定API对Query对象的兼容性问题。
        """
        pass

    @abc.abstractmethod
    async def call(
        self,
        query: core_entities.Query,
        model: modelmgr_entities.LLMModelInfo,
        messages: typing.List[llm_entities.Message],
        funcs: typing.List[tools_entities.LLMFunction] = None,
    ) -> llm_entities.Message:
        """调用API

        Args:
            model (modelmgr_entities.LLMModelInfo): 使用的模型信息
            messages (typing.List[llm_entities.Message]): 消息对象列表
            funcs (typing.List[tools_entities.LLMFunction], optional): 使用的工具函数列表. Defaults to None.

        Returns:
            llm_entities.Message: 返回消息对象
        """
        pass
