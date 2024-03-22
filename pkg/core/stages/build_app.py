from __future__ import annotations

import sys

from .. import stage, app
from ...utils import version, proxy, announce, platform
from ...audit.center import v2 as center_v2
from ...audit import identifier
from ...pipeline import pool, controller, stagemgr
from ...plugin import manager as plugin_mgr
from ...command import cmdmgr
from ...provider.session import sessionmgr as llm_session_mgr
from ...provider.modelmgr import modelmgr as llm_model_mgr
from ...provider.sysprompt import sysprompt as llm_prompt_mgr
from ...provider.tools import toolmgr as llm_tool_mgr
from ...platform import manager as im_mgr


@stage.stage_class("BuildAppStage")
class BuildAppStage(stage.BootingStage):
    """构建应用阶段
    """

    async def run(self, ap: app.Application):
        """构建app对象的各个组件对象并初始化
        """

        proxy_mgr = proxy.ProxyManager(ap)
        await proxy_mgr.initialize()
        ap.proxy_mgr = proxy_mgr
        
        ver_mgr = version.VersionManager(ap)
        await ver_mgr.initialize()
        ap.ver_mgr = ver_mgr

        center_v2_api = center_v2.V2CenterAPI(
            ap,
            basic_info={
                "host_id": identifier.identifier["host_id"],
                "instance_id": identifier.identifier["instance_id"],
                "semantic_version": ver_mgr.get_current_version(),
                "platform": platform.get_platform(),
            },
            runtime_info={
                "admin_id": "{}".format(ap.system_cfg.data["admin-sessions"]),
                "msg_source": str([
                    adapter_cfg['adapter'] if 'adapter' in adapter_cfg else 'unknown'
                    for adapter_cfg in ap.platform_cfg.data['platform-adapters'] if adapter_cfg['enable']
                ]),
            },
        )
        ap.ctr_mgr = center_v2_api

        # 发送公告
        ann_mgr = announce.AnnouncementManager(ap)
        await ann_mgr.show_announcements()

        ap.query_pool = pool.QueryPool()

        await ap.ver_mgr.show_version_update()

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

        llm_prompt_mgr_inst = llm_prompt_mgr.PromptManager(ap)
        await llm_prompt_mgr_inst.initialize()
        ap.prompt_mgr = llm_prompt_mgr_inst

        llm_tool_mgr_inst = llm_tool_mgr.ToolManager(ap)
        await llm_tool_mgr_inst.initialize()
        ap.tool_mgr = llm_tool_mgr_inst

        im_mgr_inst = im_mgr.PlatformManager(ap=ap)
        await im_mgr_inst.initialize()
        ap.platform_mgr = im_mgr_inst

        stage_mgr = stagemgr.StageManager(ap)
        await stage_mgr.initialize()
        ap.stage_mgr = stage_mgr

        ctrl = controller.Controller(ap)
        ap.ctrl = ctrl
