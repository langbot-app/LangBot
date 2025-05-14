from __future__ import annotations

import logging

from .. import stage, app
from ..bootutils import log


class PersistenceHandler(logging.Handler, object):
    """
    保存日志到数据库
    """

    ap: app.Application

    def __init__(self, name, ap: app.Application):
        logging.Handler.__init__(self)
        self.ap = ap

    def emit(self, record):
        """
        emit函数为自定义handler类时必重写的函数，这里可以根据需要对日志消息做一些处理，比如发送日志到服务器

        发出记录(Emit a record)
        """
        try:
            msg = self.format(record)
            if self.ap.log_cache is not None:
                self.ap.log_cache.add_log(msg)

        except Exception:
            self.handleError(record)


@stage.stage_class('SetupLoggerStage')
class SetupLoggerStage(stage.BootingStage):
    """设置日志器阶段"""

    async def run(self, ap: app.Application):
        """启动"""
        persistence_handler = PersistenceHandler('LoggerHandler', ap)

        extra_handlers = []
        extra_handlers = [persistence_handler]

        ap.logger = await log.init_logging(extra_handlers)
