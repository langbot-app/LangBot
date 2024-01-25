from __future__ import annotations
import abc

from ...boot import app


class ReteLimitAlgo(metaclass=abc.ABCMeta):
    
    ap: app.Application

    def __init__(self, ap: app.Application):
        self.ap = ap

    async def initialize(self):
        pass

    @abc.abstractmethod
    async def require_access(self, launcher_type: str, launcher_id: int) -> bool:
        raise NotImplementedError
    
    @abc.abstractmethod
    async def release_access(self, launcher_type: str, launcher_id: int):
        raise NotImplementedError
 