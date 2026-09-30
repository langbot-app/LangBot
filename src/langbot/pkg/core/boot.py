from __future__ import annotations

import traceback
import asyncio
import contextlib
import os

from . import app
from . import stage
from ..utils import constants, importutil

# Import startup stage implementation to register
from . import stages

importutil.import_modules_in_pkg(stages)


stage_order = [
    'LoadConfigStage',
    'GenKeysStage',
    'SetupLoggerStage',
    'BuildAppStage',
    'ShowNotesStage',
]


async def make_app(loop: asyncio.AbstractEventLoop) -> app.Application:
    # Determine if it is debug mode
    if 'DEBUG' in os.environ and os.environ['DEBUG'] in ['true', '1']:
        constants.debug_mode = True

    ap = app.Application()

    ap.event_loop = loop

    try:
        # Execute startup stage
        for stage_name in stage_order:
            stage_cls = stage.preregistered_stages[stage_name]
            stage_inst = stage_cls()

            await stage_inst.run(ap)

        await ap.initialize()
    except BaseException:
        # ``main()`` cannot clean up a partially built application because
        # ``make_app()`` has not returned it yet. Release managers, pools and
        # child processes that earlier startup stages already attached.
        with contextlib.suppress(BaseException):
            await ap.shutdown()
        raise

    return ap


async def main(loop: asyncio.AbstractEventLoop):
    app_inst: app.Application | None = None
    runtime_loop = asyncio.get_running_loop()
    shutdown_requested = asyncio.Event()
    run_task: asyncio.Task | None = None
    try:
        import signal

        def signal_handler(sig, frame):
            print('[Signal] Program exit.')
            runtime_loop.call_soon_threadsafe(shutdown_requested.set)

        signal.signal(signal.SIGINT, signal_handler)
        if hasattr(signal, 'SIGTERM'):
            signal.signal(signal.SIGTERM, signal_handler)

        app_inst = await make_app(loop)
        if app_inst is None:
            return
        run_task = asyncio.create_task(app_inst.run())
        shutdown_task = asyncio.create_task(shutdown_requested.wait())
        done, pending = await asyncio.wait((run_task, shutdown_task), return_when=asyncio.FIRST_COMPLETED)
        if shutdown_task in done:
            await app_inst.shutdown()
            if not run_task.done():
                run_task.cancel()
        for task in pending:
            task.cancel()
        results = await asyncio.gather(run_task, shutdown_task, return_exceptions=True)
        run_result = results[0]
        if isinstance(run_result, BaseException) and not isinstance(run_result, asyncio.CancelledError):
            raise run_result
    except Exception:
        traceback.print_exc()
    finally:
        if app_inst is not None:
            await app_inst.shutdown()
