from __future__ import annotations

import logging
import asyncio
import traceback

from ..platform import manager as im_mgr
from ..provider.session import sessionmgr as llm_session_mgr
from ..provider.requester import modelmgr as llm_model_mgr
from ..provider.sysprompt import sysprompt as llm_prompt_mgr
from ..provider.tools import toolmgr as llm_tool_mgr
from ..config import manager as config_mgr
from ..audit.center import v2 as center_mgr
from ..command import cmdmgr
from ..plugin import manager as plugin_mgr
from . import pool, controller
from ..pipeline import stagemgr
from ..utils import version as version_mgr, proxy as proxy_mgr


class Application:
    im_mgr: im_mgr.PlatformManager = None

    cmd_mgr: cmdmgr.CommandManager = None

    sess_mgr: llm_session_mgr.SessionManager = None

    model_mgr: llm_model_mgr.ModelManager = None

    prompt_mgr: llm_prompt_mgr.PromptManager = None

    tool_mgr: llm_tool_mgr.ToolManager = None

    command_cfg: config_mgr.ConfigManager = None

    pipeline_cfg: config_mgr.ConfigManager = None

    platform_cfg: config_mgr.ConfigManager = None

    provider_cfg: config_mgr.ConfigManager = None

    system_cfg: config_mgr.ConfigManager = None

    ctr_mgr: center_mgr.V2CenterAPI = None

    plugin_mgr: plugin_mgr.PluginManager = None

    query_pool: pool.QueryPool = None

    ctrl: controller.Controller = None

    stage_mgr: stagemgr.StageManager = None

    ver_mgr: version_mgr.VersionManager = None

    proxy_mgr: proxy_mgr.ProxyManager = None

    logger: logging.Logger = None

    def __init__(self):
        pass

    async def initialize(self):
        pass

    async def run(self):
        await self.plugin_mgr.load_plugins()
        await self.plugin_mgr.initialize_plugins()

        tasks = []

        try:

                    
            tasks = [
                asyncio.create_task(self.im_mgr.run()),
                asyncio.create_task(self.ctrl.run())
            ]

            # async def interrupt(tasks):
            #     await asyncio.sleep(1.5)
            #     while await aioconsole.ainput("使用 ctrl+c 或 'exit' 退出程序 > ") != 'exit':
            #         pass
            #     for task in tasks:
            #         task.cancel()
            
            # await interrupt(tasks)

            import signal

            def signal_handler(sig, frame):
                for task in tasks:
                    task.cancel()
                self.logger.info("程序退出.")
                exit(0)

            signal.signal(signal.SIGINT, signal_handler)

            await asyncio.gather(*tasks, return_exceptions=True)

        except asyncio.CancelledError:
            pass
        except Exception as e:
            self.logger.error(f"应用运行致命异常: {e}")
            self.logger.debug(f"Traceback: {traceback.format_exc()}")

