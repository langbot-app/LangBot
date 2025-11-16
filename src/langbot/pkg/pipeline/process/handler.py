from __future__ import annotations

import abc

from ...core import app
from .. import entities
import langbot_plugin.api.entities.builtin.pipeline.query as pipeline_query


class MessageHandler(metaclass=abc.ABCMeta):
    ap: app.Application

    def __init__(self, ap: app.Application):
        self.ap = ap

    async def initialize(self):
        pass

    @abc.abstractmethod
    async def handle(
        self,
        query: pipeline_query.Query,
    ) -> entities.StageProcessResult:
        raise NotImplementedError

    def cut_str(self, s: str) -> str:
        """
        Take the first line of the string, up to 20 characters, if there are multiple lines, or more than 20 characters, add an ellipsis
        """
        s0 = s.split('\n')[0]
        if len(s0) > 20 or '\n' in s:
            s0 = s0[:20] + '...'
        return s0
