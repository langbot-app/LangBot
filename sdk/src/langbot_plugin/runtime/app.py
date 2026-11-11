from __future__ import annotations

import argparse
from enum import Enum
import logging
import os
import signal
from collections.abc import Mapping

import asyncio
import contextlib

from langbot_plugin.runtime.io.controllers.stdio import (
    server as stdio_controller_server,
)
from langbot_plugin.runtime.io.controllers.ws import server as ws_controller_server
from langbot_plugin.runtime.io.handlers import control as control_handler_cls
from langbot_plugin.runtime.io.handlers import plugin as plugin_handler_cls
from langbot_plugin.runtime.io.connection import Connection
from langbot_plugin.runtime.plugin import mgr as plugin_mgr_cls
from langbot_plugin.runtime import context
from langbot_plugin.runtime.bounded_executor import (
    configure_bounded_default_executor_from_env,
)
from langbot_plugin.runtime.event_loop_monitor import EventLoopLagMonitor
from langbot_plugin.runtime import ops_metrics as ops_metrics_module
from langbot_plugin.version import __version__ as runtime_version

from langbot_plugin.runtime.security import (
    PLUGIN_DEBUG_KEY_HEADER,
    PLUGIN_REGISTRATION_CAPABILITY_HEADER,
    PLUGIN_RUNTIME_CONTROL_TOKEN_ENV,
    PLUGIN_RUNTIME_CONTROL_TOKEN_HEADER,
    validate_runtime_secret,
)
from langbot_plugin.utils.log import configure_process_logging

logger = logging.getLogger(__name__)


class ControlConnectionMode(Enum):
    STDIO = "stdio"
    WS = "ws"


class RuntimeApplication:
    """Runtime application context."""

    _control_connection_mode: ControlConnectionMode

    context: context.RuntimeContext

    def __init__(self, args: argparse.Namespace):
        self.args = args
        if getattr(args, "pypi_index_url", ""):
            os.environ["LANGBOT_PLUGIN_PYPI_INDEX_URL"] = args.pypi_index_url
        if getattr(args, "pypi_trusted_host", ""):
            os.environ["LANGBOT_PLUGIN_PYPI_TRUSTED_HOST"] = args.pypi_trusted_host
        self.context = context.RuntimeContext()
        self.event_loop_monitor = EventLoopLagMonitor()
        self.context.event_loop_monitor = self.event_loop_monitor
        self._server_tasks: set[asyncio.Task] = set()
        self._control_tasks: set[asyncio.Task] = set()
        self._control_handler_lock = asyncio.Lock()
        self._closing = False
        self._shutdown_complete = False

        # Set the debug port in context so PluginManager can use it
        self.context.ws_debug_port = self.args.ws_debug_port

        self.context.plugin_mgr = plugin_mgr_cls.PluginManager(self.context)

        if args.stdio_control:
            self._control_connection_mode = ControlConnectionMode.STDIO
        else:
            self._control_connection_mode = ControlConnectionMode.WS

        # build controllers layer
        if self._control_connection_mode == ControlConnectionMode.STDIO:
            self.context.stdio_server = stdio_controller_server.StdioServerController()

        elif self._control_connection_mode == ControlConnectionMode.WS:
            configured_control_token = str(
                os.environ.get(PLUGIN_RUNTIME_CONTROL_TOKEN_ENV, "")
            ).strip()
            expected_headers = {}
            if configured_control_token:
                expected_headers[PLUGIN_RUNTIME_CONTROL_TOKEN_HEADER] = (
                    validate_runtime_secret(
                        configured_control_token,
                        name=PLUGIN_RUNTIME_CONTROL_TOKEN_ENV,
                    )
                )
            control_host = "0.0.0.0"
            self.context.ws_control_server = (
                ws_controller_server.WebSocketServerController(
                    self.args.ws_control_port,
                    host=control_host,
                    expected_headers=expected_headers,
                    health_snapshot_provider=self._health_snapshot,
                )
            )

        # The plugin WebSocket serves explicit debug clients and Windows
        # Runtime-managed children, with separate authentication credentials.
        self.context.ws_debug_server = ws_controller_server.WebSocketServerController(
            self.args.ws_debug_port,
            request_authenticator=self._authenticate_plugin_request,
            health_snapshot_provider=self._health_snapshot,
        )

    def _health_snapshot(self) -> dict[str, object]:
        """Return public aggregate health without credentials or tenant IDs."""

        ops_metrics = getattr(self.context.plugin_mgr, "ops_metrics", None)
        process = ops_metrics_module.sample_process_resources() if ops_metrics else {}
        runtime: dict[str, object] = {
            "version": runtime_version,
            "profile": self.context.runtime_profile or "unknown",
        }
        if ops_metrics is not None:
            runtime["uptime_seconds"] = ops_metrics.uptime_seconds
        runtime.update(process)
        return {
            "live": not self._closing,
            "runtime": runtime,
            "resources": self.context.get_runtime_resource_stats(),
        }

    def _authenticate_plugin_request(self, headers: Mapping[str, str]) -> bool:
        """Admit explicit debug clients or one pending installed plugin."""

        supplied_debug_key = str(headers.get(PLUGIN_DEBUG_KEY_HEADER) or "")
        if self.context.workspace_debug_tokens.binding_for_token(supplied_debug_key):
            return True

        registration_capability = str(
            headers.get(PLUGIN_REGISTRATION_CAPABILITY_HEADER) or ""
        )
        return self.context.plugin_mgr.is_registration_capability_pending(
            registration_capability
        )

    def set_control_handler(
        self, handler: control_handler_cls.ControlConnectionHandler
    ):
        previous = self.context.activate_control_handler(handler)
        if previous is not None and previous is not handler:
            previous.invalidate()
        mark_ready = getattr(
            self.context.plugin_mgr,
            "mark_control_connection_ready",
            None,
        )
        if mark_ready is not None:
            mark_ready()

        async def run_active_handler() -> None:
            async with self._control_handler_lock:
                if self._closing:
                    handler.invalidate()
                    if self.context.is_active_control_handler(handler):
                        self.context.control_handler = None
                    await handler.close()
                    return

            close_task: asyncio.Task[None] | None = None
            if previous is not None and previous is not handler:
                close_task = asyncio.create_task(previous.close())
            try:
                await handler.run()
            finally:
                if close_task is not None:
                    try:
                        await close_task
                    except Exception:
                        logger.warning(
                            "Failed to close superseded control connection",
                            exc_info=True,
                        )
                async with self._control_handler_lock:
                    if self.context.is_active_control_handler(handler):
                        self.context.control_handler = None

        task = asyncio.create_task(run_active_handler())
        self._control_tasks.add(task)
        task.add_done_callback(self._control_task_done)
        logger.info("Got control connection.")
        return task

    def _control_task_done(self, task: asyncio.Task) -> None:
        self._control_tasks.discard(task)
        if task.cancelled():
            return
        exc = task.exception()
        if exc is not None:
            logger.error(
                "Control connection task failed",
                exc_info=(type(exc), exc, exc.__traceback__),
            )

    async def _start_legacy_plugin_workloads(self) -> None:
        """Start the OSS ``data/plugins`` bridge only after the handshake.

        The Runtime does not know its immutable deployment profile until
        ``SET_RUNTIME_CONFIG`` arrives.  In particular, inspecting legacy
        artifacts or installing their dependencies before that handshake
        would let a shared Runtime bypass its verified artifact, nsjail, and
        immutable dependency-environment boundaries.
        """

        await self.context.wait_for_runtime_configuration()
        if self.context.runtime_profile == "shared":
            logger.info(
                "Shared Runtime skips legacy data/plugins dependency and launch paths"
            )
            return

        if not self.args.skip_deps_check:
            logger.info("Ensuring all installed plugins dependencies are installed...")
            await self.context.plugin_mgr.ensure_all_plugins_dependencies_installed()

        if not self.args.debug_only:
            await self.context.plugin_mgr.launch_all_plugins()

    async def run(self):
        server_coroutines = []

        # ==== control server ====
        async def new_control_connection_callback(connection: Connection):
            handler = control_handler_cls.ControlConnectionHandler(
                connection, self.context
            )
            await self.set_control_handler(handler)

        if self.context.stdio_server:
            server_coroutines.append(
                self.context.stdio_server.run(new_control_connection_callback)
            )

        if self.context.ws_control_server:
            server_coroutines.append(
                self.context.ws_control_server.run(new_control_connection_callback)
            )

        # ==== plugin debug server ====
        async def new_plugin_debug_connection_callback(connection: Connection):
            plugin_handler = plugin_handler_cls.PluginConnectionHandler(
                connection, self.context, debug_plugin=True
            )
            request_headers = getattr(connection, "request_headers", {})
            plugin_handler.debug_workspace_binding = (
                self.context.workspace_debug_tokens.binding_for_token(
                    str(request_headers.get(PLUGIN_DEBUG_KEY_HEADER) or "")
                )
            )
            plugin_handler.debug_auth_token = str(
                request_headers.get(PLUGIN_DEBUG_KEY_HEADER) or ""
            )

            await self.context.plugin_mgr.add_plugin_handler(plugin_handler)

        if self.context.ws_debug_server:
            server_coroutines.append(
                self.context.ws_debug_server.run(new_plugin_debug_connection_callback)
            )

        # Bind listeners before waiting for the immutable Runtime handshake.
        # Otherwise LangBot has no transport on which to send SET_RUNTIME_CONFIG.
        for coroutine in server_coroutines:
            task = asyncio.create_task(coroutine)
            self._server_tasks.add(task)
        await asyncio.sleep(0)
        for task in list(self._server_tasks):
            if task.done() and not task.cancelled():
                exc = task.exception()
                if exc is not None:
                    raise exc

        # The transport tasks must start first so LangBot can deliver the
        # immutable Runtime handshake. Legacy plugin inspection and launch are
        # gated by the resulting profile inside this concurrent workload.
        workload_task = asyncio.create_task(self._start_legacy_plugin_workloads())
        self._server_tasks.add(workload_task)

        if self._server_tasks:
            await asyncio.gather(*list(self._server_tasks))

    async def shutdown(self):
        if self._shutdown_complete:
            return
        self._closing = True

        async with self._control_handler_lock:
            control_handler = getattr(self.context, "control_handler", None)
            if control_handler is not None:
                close = getattr(control_handler, "close", None)
                if close is not None:
                    with contextlib.suppress(Exception):
                        await close()

        await self.context.plugin_mgr.shutdown_all_plugins()

        tasks = [*self._control_tasks, *self._server_tasks]
        for task in tasks:
            task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        self._control_tasks.clear()
        self._server_tasks.clear()
        self._shutdown_complete = True


async def _run_with_shutdown(app: RuntimeApplication) -> None:
    """Run the Runtime and turn container SIGTERM into an orderly shutdown."""

    app.blocking_executor = configure_bounded_default_executor_from_env(
        thread_name_prefix="langbot-plugin-runtime-blocking",
    )
    runtime_context = getattr(app, "context", None)
    if runtime_context is not None:
        runtime_context.blocking_executor = app.blocking_executor
    event_loop_monitor = getattr(app, "event_loop_monitor", None)
    if event_loop_monitor is not None:
        event_loop_monitor.start()
    loop = asyncio.get_running_loop()
    runtime_task = asyncio.current_task()
    signal_handler_installed = False

    if runtime_task is not None:
        try:
            loop.add_signal_handler(signal.SIGTERM, runtime_task.cancel)
            signal_handler_installed = True
        except (NotImplementedError, RuntimeError):
            # Windows event loops do not expose POSIX signal handlers.
            pass

    try:
        await app.run()
    finally:
        if signal_handler_installed:
            loop.remove_signal_handler(signal.SIGTERM)
        try:
            await app.shutdown()
        finally:
            if event_loop_monitor is not None:
                await event_loop_monitor.stop()


def main(args: argparse.Namespace):
    configure_process_logging()

    app = RuntimeApplication(args)

    try:
        asyncio.run(_run_with_shutdown(app))
    except asyncio.CancelledError:
        logger.info("Runtime application cancelled")
        return
    except KeyboardInterrupt:
        logger.info("Keyboard interrupt, exiting...")
        return
