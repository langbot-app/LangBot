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
from ..utils import version, proxy

use_override = False


async def make_app() -> app.Application:
    global use_override

    generated_files = await files.generate_files()

    if generated_files:
        print("以下文件不存在，已自动生成，请修改配置文件后重启：")
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

    cfg_mgr = await config.load_python_module_config(
        "config.py",
        "config-template.py"
    )
    cfg = cfg_mgr.data

    # 检查是否携带了 --override 或 -r 参数
    if '--override' in sys.argv or '-r' in sys.argv:
        use_override = True

    if use_override:
        overrided = await config.override_config_manager(cfg_mgr)
        if overrided:
            qcg_logger.info("以下配置项已使用 override.json 覆盖：" + ",".join(overrided))
    
    tips_mgr = await config.load_python_module_config(
        "tips.py",
        "tips-custom-template.py"
    )

    # 检查管理员QQ号
    if cfg_mgr.data['admin_qq'] == 0:
        qcg_logger.warning("未设置管理员QQ号，将无法使用管理员命令，请在 config.py 中修改 admin_qq")

    # 构建组建实例
    ap = app.Application()
    ap.logger = qcg_logger
    ap.cfg_mgr = cfg_mgr
    ap.tips_mgr = tips_mgr

    ap.query_pool = pool.QueryPool()

    proxy_mgr = proxy.ProxyManager(ap)
    await proxy_mgr.initialize()
    ap.proxy_mgr = proxy_mgr

    ver_mgr = version.VersionManager(ap)
    await ver_mgr.initialize()
    ap.ver_mgr = ver_mgr

    plugin_mgr_inst = plugin_mgr.PluginManager(ap)
    await plugin_mgr_inst.initialize()
    ap.plugin_mgr = plugin_mgr_inst

    center_v2_api = center_v2.V2CenterAPI(
        ap,
        basic_info={
            "host_id": identifier.identifier['host_id'],
            "instance_id": identifier.identifier['instance_id'],
            "semantic_version": ver_mgr.get_current_version(),
            "platform": sys.platform,
        },
        runtime_info={
            "admin_id": "{}".format(cfg['admin_qq']),
            "msg_source": cfg['msg_source_adapter'],
        }
    )
    # ap.ctr_mgr = center_v2_api

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

    im_mgr_inst = im_mgr.QQBotManager(ap=ap)
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
