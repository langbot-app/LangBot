from __future__ import annotations

import abc
import typing

from ...core import app
from .. import entities as llm_entities
from . import entities


class LLMTokenizer(metaclass=abc.ABCMeta):
    """LLM分词器抽象类"""

    ap: app.Application

    def __init__(self, ap: app.Application):
        self.ap = ap

    async def initialize(self):
        """初始化分词器
        """
        pass

    @abc.abstractmethod
    async def count_token(
        self,
        messages: list[llm_entities.Message],
        model: entities.LLMModelInfo
    ) -> int:
        pass
