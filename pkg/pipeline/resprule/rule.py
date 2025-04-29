from __future__ import annotations
import abc
import typing

from ...core import app, entities as core_entities
from . import entities

from ...platform.types import message as platform_message


preregisetered_rules: list[typing.Type[GroupRespondRule]] = []


def rule_class(name: str):
    def decorator(cls: typing.Type[GroupRespondRule]) -> typing.Type[GroupRespondRule]:
        cls.name = name
        preregisetered_rules.append(cls)
        return cls

    return decorator


class GroupRespondRule(metaclass=abc.ABCMeta):
    """群组响应规则的抽象类"""

    name: str

    ap: app.Application

    def __init__(self, ap: app.Application):
        self.ap = ap

    async def initialize(self):
        pass

    @abc.abstractmethod
    async def match(
        self,
        message_text: str,
        message_chain: platform_message.MessageChain,
        rule_dict: dict,
        query: core_entities.Query,
    ) -> entities.RuleJudgeResult:
        """判断消息是否匹配规则"""
        raise NotImplementedError
