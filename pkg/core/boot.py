from __future__ import print_function

import sys

from .bootutils import files
from .bootutils import log
from .bootutils import config

from . import app
from ..pipeline import pool
from ..pipeline import controller
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

from .stages import build_app, load_config, setup_logger
from . import stage


stage_order = [
    "LoadConfigStage",
    "SetupLoggerStage",
    "BuildAppStage"
]


async def make_app() -> app.Application:

    # 生成标识符
    identifier.init()

    ap = app.Application()

    for stage_name in stage_order:
        stage_cls = stage.preregistered_stages[stage_name]
        stage_inst = stage_cls()
        await stage_inst.run(ap)

    await ap.initialize()

    return ap


async def main():
    app_inst = await make_app()
    await app_inst.run()
