from __future__ import print_function

import traceback
import asyncio
import os

from . import app
from . import stage
from ..utils import constants, importutil

# 引入启动阶段实现以便注册
from . import stages

importutil.import_modules_in_pkg(stages)


stage_order = [
    'LoadConfigStage',
    'MigrationStage',
    'GenKeysStage',
    'SetupLoggerStage',
    'BuildAppStage',
    'ShowNotesStage',
]


async def make_app(loop: asyncio.AbstractEventLoop) -> app.Application:
    # 确定是否为调试模式
    if 'DEBUG' in os.environ and os.environ['DEBUG'] in ['true', '1']:
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

        def signal_handler(sig, frame):
            print('[Signal] 程序退出.')
            # ap.shutdown()
            os._exit(0)

        signal.signal(signal.SIGINT, signal_handler)

        app_inst = await make_app(loop)
        await app_inst.run()
    except Exception:
        traceback.print_exc()
