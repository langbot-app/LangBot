from __future__ import annotations

import asyncio

from .. import stage, app
from ...utils import version, proxy
from ...pipeline import pool, controller, pipelinemgr
from ...plugin import connector as plugin_connector
from ...command import cmdmgr
from ...provider.session import sessionmgr as llm_session_mgr
from ...provider.modelmgr import modelmgr as llm_model_mgr
from ...provider.tools import toolmgr as llm_tool_mgr
from ...rag.knowledge import kbmgr as rag_mgr
from ...platform import botmgr as im_mgr
from ...platform.webhook_pusher import WebhookPusher
from ...persistence import mgr as persistencemgr
from ...api.http.controller import main as http_controller
from ...api.http.service import user as user_service
from ...api.http.service import model as model_service
from ...api.http.service import pipeline as pipeline_service
from ...api.http.service import bot as bot_service
from ...api.http.service import knowledge as knowledge_service
from ...api.http.service import mcp as mcp_service
from ...api.http.service import apikey as apikey_service
from ...api.http.service import webhook as webhook_service
from ...discover import engine as discover_engine
from ...storage import mgr as storagemgr
from ...utils import logcache
from ...vector import mgr as vectordb_mgr
from .. import taskmgr


@stage.stage_class('BuildAppStage')
class BuildAppStage(stage.BootingStage):
    """Build LangBot application"""

    async def run(self, ap: app.Application):
        """Build LangBot application"""
        ap.task_mgr = taskmgr.AsyncTaskManager(ap)

        discover = discover_engine.ComponentDiscoveryEngine(ap)
        discover.discover_blueprint('templates/components.yaml')
        ap.discover = discover

        proxy_mgr = proxy.ProxyManager(ap)
        await proxy_mgr.initialize()
        ap.proxy_mgr = proxy_mgr

        ver_mgr = version.VersionManager(ap)
        await ver_mgr.initialize()
        ap.ver_mgr = ver_mgr

        ap.query_pool = pool.QueryPool()

        log_cache = logcache.LogCache()
        ap.log_cache = log_cache

        storage_mgr_inst = storagemgr.StorageMgr(ap)
        await storage_mgr_inst.initialize()
        ap.storage_mgr = storage_mgr_inst

        persistence_mgr_inst = persistencemgr.PersistenceManager(ap)
        ap.persistence_mgr = persistence_mgr_inst
        await persistence_mgr_inst.initialize()

        async def runtime_disconnect_callback(connector: plugin_connector.PluginRuntimeConnector) -> None:
            await asyncio.sleep(3)
            await plugin_connector_inst.initialize()

        plugin_connector_inst = plugin_connector.PluginRuntimeConnector(ap, runtime_disconnect_callback)
        await plugin_connector_inst.initialize()
        ap.plugin_connector = plugin_connector_inst

        cmd_mgr_inst = cmdmgr.CommandManager(ap)
        await cmd_mgr_inst.initialize()
        ap.cmd_mgr = cmd_mgr_inst

        llm_model_mgr_inst = llm_model_mgr.ModelManager(ap)
        await llm_model_mgr_inst.initialize()
        ap.model_mgr = llm_model_mgr_inst

        llm_session_mgr_inst = llm_session_mgr.SessionManager(ap)
        await llm_session_mgr_inst.initialize()
        ap.sess_mgr = llm_session_mgr_inst

        llm_tool_mgr_inst = llm_tool_mgr.ToolManager(ap)
        await llm_tool_mgr_inst.initialize()
        ap.tool_mgr = llm_tool_mgr_inst

        im_mgr_inst = im_mgr.PlatformManager(ap=ap)
        await im_mgr_inst.initialize()
        ap.platform_mgr = im_mgr_inst

        # Initialize webhook pusher
        webhook_pusher_inst = WebhookPusher(ap)
        ap.webhook_pusher = webhook_pusher_inst

        pipeline_mgr = pipelinemgr.PipelineManager(ap)
        await pipeline_mgr.initialize()
        ap.pipeline_mgr = pipeline_mgr

        rag_mgr_inst = rag_mgr.RAGManager(ap)
        await rag_mgr_inst.initialize()
        ap.rag_mgr = rag_mgr_inst

        # 初始化向量数据库管理器
        vectordb_mgr_inst = vectordb_mgr.VectorDBManager(ap)
        await vectordb_mgr_inst.initialize()
        ap.vector_db_mgr = vectordb_mgr_inst

        http_ctrl = http_controller.HTTPController(ap)
        await http_ctrl.initialize()
        ap.http_ctrl = http_ctrl

        user_service_inst = user_service.UserService(ap)
        ap.user_service = user_service_inst

        llm_model_service_inst = model_service.LLMModelsService(ap)
        ap.llm_model_service = llm_model_service_inst

        embedding_models_service_inst = model_service.EmbeddingModelsService(ap)
        ap.embedding_models_service = embedding_models_service_inst

        pipeline_service_inst = pipeline_service.PipelineService(ap)
        ap.pipeline_service = pipeline_service_inst

        bot_service_inst = bot_service.BotService(ap)
        ap.bot_service = bot_service_inst

        knowledge_service_inst = knowledge_service.KnowledgeService(ap)
        ap.knowledge_service = knowledge_service_inst

        mcp_service_inst = mcp_service.MCPService(ap)
        ap.mcp_service = mcp_service_inst

        apikey_service_inst = apikey_service.ApiKeyService(ap)
        ap.apikey_service = apikey_service_inst

        webhook_service_inst = webhook_service.WebhookService(ap)
        ap.webhook_service = webhook_service_inst

        ctrl = controller.Controller(ap)
        ap.ctrl = ctrl
