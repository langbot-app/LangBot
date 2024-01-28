from __future__ import annotations
import abc

import mirai

from ...core import app
from . import entities


class GroupRespondRule(metaclass=abc.ABCMeta):
    """群组响应规则的抽象类
    """

    ap: app.Application

    def __init__(self, ap: app.Application):
        self.ap = ap

    async def initialize(self):
        pass

    @abc.abstractmethod
    async def match(
        self,
        message_text: str,
        message_chain: mirai.MessageChain,
        rule_dict: dict
    ) -> entities.RuleJudgeResult:
        """判断消息是否匹配规则
        """
        raise NotImplementedError
