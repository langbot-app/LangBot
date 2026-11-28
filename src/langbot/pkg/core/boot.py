from __future__ import annotations

import asyncio
import contextlib
import logging
import os
import sys

from langbot_plugin.utils.log import ServiceFormatter

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


def _log_boot_failure(app_inst: app.Application | None) -> None:
    """Log a fatal Core exception with severity even before SetupLoggerStage runs."""
    logger = getattr(app_inst, 'logger', None) or logging.getLogger('langbot')
    if isinstance(logger, logging.Logger) and not logger.hasHandlers():
        fallback = logging.StreamHandler(sys.stderr)
        fallback.setFormatter(ServiceFormatter('CORE', sys.stderr))
        logger.addHandler(fallback)
        try:
            logger.exception('LangBot core failed')
        finally:
            fallback.flush()
            logger.removeHandler(fallback)
            fallback.close()
        return
    logger.exception('LangBot core failed')


async def main(loop: asyncio.AbstractEventLoop):
    app_inst: app.Application | None = None
    runtime_loop = asyncio.get_running_loop()
    shutdown_requested = asyncio.Event()
    run_task: asyncio.Task | None = None
    shutdown_attempted = False
    failed = False
    try:
        import signal

        def signal_handler(sig, frame):
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
            shutdown_attempted = True
            try:
                await app_inst.shutdown()
            except BaseException:
                if not run_task.done():
                    run_task.cancel()
                with contextlib.suppress(BaseException):
                    await asyncio.gather(run_task, return_exceptions=True)
                raise
            if not run_task.done():
                run_task.cancel()
        for task in pending:
            task.cancel()
        results = await asyncio.gather(run_task, shutdown_task, return_exceptions=True)
        run_result = results[0]
        if isinstance(run_result, BaseException) and not isinstance(run_result, asyncio.CancelledError):
            raise run_result
    except Exception:
        failed = True
        _log_boot_failure(app_inst)
        raise SystemExit(1) from None
    finally:
        if app_inst is not None and not shutdown_attempted:
            shutdown_attempted = True
            try:
                await app_inst.shutdown()
            except Exception:
                _log_boot_failure(app_inst)
                if not failed:
                    raise SystemExit(1) from None
