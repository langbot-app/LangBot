from __future__ import annotations

from .. import stage, app
from ..bootutils import log


@stage.stage_class("SetupLoggerStage")
class SetupLoggerStage(stage.BootingStage):
    """设置日志器阶段
    """

    async def run(self, ap: app.Application):
        """启动
        """
        ap.logger = await log.init_logging()
