from __future__ import annotations

import logging
import asyncio
import traceback
import sys
import os

from ..platform import botmgr as im_mgr
from ..provider.session import sessionmgr as llm_session_mgr
from ..provider.modelmgr import modelmgr as llm_model_mgr
from ..provider.tools import toolmgr as llm_tool_mgr
from ..config import manager as config_mgr
from ..command import cmdmgr
from ..plugin import manager as plugin_mgr
from ..pipeline import pool
from ..pipeline import controller, pipelinemgr
from ..utils import version as version_mgr, proxy as proxy_mgr, announce as announce_mgr
from ..persistence import mgr as persistencemgr
from ..api.http.controller import main as http_controller
from ..api.http.service import user as user_service
from ..api.http.service import model as model_service
from ..api.http.service import pipeline as pipeline_service
from ..api.http.service import bot as bot_service
from ..api.http.service import knowledge as knowledge_service
from ..discover import engine as discover_engine
from ..storage import mgr as storagemgr
from ..utils import logcache
from . import taskmgr
from . import entities as core_entities
from ..rag.knowledge import kbmgr as rag_mgr
from ..vector import mgr as vectordb_mgr


class Application:
    """Runtime application object and context"""

    event_loop: asyncio.AbstractEventLoop = None

    # asyncio_tasks: list[asyncio.Task] = []
    task_mgr: taskmgr.AsyncTaskManager = None

    discover: discover_engine.ComponentDiscoveryEngine = None

    platform_mgr: im_mgr.PlatformManager = None

    cmd_mgr: cmdmgr.CommandManager = None

    sess_mgr: llm_session_mgr.SessionManager = None

    model_mgr: llm_model_mgr.ModelManager = None

    rag_mgr: rag_mgr.RAGManager = None

    # TODO move to pipeline
    tool_mgr: llm_tool_mgr.ToolManager = None

    # ======= Config manager =======

    command_cfg: config_mgr.ConfigManager = None  # deprecated

    pipeline_cfg: config_mgr.ConfigManager = None  # deprecated

    platform_cfg: config_mgr.ConfigManager = None  # deprecated

    provider_cfg: config_mgr.ConfigManager = None  # deprecated

    system_cfg: config_mgr.ConfigManager = None  # deprecated

    instance_config: config_mgr.ConfigManager = None

    # ======= Metadata config manager =======

    sensitive_meta: config_mgr.ConfigManager = None

    pipeline_config_meta_trigger: config_mgr.ConfigManager = None
    pipeline_config_meta_safety: config_mgr.ConfigManager = None
    pipeline_config_meta_ai: config_mgr.ConfigManager = None
    pipeline_config_meta_output: config_mgr.ConfigManager = None

    # =========================

    plugin_mgr: plugin_mgr.PluginManager = None

    query_pool: pool.QueryPool = None

    ctrl: controller.Controller = None

    pipeline_mgr: pipelinemgr.PipelineManager = None

    ver_mgr: version_mgr.VersionManager = None

    ann_mgr: announce_mgr.AnnouncementManager = None

    proxy_mgr: proxy_mgr.ProxyManager = None

    logger: logging.Logger = None

    persistence_mgr: persistencemgr.PersistenceManager = None

    vector_db_mgr: vectordb_mgr.VectorDBManager = None

    http_ctrl: http_controller.HTTPController = None

    log_cache: logcache.LogCache = None

    storage_mgr: storagemgr.StorageMgr = None

    # ========= HTTP Services =========

    user_service: user_service.UserService = None

    llm_model_service: model_service.LLMModelsService = None

    embedding_models_service: model_service.EmbeddingModelsService = None

    pipeline_service: pipeline_service.PipelineService = None

    bot_service: bot_service.BotService = None

    knowledge_service: knowledge_service.KnowledgeService = None

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

            self.task_mgr.create_task(
                self.platform_mgr.run(),
                name='platform-manager',
                scopes=[
                    core_entities.LifecycleControlScope.APPLICATION,
                    core_entities.LifecycleControlScope.PLATFORM,
                ],
            )
            self.task_mgr.create_task(
                self.ctrl.run(),
                name='query-controller',
                scopes=[core_entities.LifecycleControlScope.APPLICATION],
            )
            self.task_mgr.create_task(
                self.http_ctrl.run(),
                name='http-api-controller',
                scopes=[core_entities.LifecycleControlScope.APPLICATION],
            )

            self.task_mgr.create_task(
                never_ending(),
                name='never-ending-task',
                scopes=[core_entities.LifecycleControlScope.APPLICATION],
            )

            await self.print_web_access_info()
            await self.task_mgr.wait_all()
        except asyncio.CancelledError:
            pass
        except Exception as e:
            self.logger.error(f'Application runtime fatal exception: {e}')
            self.logger.debug(f'Traceback: {traceback.format_exc()}')

    async def print_web_access_info(self):
        """Print access webui tips"""

        if not os.path.exists(os.path.join('.', 'web/out')):
            self.logger.warning('WebUI 文件缺失，请根据文档部署：https://docs.langbot.app/zh')
            self.logger.warning(
                'WebUI files are missing, please deploy according to the documentation: https://docs.langbot.app/en'
            )
            return

        host_ip = '127.0.0.1'

        port = self.instance_config.data['api']['port']

        tips = f"""
=======================================
✨ Access WebUI / 访问管理面板

🏠 Local Address: http://{host_ip}:{port}/
🌐 Public Address: http://<Your Public IP>:{port}/

📌 Running this program in a container? Please ensure that the {port} port is exposed
=======================================
""".strip()
        for line in tips.split('\n'):
            self.logger.info(line)

    async def reload(
        self,
        scope: core_entities.LifecycleControlScope,
    ):
        match scope:
            case core_entities.LifecycleControlScope.PLATFORM.value:
                self.logger.info('Hot reload scope=' + scope)
                await self.platform_mgr.shutdown()

                self.platform_mgr = im_mgr.PlatformManager(self)

                await self.platform_mgr.initialize()

                self.task_mgr.create_task(
                    self.platform_mgr.run(),
                    name='platform-manager',
                    scopes=[
                        core_entities.LifecycleControlScope.APPLICATION,
                        core_entities.LifecycleControlScope.PLATFORM,
                    ],
                )
            case core_entities.LifecycleControlScope.PLUGIN.value:
                self.logger.info('Hot reload scope=' + scope)
                await self.plugin_mgr.destroy_plugins()

                # 删除 sys.module 中所有的 plugins/* 下的模块
                for mod in list(sys.modules.keys()):
                    if mod.startswith('plugins.'):
                        del sys.modules[mod]

                self.plugin_mgr = plugin_mgr.PluginManager(self)
                await self.plugin_mgr.initialize()

                await self.plugin_mgr.initialize_plugins()

                await self.plugin_mgr.load_plugins()
                await self.plugin_mgr.initialize_plugins()
            case core_entities.LifecycleControlScope.PROVIDER.value:
                self.logger.info('Hot reload scope=' + scope)

                await self.tool_mgr.shutdown()

                llm_model_mgr_inst = llm_model_mgr.ModelManager(self)
                await llm_model_mgr_inst.initialize()
                self.model_mgr = llm_model_mgr_inst

                llm_session_mgr_inst = llm_session_mgr.SessionManager(self)
                await llm_session_mgr_inst.initialize()
                self.sess_mgr = llm_session_mgr_inst

                llm_tool_mgr_inst = llm_tool_mgr.ToolManager(self)
                await llm_tool_mgr_inst.initialize()
                self.tool_mgr = llm_tool_mgr_inst
            case _:
                pass
