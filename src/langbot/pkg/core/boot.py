from __future__ import annotations

import traceback
import asyncio
import contextlib
import os

from . import app
from . import stage
from ..telemetry import diagnostics
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

            if stage_name == 'GenKeysStage':
                # Optional diagnostics must not make startup depend on package
                # metadata, session markers, or its background transport.
                ap.diagnostics = None
                space_config = ap.instance_config.data.get('space', {})
                if not space_config.get('disable_telemetry', False) and not space_config.get(
                    'disable_beta_diagnostics', False
                ):
                    manager = None
                    try:
                        manager = diagnostics.DiagnosticsManager(ap, marker_path='data/labels/beta_diagnostics_session')
                        await manager.start_session()
                        manager.start()
                        ap.diagnostics = manager
                    except BaseException as exc:
                        if manager is not None:
                            # Cleanup faults cannot replace the startup fault.
                            try:
                                await manager.shutdown(drain_timeout=0)
                            except asyncio.CancelledError:
                                if not isinstance(exc, asyncio.CancelledError):
                                    raise
                            except Exception:
                                pass
                        if not isinstance(exc, Exception):
                            raise
            await diagnostics.observe('lifecycle', 'startup.' + stage_name, source='startup', ap=ap)(stage_inst.run)(ap)

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
