from __future__ import annotations

import logging
import asyncio

from ..im import manager as qqbot_mgr
from ..gai.session import sessionmgr as llm_session_mgr
from ..gai.requester import modelmgr as llm_model_mgr
from ..gai.sysprompt import sysprompt as llm_prompt_mgr
from ..gai.tools import toolmgr as llm_tool_mgr
from ..config import manager as config_mgr
from ..database import manager as database_mgr
from ..utils.center import v2 as center_mgr
from ..command import cmdmgr
from ..plugin import host as plugin_host
from . import pool, controller
from ..pipeline import stagemgr


class Application:
    im_mgr: qqbot_mgr.QQBotManager = None

    cmd_mgr: cmdmgr.CommandManager = None

    sess_mgr: llm_session_mgr.SessionManager = None

    model_mgr: llm_model_mgr.ModelManager = None

    prompt_mgr: llm_prompt_mgr.PromptManager = None

    tool_mgr: llm_tool_mgr.ToolManager = None

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

    async def initialize(self):
        plugin_host.initialize_plugins()

        # 把现有的所有内容函数加到toolmgr里
        for func in plugin_host.__callable_functions__:
            self.tool_mgr.register_legacy_function(
                name=func['name'],
                description=func['description'],
                parameters=func['parameters'],
                func=plugin_host.__function_inst_map__[func['name']]
            )

    async def run(self):

        tasks = [
            asyncio.create_task(self.im_mgr.run()),
            asyncio.create_task(self.ctrl.run())
        ]

        await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
