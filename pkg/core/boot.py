from __future__ import print_function

import traceback
import asyncio
import os

from . import app
from ..audit import identifier
from . import stage
from ..utils import constants

# 引入启动阶段实现以便注册
from .stages import load_config, setup_logger, build_app, migrate, show_notes


stage_order = [
    "LoadConfigStage",
    "MigrationStage",
    "SetupLoggerStage",
    "BuildAppStage",
    "ShowNotesStage"
]


async def make_app(loop: asyncio.AbstractEventLoop) -> app.Application:

    # 生成标识符
    identifier.init()

    # 确定是否为调试模式
    if "DEBUG" in os.environ and os.environ["DEBUG"] in ["true", "1"]:
        constants.debug_mode = True

    ap = app.Application()

    ap.event_loop = loop

    # 执行启动阶段
    for stage_name in stage_order:
        stage_cls = stage.preregistered_stages[stage_name]
        stage_inst = stage_cls()

        await stage_inst.run(ap)

    await ap.initialize()

    return ap


async def main(loop: asyncio.AbstractEventLoop):
    try:

        # 挂系统信号处理
        import signal

        ap: app.Application

        def signal_handler(sig, frame):
            print("[Signal] 程序退出.")
            # ap.shutdown()
            os._exit(0)

        signal.signal(signal.SIGINT, signal_handler)

        app_inst = await make_app(loop)
        ap = app_inst
        await app_inst.run()
    except Exception as e:
        traceback.print_exc()
