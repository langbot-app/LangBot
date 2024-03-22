from __future__ import annotations

import abc
import typing

from ...core import app
from ...core import entities as core_entities
from .. import entities as llm_entities


preregistered_requesters: list[typing.Type[LLMAPIRequester]] = []

def requester_class(name: str):

    def decorator(cls: typing.Type[LLMAPIRequester]) -> typing.Type[LLMAPIRequester]:
        cls.name = name
        preregistered_requesters.append(cls)
        return cls

    return decorator


class LLMAPIRequester(metaclass=abc.ABCMeta):
    """LLM API请求器
    """
    name: str = None

    ap: app.Application

    def __init__(self, ap: app.Application):
        self.ap = ap

    async def initialize(self):
        pass

    @abc.abstractmethod
    async def request(
        self,
        query: core_entities.Query,
    ) -> typing.AsyncGenerator[llm_entities.Message, None]:
        """请求API

        对话前文可以从 query 对象中获取。
        可以多次yield消息对象。

        Args:
            query (core_entities.Query): 本次请求的上下文对象

        Yields:
            pkg.provider.entities.Message: 返回消息对象
        """
        raise NotImplementedError
