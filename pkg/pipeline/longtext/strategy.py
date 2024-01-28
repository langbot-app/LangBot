from __future__ import annotations
import abc
import typing

import mirai
from mirai.models.message import MessageComponent

from ...core import app


class LongTextStrategy(metaclass=abc.ABCMeta):
    ap: app.Application

    def __init__(self, ap: app.Application):
        self.ap = ap
    
    async def initialize(self):
        pass
    
    @abc.abstractmethod
    async def process(self, message: str) -> list[MessageComponent]:
        return []
