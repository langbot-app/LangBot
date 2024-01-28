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
