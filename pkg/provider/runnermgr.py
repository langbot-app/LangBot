from __future__ import annotations

from . import runner
from ..core import app

from .runners import localagent
from .runners import difysvapi
from .runners import dashscopeapi

class RunnerManager:

    ap: app.Application

    using_runner: runner.RequestRunner

    def __init__(self, ap: app.Application):
        self.ap = ap

    async def initialize(self):

        for r in runner.preregistered_runners:
            if r.name == self.ap.provider_cfg.data['runner']:
                self.using_runner = r(self.ap)
                await self.using_runner.initialize()
                break
        else:
            raise ValueError(f"未找到请求运行器: {self.ap.provider_cfg.data['runner']}")

    def get_runner(self) -> runner.RequestRunner:
        return self.using_runner
