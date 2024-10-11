from __future__ import annotations

import traceback

import quart

from .....core import app
from .. import group


@group.group_class('log', '/api/v1/log')
class LogRouterGroup(group.RouterGroup):
    
    async def initialize(self) -> None:
        @self.route('', methods=['GET'])
        async def _() -> str:
            return self.success(
                data={
                    "logs": self.ap.log_cache.get_all_logs()
                }
            )
