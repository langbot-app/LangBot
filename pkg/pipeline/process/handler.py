from __future__ import annotations

import abc

from ...core import app
from ...core import entities as core_entities
from .. import entities


class MessageHandler(metaclass=abc.ABCMeta):
    ap: app.Application

    def __init__(self, ap: app.Application):
        self.ap = ap

    async def initialize(self):
        pass

    @abc.abstractmethod
    async def handle(
        self,
        query: core_entities.Query,
    ) -> entities.StageProcessResult:
        raise NotImplementedError

    def cut_str(self, s: str) -> str:
        """
        取字符串第一行，最多20个字符，若有多行，或超过20个字符，则加省略号
        """
        s0 = s.split('\n')[0]
        if len(s0) > 20 or '\n' in s:
            s0 = s0[:20] + '...'
        return s0
