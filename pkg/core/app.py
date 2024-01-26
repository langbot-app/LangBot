from __future__ import annotations

import logging
import asyncio

from ..qqbot import manager as qqbot_mgr
from ..openai import manager as openai_mgr
from ..config import manager as config_mgr
from ..database import manager as database_mgr
from ..utils.center import v2 as center_mgr
from ..plugin import host as plugin_host
from . import pool, controller
from ..pipeline import stagemgr


class Application:
    im_mgr: qqbot_mgr.QQBotManager = None

    llm_mgr: openai_mgr.OpenAIInteract = None

    cfg_mgr: config_mgr.ConfigManager = None

    tips_mgr: config_mgr.ConfigManager = None

    db_mgr: database_mgr.DatabaseManager = None

    ctr_mgr: center_mgr.V2CenterAPI = None

    query_pool: pool.QueryPool = None

    ctrl: controller.Controller = None

    stage_mgr: stagemgr.StageManager = None

    logger: logging.Logger = None

    def __init__(self):
        pass

    async def run(self):
        # TODO make it async
        plugin_host.initialize_plugins()

        tasks = [
            asyncio.create_task(self.im_mgr.run()),
            asyncio.create_task(self.ctrl.run())
        ]

        await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
