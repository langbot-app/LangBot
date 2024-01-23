from __future__ import print_function

import os
import sys

from . import files
from . import deps
from . import log
from . import config

from . import app
from ..audit import identifier
from ..database import manager as db_mgr
from ..openai import manager as llm_mgr
from ..openai import session as llm_session
from ..openai import dprompt as llm_dprompt
from ..qqbot import manager as im_mgr
from ..qqbot.cmds import aamgr as im_cmd_aamgr
from ..plugin import host as plugin_host
from ..utils.center import v2 as center_v2
from ..utils import updater
from ..utils import context

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

    cfg_mgr = await config.load_config()
    context.set_config_manager(cfg_mgr)
    cfg = cfg_mgr.data

    # 检查是否携带了 --override 或 -r 参数
    if '--override' in sys.argv or '-r' in sys.argv:
        use_override = True

    if use_override:
        overrided = await config.override_config_manager(cfg_mgr)
        if overrided:
            qcg_logger.info("以下配置项已使用 override.json 覆盖：" + ",".join(overrided))
    
    tips_mgr = await config.load_tips()

    # 初始化文字转图片
    from pkg.utils import text2img
    # TODO make it async
    text2img.initialize()

    # 检查管理员QQ号
    if cfg_mgr.data['admin_qq'] == 0:
        qcg_logger.warning("未设置管理员QQ号，将无法使用管理员命令，请在 config.py 中修改 admin_qq")

    # TODO make it async
    llm_dprompt.register_all()
    im_cmd_aamgr.register_all()
    im_cmd_aamgr.apply_privileges()

    # 构建组建实例
    ap = app.Application()
    ap.logger = qcg_logger
    ap.cfg_mgr = cfg_mgr
    ap.tips_mgr = tips_mgr

    center_v2_api = center_v2.V2CenterAPI(
        basic_info={
            "host_id": identifier.identifier['host_id'],
            "instance_id": identifier.identifier['instance_id'],
            "semantic_version": updater.get_current_tag(),
            "platform": sys.platform,
        },
        runtime_info={
            "admin_id": "{}".format(cfg['admin_qq']),
            "msg_source": cfg['msg_source_adapter'],
        }
    )
    ap.ctr_mgr = center_v2_api

    db_mgr_inst = db_mgr.DatabaseManager(ap)
    # TODO make it async
    db_mgr_inst.initialize_database()
    ap.db_mgr = db_mgr_inst

    llm_mgr_inst = llm_mgr.OpenAIInteract(ap)
    ap.llm_mgr = llm_mgr_inst
    # TODO make it async
    llm_session.load_sessions()

    im_mgr_inst = im_mgr.QQBotManager(first_time_init=True, ap=ap)
    ap.im_mgr = im_mgr_inst

    # TODO make it async
    plugin_host.load_plugins()
    # plugin_host.initialize_plugins()

    return ap


async def main():
    app_inst = await make_app()
    await app_inst.run()
