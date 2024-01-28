from __future__ import annotations

from . import algo
from .algos import fixedwin
from ...core import app


class RateLimiter:
    """限速器
    """

    ap: app.Application

    algo: algo.ReteLimitAlgo

    def __init__(self, ap: app.Application):
        self.ap = ap

    async def initialize(self):
        self.algo = fixedwin.FixedWindowAlgo(self.ap)
        await self.algo.initialize()

    async def require(self, launcher_type: str, launcher_id: int) -> bool:
        """请求访问
        """
        return await self.algo.require_access(launcher_type, launcher_id)

    async def release(self, launcher_type: str, launcher_id: int):
        """释放访问
        """
        return await self.algo.release_access(launcher_type, launcher_id)