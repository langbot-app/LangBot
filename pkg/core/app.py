from __future__ import annotations

import logging
import asyncio
import threading
import traceback
import enum
import sys
import os

from ..platform import manager as im_mgr
from ..provider.session import sessionmgr as llm_session_mgr
from ..provider.modelmgr import modelmgr as llm_model_mgr
from ..provider.sysprompt import sysprompt as llm_prompt_mgr
from ..provider.tools import toolmgr as llm_tool_mgr
from ..provider import runnermgr
from ..config import manager as config_mgr
from ..config import settings as settings_mgr
from ..audit.center import v2 as center_mgr
from ..command import cmdmgr
from ..plugin import manager as plugin_mgr
from ..pipeline import pool
from ..pipeline import controller, stagemgr
from ..utils import version as version_mgr, proxy as proxy_mgr, announce as announce_mgr
from ..persistence import mgr as persistencemgr
from ..api.http.controller import main as http_controller
from ..api.http.service import user as user_service
from ..discover import engine as discover_engine
from ..utils import logcache, ip
from . import taskmgr
from . import entities as core_entities
from .bootutils import config


class Application:
    """运行时应用对象和上下文"""

    event_loop: asyncio.AbstractEventLoop = None

    # asyncio_tasks: list[asyncio.Task] = []
    task_mgr: taskmgr.AsyncTaskManager = None

    discover: discover_engine.ComponentDiscoveryEngine = None

    platform_mgr: im_mgr.PlatformManager = None

    cmd_mgr: cmdmgr.CommandManager = None

    sess_mgr: llm_session_mgr.SessionManager = None

    model_mgr: llm_model_mgr.ModelManager = None

    prompt_mgr: llm_prompt_mgr.PromptManager = None

    tool_mgr: llm_tool_mgr.ToolManager = None

    runner_mgr: runnermgr.RunnerManager = None

    settings_mgr: settings_mgr.SettingsManager = None

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

    instance_secret_meta: config_mgr.ConfigManager = None

    # =========================

    ctr_mgr: center_mgr.V2CenterAPI = None

    plugin_mgr: plugin_mgr.PluginManager = None

    query_pool: pool.QueryPool = None

    ctrl: controller.Controller = None

    stage_mgr: stagemgr.StageManager = None

    ver_mgr: version_mgr.VersionManager = None

    ann_mgr: announce_mgr.AnnouncementManager = None

    proxy_mgr: proxy_mgr.ProxyManager = None

    logger: logging.Logger = None

    persistence_mgr: persistencemgr.PersistenceManager = None

    http_ctrl: http_controller.HTTPController = None

    log_cache: logcache.LogCache = None

    # ========= HTTP Services =========

    user_service: user_service.UserService = None

    def __init__(self):
        pass

    async def initialize(self):
        pass

    async def run(self):
        try:
            await self.plugin_mgr.initialize_plugins()
            # 后续可能会允许动态重启其他任务
            # 故为了防止程序在非 Ctrl-C 情况下退出，这里创建一个不会结束的协程
            async def never_ending():
                while True:
                    await asyncio.sleep(1)

            self.task_mgr.create_task(self.platform_mgr.run(), name="platform-manager", scopes=[core_entities.LifecycleControlScope.APPLICATION, core_entities.LifecycleControlScope.PLATFORM])
            self.task_mgr.create_task(self.ctrl.run(), name="query-controller", scopes=[core_entities.LifecycleControlScope.APPLICATION])
            self.task_mgr.create_task(self.http_ctrl.run(), name="http-api-controller", scopes=[core_entities.LifecycleControlScope.APPLICATION])
            self.task_mgr.create_task(never_ending(), name="never-ending-task", scopes=[core_entities.LifecycleControlScope.APPLICATION])

            await self.print_web_access_info()
            await self.task_mgr.wait_all()
        except asyncio.CancelledError:
            pass
        except Exception as e:
            self.logger.error(f"应用运行致命异常: {e}")
            self.logger.debug(f"Traceback: {traceback.format_exc()}")

    async def print_web_access_info(self):
        """打印访问 webui 的提示"""

        if not os.path.exists(os.path.join(".", "web/dist")):
            self.logger.warning("WebUI 文件缺失，请根据文档获取：https://docs.langbot.app/webui/intro.html")
            return

        host_ip = "127.0.0.1"

        public_ip = await ip.get_myip()

        port = self.system_cfg.data['http-api']['port']

        tips = f"""
=======================================
✨ 您可通过以下方式访问管理面板

🏠 本地地址：http://{host_ip}:{port}/
🌐 公网地址：http://{public_ip}:{port}/

📌 如果您在容器中运行此程序，请确保容器的 {port} 端口已对外暴露
🔗 若要使用公网地址访问，请阅读以下须知
   1. 公网地址仅供参考，请以您的主机公网 IP 为准；
   2. 要使用公网地址访问，请确保您的主机具有公网 IP，并且系统防火墙已放行 {port} 端口；

🤯 WebUI 仍处于 Beta 测试阶段，如有问题或建议请反馈到 https://github.com/RockChinQ/LangBot/issues
=======================================
""".strip()
        for line in tips.split("\n"):
            self.logger.info(line)

    async def reload(
        self,
        scope: core_entities.LifecycleControlScope,
    ):
        match scope:
            case core_entities.LifecycleControlScope.PLATFORM.value:
                self.logger.info("执行热重载 scope="+scope)
                await self.platform_mgr.shutdown()

                self.platform_mgr = im_mgr.PlatformManager(self)

                await self.platform_mgr.initialize()

                self.task_mgr.create_task(self.platform_mgr.run(), name="platform-manager", scopes=[core_entities.LifecycleControlScope.APPLICATION, core_entities.LifecycleControlScope.PLATFORM])
            case core_entities.LifecycleControlScope.PLUGIN.value:
                self.logger.info("执行热重载 scope="+scope)
                await self.plugin_mgr.destroy_plugins()

                # 删除 sys.module 中所有的 plugins/* 下的模块
                for mod in list(sys.modules.keys()):
                    if mod.startswith("plugins."):
                        del sys.modules[mod]

                self.plugin_mgr = plugin_mgr.PluginManager(self)
                await self.plugin_mgr.initialize()

                await self.plugin_mgr.initialize_plugins()

                await self.plugin_mgr.load_plugins()
                await self.plugin_mgr.initialize_plugins()
            case core_entities.LifecycleControlScope.PROVIDER.value:
                self.logger.info("执行热重载 scope="+scope)

                latest_llm_model_config = await config.load_json_config("data/metadata/llm-models.json", "templates/metadata/llm-models.json")
                self.llm_models_meta = latest_llm_model_config
                llm_model_mgr_inst = llm_model_mgr.ModelManager(self)
                await llm_model_mgr_inst.initialize()
                self.model_mgr = llm_model_mgr_inst

                llm_session_mgr_inst = llm_session_mgr.SessionManager(self)
                await llm_session_mgr_inst.initialize()
                self.sess_mgr = llm_session_mgr_inst

                llm_prompt_mgr_inst = llm_prompt_mgr.PromptManager(self)
                await llm_prompt_mgr_inst.initialize()
                self.prompt_mgr = llm_prompt_mgr_inst

                llm_tool_mgr_inst = llm_tool_mgr.ToolManager(self)
                await llm_tool_mgr_inst.initialize()
                self.tool_mgr = llm_tool_mgr_inst

                runner_mgr_inst = runnermgr.RunnerManager(self)
                await runner_mgr_inst.initialize()
                self.runner_mgr = runner_mgr_inst
            case _:
                pass