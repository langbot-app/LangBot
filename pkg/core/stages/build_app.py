from __future__ import annotations


from .. import stage, app
from ...utils import version, proxy, announce
from ...pipeline import pool, controller, pipelinemgr
from ...plugin import manager as plugin_mgr
from ...command import cmdmgr
from ...provider.session import sessionmgr as llm_session_mgr
from ...provider.modelmgr import modelmgr as llm_model_mgr
from ...provider.tools import toolmgr as llm_tool_mgr
from ...platform import botmgr as im_mgr
from ...persistence import mgr as persistencemgr
from ...api.http.controller import main as http_controller
from ...api.http.service import user as user_service
from ...api.http.service import model as model_service
from ...api.http.service import pipeline as pipeline_service
from ...api.http.service import bot as bot_service
from ...discover import engine as discover_engine
from ...utils import logcache
from .. import taskmgr


@stage.stage_class('BuildAppStage')
class BuildAppStage(stage.BootingStage):
    """构建应用阶段"""

    async def run(self, ap: app.Application):
        """构建app对象的各个组件对象并初始化"""
        ap.task_mgr = taskmgr.AsyncTaskManager(ap)

        discover = discover_engine.ComponentDiscoveryEngine(ap)
        discover.discover_blueprint('components.yaml')
        ap.discover = discover

        proxy_mgr = proxy.ProxyManager(ap)
        await proxy_mgr.initialize()
        ap.proxy_mgr = proxy_mgr

        ver_mgr = version.VersionManager(ap)
        await ver_mgr.initialize()
        ap.ver_mgr = ver_mgr

        # 发送公告
        ann_mgr = announce.AnnouncementManager(ap)
        ap.ann_mgr = ann_mgr

        ap.query_pool = pool.QueryPool()

        log_cache = logcache.LogCache()
        ap.log_cache = log_cache

        persistence_mgr_inst = persistencemgr.PersistenceManager(ap)
        ap.persistence_mgr = persistence_mgr_inst
        await persistence_mgr_inst.initialize()

        plugin_mgr_inst = plugin_mgr.PluginManager(ap)
        await plugin_mgr_inst.initialize()
        ap.plugin_mgr = plugin_mgr_inst
        await plugin_mgr_inst.load_plugins()

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

        pipeline_mgr = pipelinemgr.PipelineManager(ap)
        await pipeline_mgr.initialize()
        ap.pipeline_mgr = pipeline_mgr

        http_ctrl = http_controller.HTTPController(ap)
        await http_ctrl.initialize()
        ap.http_ctrl = http_ctrl

        user_service_inst = user_service.UserService(ap)
        ap.user_service = user_service_inst

        model_service_inst = model_service.ModelsService(ap)
        ap.model_service = model_service_inst

        pipeline_service_inst = pipeline_service.PipelineService(ap)
        ap.pipeline_service = pipeline_service_inst

        bot_service_inst = bot_service.BotService(ap)
        ap.bot_service = bot_service_inst

        ctrl = controller.Controller(ap)
        ap.ctrl = ctrl
