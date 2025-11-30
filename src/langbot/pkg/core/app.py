from __future__ import annotations

import logging
import asyncio
import traceback
import os

from ..platform import botmgr as im_mgr
from ..platform.webhook_pusher import WebhookPusher
from ..provider.session import sessionmgr as llm_session_mgr
from ..provider.modelmgr import modelmgr as llm_model_mgr
from langbot.pkg.provider.tools import toolmgr as llm_tool_mgr
from ..config import manager as config_mgr
from ..command import cmdmgr
from ..plugin import connector as plugin_connector
from ..pipeline import pool
from ..pipeline import controller, pipelinemgr
from ..utils import version as version_mgr, proxy as proxy_mgr
from ..persistence import mgr as persistencemgr
from ..api.http.controller import main as http_controller
from ..api.http.service import user as user_service
from ..api.http.service import model as model_service
from ..api.http.service import pipeline as pipeline_service
from ..api.http.service import bot as bot_service
from ..api.http.service import knowledge as knowledge_service
from ..api.http.service import mcp as mcp_service
from ..api.http.service import apikey as apikey_service
from ..api.http.service import webhook as webhook_service
from ..api.http.service import external_kb as external_kb_service
from ..discover import engine as discover_engine
from ..storage import mgr as storagemgr
from ..utils import logcache
from . import taskmgr
from . import entities as core_entities
from ..rag.knowledge import kbmgr as rag_mgr
from ..vector import mgr as vectordb_mgr


class Application:
    """Runtime application object and context"""

    event_loop: asyncio.AbstractEventLoop | None = None

    # asyncio_tasks: list[asyncio.Task] = []
    task_mgr: taskmgr.AsyncTaskManager | None = None

    discover: discover_engine.ComponentDiscoveryEngine | None = None

    platform_mgr: im_mgr.PlatformManager | None = None

    webhook_pusher: WebhookPusher | None = None

    cmd_mgr: cmdmgr.CommandManager | None = None

    sess_mgr: llm_session_mgr.SessionManager | None = None

    model_mgr: llm_model_mgr.ModelManager | None = None

    rag_mgr: rag_mgr.RAGManager | None = None

    # TODO move to pipeline
    tool_mgr: llm_tool_mgr.ToolManager | None = None

    # ======= Config manager =======

    command_cfg: config_mgr.ConfigManager | None = None  # deprecated

    pipeline_cfg: config_mgr.ConfigManager | None = None  # deprecated

    platform_cfg: config_mgr.ConfigManager | None = None  # deprecated

    provider_cfg: config_mgr.ConfigManager | None = None  # deprecated

    system_cfg: config_mgr.ConfigManager | None = None  # deprecated

    instance_config: config_mgr.ConfigManager | None = None

    # ======= Metadata config manager =======

    sensitive_meta: config_mgr.ConfigManager | None = None

    pipeline_config_meta_trigger: dict | None = None
    pipeline_config_meta_safety: dict | None = None
    pipeline_config_meta_ai: dict | None = None
    pipeline_config_meta_output: dict | None = None

    # =========================

    plugin_connector: plugin_connector.PluginRuntimeConnector | None = None

    query_pool: pool.QueryPool | None = None

    ctrl: controller.Controller | None = None

    pipeline_mgr: pipelinemgr.PipelineManager | None = None

    ver_mgr: version_mgr.VersionManager | None = None

    proxy_mgr: proxy_mgr.ProxyManager | None = None

    logger: logging.Logger | None = None

    persistence_mgr: persistencemgr.PersistenceManager | None = None

    vector_db_mgr: vectordb_mgr.VectorDBManager | None = None

    http_ctrl: http_controller.HTTPController | None = None

    log_cache: logcache.LogCache | None = None

    storage_mgr: storagemgr.StorageMgr | None = None

    # ========= HTTP Services =========

    user_service: user_service.UserService | None = None

    llm_model_service: model_service.LLMModelsService | None = None

    embedding_models_service: model_service.EmbeddingModelsService | None = None

    pipeline_service: pipeline_service.PipelineService | None = None

    bot_service: bot_service.BotService | None = None

    knowledge_service: knowledge_service.KnowledgeService | None = None

    external_kb_service: external_kb_service.ExternalKBService | None = None

    mcp_service: mcp_service.MCPService | None = None

    apikey_service: apikey_service.ApiKeyService | None = None

    webhook_service: webhook_service.WebhookService | None = None

    def __init__(self):
        pass

    async def initialize(self):
        pass

    async def run(self):
        try:
            await self.plugin_connector.initialize_plugins()

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

    def dispose(self):
        self.plugin_connector.dispose()

    async def print_web_access_info(self):
        """Print access webui tips"""

        from ..utils import paths

        frontend_path = paths.get_frontend_path()

        if not os.path.exists(frontend_path):
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
