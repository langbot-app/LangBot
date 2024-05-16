from __future__ import annotations

import logging
import asyncio
import traceback

from ..platform import manager as im_mgr
from ..provider.session import sessionmgr as llm_session_mgr
from ..provider.modelmgr import modelmgr as llm_model_mgr
from ..provider.sysprompt import sysprompt as llm_prompt_mgr
from ..provider.tools import toolmgr as llm_tool_mgr
from ..config import manager as config_mgr
from ..audit.center import v2 as center_mgr
from ..command import cmdmgr
from ..plugin import manager as plugin_mgr
from ..pipeline import pool
from ..pipeline import controller, stagemgr
from ..utils import version as version_mgr, proxy as proxy_mgr


class Application:
    """运行时应用对象和上下文"""

    platform_mgr: im_mgr.PlatformManager = None

    cmd_mgr: cmdmgr.CommandManager = None

    sess_mgr: llm_session_mgr.SessionManager = None

    model_mgr: llm_model_mgr.ModelManager = None

    prompt_mgr: llm_prompt_mgr.PromptManager = None

    tool_mgr: llm_tool_mgr.ToolManager = None

    # ======= 配置管理器 =======

    command_cfg: config_mgr.ConfigManager = None

    pipeline_cfg: config_mgr.ConfigManager = None

    platform_cfg: config_mgr.ConfigManager = None

    provider_cfg: config_mgr.ConfigManager = None

    system_cfg: config_mgr.ConfigManager = None

    # ======= 元数据配置管理器 =======

    sensitive_meta: config_mgr.ConfigManager = None

    adapter_qq_botpy_meta: config_mgr.ConfigManager = None

    plugin_setting_meta: config_mgr.ConfigManager = None

    llm_models_meta: config_mgr.ConfigManager = None

    # =========================

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
        await self.plugin_mgr.initialize_plugins()

        tasks = []

        try:
   
            tasks = [
                asyncio.create_task(self.platform_mgr.run()),
                asyncio.create_task(self.ctrl.run())
            ]

            # 挂信号处理

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

