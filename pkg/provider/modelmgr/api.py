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
        """请求
        """
        raise NotImplementedError
