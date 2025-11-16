from __future__ import annotations

import logging

from .. import stage, app
from ..bootutils import log


class PersistenceHandler(logging.Handler, object):
    """
    Save logs to database
    """

    ap: app.Application

    def __init__(self, name, ap: app.Application):
        logging.Handler.__init__(self)
        self.ap = ap

    def emit(self, record):
        """
        emit function is a required function for custom handler classes, here you can process the log messages as needed, such as sending logs to the server

        Emit a record
        """
        try:
            msg = self.format(record)
            if self.ap.log_cache is not None:
                self.ap.log_cache.add_log(msg)

        except Exception:
            self.handleError(record)


@stage.stage_class('SetupLoggerStage')
class SetupLoggerStage(stage.BootingStage):
    """Setup logger stage"""

    async def run(self, ap: app.Application):
        """Setup logger"""
        persistence_handler = PersistenceHandler('LoggerHandler', ap)

        extra_handlers = []
        extra_handlers = [persistence_handler]

        ap.logger = await log.init_logging(extra_handlers)
