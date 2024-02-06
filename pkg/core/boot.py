from __future__ import print_function

import os
import sys

from .bootutils import files
from .bootutils import deps
from .bootutils import log
from .bootutils import config

from . import app
from . import pool
from . import controller
from ..pipeline import stagemgr
from ..audit import identifier
from ..provider.session import sessionmgr as llm_session_mgr
from ..provider.requester import modelmgr as llm_model_mgr
from ..provider.sysprompt import sysprompt as llm_prompt_mgr
from ..provider.tools import toolmgr as llm_tool_mgr
from ..platform import manager as im_mgr
from ..command import cmdmgr
from ..plugin import manager as plugin_mgr
from ..audit.center import v2 as center_v2
from ..utils import version, proxy, announce

use_override = False


async def make_app() -> app.Application:
    global use_override

    generated_files = await files.generate_files()

    if generated_files:
        print("以下文件不存在，已自动生成，请按需修改配置文件后重启：")
        for file in generated_files:
            print("-", file)

        sys.exit(0)

    missing_deps = await deps.check_deps()

    if missing_deps:
        print("以下依赖包未安装，将自动安装，请完成后重启程序：")
        for dep in missing_deps:
            print("-", dep)
        await deps.install_deps(missing_deps)
        sys.exit(0)

    qcg_logger = await log.init_logging()

    # 生成标识符
    identifier.init()

    # ========== 加载配置文件 ==========

    command_cfg = await config.load_json_config("data/config/command.json", "templates/command.json")
    pipeline_cfg = await config.load_json_config("data/config/pipeline.json", "templates/pipeline.json")
    platform_cfg = await config.load_json_config("data/config/platform.json", "templates/platform.json")
    provider_cfg = await config.load_json_config("data/config/provider.json", "templates/provider.json")
    system_cfg = await config.load_json_config("data/config/system.json", "templates/system.json")

    # ========== 构建应用实例 ==========
    ap = app.Application()
    ap.logger = qcg_logger

    ap.command_cfg = command_cfg
    ap.pipeline_cfg = pipeline_cfg
    ap.platform_cfg = platform_cfg
    ap.provider_cfg = provider_cfg
    ap.system_cfg = system_cfg

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
            "platform": sys.platform,
        },
        runtime_info={
            "admin_id": "{}".format(system_cfg.data["admin-sessions"]),
            "msg_source": platform_cfg.data["platform-adapter"],
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
    ap.im_mgr = im_mgr_inst

    stage_mgr = stagemgr.StageManager(ap)
    await stage_mgr.initialize()
    ap.stage_mgr = stage_mgr

    ctrl = controller.Controller(ap)
    ap.ctrl = ctrl

    await ap.initialize()

    return ap


async def main():
    app_inst = await make_app()
    await app_inst.run()
