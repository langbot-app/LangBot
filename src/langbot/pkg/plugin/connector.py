# For connect to plugin runtime.
from __future__ import annotations

import asyncio
from typing import Any
import typing
import os
import sys
import httpx
import traceback
import sqlalchemy
from async_lru import alru_cache
from langbot_plugin.api.entities.builtin.pipeline.query import provider_session

from ..core import app
from . import handler
from ..utils import platform
from langbot_plugin.runtime.io.controllers.stdio import (
    client as stdio_client_controller,
)
from langbot_plugin.runtime.io.controllers.ws import client as ws_client_controller
from langbot_plugin.api.entities import events
from langbot_plugin.api.entities import context
import langbot_plugin.runtime.io.connection as base_connection
from langbot_plugin.api.definition.components.manifest import ComponentManifest
from langbot_plugin.api.entities.builtin.command import (
    context as command_context,
    errors as command_errors,
)
from langbot_plugin.runtime.plugin.mgr import PluginInstallSource
from ..core import taskmgr
from ..entity.persistence import plugin as persistence_plugin


class PluginRuntimeConnector:
    """Plugin runtime connector"""

    ap: app.Application

    handler: handler.RuntimeConnectionHandler

    handler_task: asyncio.Task

    heartbeat_task: asyncio.Task | None = None

    stdio_client_controller: stdio_client_controller.StdioClientController

    ctrl: stdio_client_controller.StdioClientController | ws_client_controller.WebSocketClientController

    runtime_subprocess_on_windows: asyncio.subprocess.Process | None = None

    runtime_subprocess_on_windows_task: asyncio.Task | None = None

    runtime_disconnect_callback: typing.Callable[
        [PluginRuntimeConnector], typing.Coroutine[typing.Any, typing.Any, None]
    ]

    is_enable_plugin: bool = True
    """Mark if the plugin system is enabled"""

    def __init__(
        self,
        ap: app.Application,
        runtime_disconnect_callback: typing.Callable[
            [PluginRuntimeConnector], typing.Coroutine[typing.Any, typing.Any, None]
        ],
    ):
        self.ap = ap
        self.runtime_disconnect_callback = runtime_disconnect_callback
        self.is_enable_plugin = self.ap.instance_config.data.get('plugin', {}).get('enable', True)

    async def heartbeat_loop(self):
        while True:
            await asyncio.sleep(20)
            try:
                await self.ping_plugin_runtime()
                self.ap.logger.debug('Heartbeat to plugin runtime success.')
            except Exception as e:
                self.ap.logger.debug(f'Failed to heartbeat to plugin runtime: {e}')

    async def initialize(self):
        if not self.is_enable_plugin:
            self.ap.logger.info('Plugin system is disabled.')
            return

        async def new_connection_callback(connection: base_connection.Connection):
            async def disconnect_callback(
                rchandler: handler.RuntimeConnectionHandler,
            ) -> bool:
                if platform.get_platform() == 'docker' or platform.use_websocket_to_connect_plugin_runtime():
                    self.ap.logger.error('Disconnected from plugin runtime, trying to reconnect...')
                    await self.runtime_disconnect_callback(self)
                    return False
                else:
                    self.ap.logger.error(
                        'Disconnected from plugin runtime, cannot automatically reconnect while LangBot connects to plugin runtime via stdio, please restart LangBot.'
                    )
                    return False

            self.handler = handler.RuntimeConnectionHandler(connection, disconnect_callback, self.ap)

            self.handler_task = asyncio.create_task(self.handler.run())
            _ = await self.handler.ping()
            self.ap.logger.info('Connected to plugin runtime.')
            # Sync polymorphic component instances after connection
            try:
                await self.sync_polymorphic_component_instances()
            except Exception as e:
                traceback.print_exc()
                self.ap.logger.error(f'Failed to sync polymorphic component instances: {e}')
            await self.handler_task

        task: asyncio.Task | None = None

        if platform.get_platform() == 'docker' or platform.use_websocket_to_connect_plugin_runtime():  # use websocket
            self.ap.logger.info('use websocket to connect to plugin runtime')
            ws_url = self.ap.instance_config.data.get('plugin', {}).get(
                'runtime_ws_url', 'ws://langbot_plugin_runtime:5400/control/ws'
            )

            async def make_connection_failed_callback(
                ctrl: ws_client_controller.WebSocketClientController,
                exc: Exception = None,
            ) -> None:
                if exc is not None:
                    self.ap.logger.error(f'Failed to connect to plugin runtime({ws_url}): {exc}')
                else:
                    self.ap.logger.error(f'Failed to connect to plugin runtime({ws_url}), trying to reconnect...')
                await self.runtime_disconnect_callback(self)

            self.ctrl = ws_client_controller.WebSocketClientController(
                ws_url=ws_url,
                make_connection_failed_callback=make_connection_failed_callback,
            )
            task = self.ctrl.run(new_connection_callback)
        elif platform.get_platform() == 'win32':
            # Due to Windows's lack of supports for both stdio and subprocess:
            # See also: https://docs.python.org/zh-cn/3.13/library/asyncio-platforms.html
            # We have to launch runtime via cmd but communicate via ws.
            self.ap.logger.info('(windows) use cmd to launch plugin runtime and communicate via ws')

            if self.runtime_subprocess_on_windows is None:  # only launch once
                python_path = sys.executable
                env = os.environ.copy()
                self.runtime_subprocess_on_windows = await asyncio.create_subprocess_exec(
                    python_path,
                    '-m',
                    'langbot_plugin.cli.__init__',
                    'rt',
                    env=env,
                )

                # hold the process
                self.runtime_subprocess_on_windows_task = asyncio.create_task(self.runtime_subprocess_on_windows.wait())

            ws_url = 'ws://localhost:5400/control/ws'

            async def make_connection_failed_callback(
                ctrl: ws_client_controller.WebSocketClientController,
                exc: Exception = None,
            ) -> None:
                if exc is not None:
                    self.ap.logger.error(f'(windows) Failed to connect to plugin runtime({ws_url}): {exc}')
                else:
                    self.ap.logger.error(
                        f'(windows) Failed to connect to plugin runtime({ws_url}), trying to reconnect...'
                    )
                await self.runtime_disconnect_callback(self)

            self.ctrl = ws_client_controller.WebSocketClientController(
                ws_url=ws_url,
                make_connection_failed_callback=make_connection_failed_callback,
            )
            task = self.ctrl.run(new_connection_callback)

        else:  # stdio
            self.ap.logger.info('use stdio to connect to plugin runtime')
            # cmd: lbp rt -s
            python_path = sys.executable
            env = os.environ.copy()
            self.ctrl = stdio_client_controller.StdioClientController(
                command=python_path,
                args=['-m', 'langbot_plugin.cli.__init__', 'rt', '-s'],
                env=env,
            )
            task = self.ctrl.run(new_connection_callback)

        if self.heartbeat_task is None:
            self.heartbeat_task = asyncio.create_task(self.heartbeat_loop())

        asyncio.create_task(task)

    async def initialize_plugins(self):
        pass

    async def ping_plugin_runtime(self):
        if not hasattr(self, 'handler'):
            raise Exception('Plugin runtime is not connected')

        return await self.handler.ping()

    async def install_plugin(
        self,
        install_source: PluginInstallSource,
        install_info: dict[str, Any],
        task_context: taskmgr.TaskContext | None = None,
    ):
        if install_source == PluginInstallSource.LOCAL:
            # transfer file before install
            file_bytes = install_info['plugin_file']
            file_key = await self.handler.send_file(file_bytes, 'lbpkg')
            install_info['plugin_file_key'] = file_key
            del install_info['plugin_file']
            self.ap.logger.info(f'Transfered file {file_key} to plugin runtime')
        elif install_source == PluginInstallSource.GITHUB:
            # download and transfer file
            try:
                async with httpx.AsyncClient(
                    trust_env=True,
                    follow_redirects=True,
                    timeout=20,
                ) as client:
                    response = await client.get(
                        install_info['asset_url'],
                    )
                    response.raise_for_status()
                    file_bytes = response.content
                    file_key = await self.handler.send_file(file_bytes, 'lbpkg')
                    install_info['plugin_file_key'] = file_key
                    self.ap.logger.info(f'Transfered file {file_key} to plugin runtime')
            except Exception as e:
                self.ap.logger.error(f'Failed to download file from GitHub: {e}')
                raise Exception(f'Failed to download file from GitHub: {e}')

        async for ret in self.handler.install_plugin(install_source.value, install_info):
            current_action = ret.get('current_action', None)
            if current_action is not None:
                if task_context is not None:
                    task_context.set_current_action(current_action)

            trace = ret.get('trace', None)
            if trace is not None:
                if task_context is not None:
                    task_context.trace(trace)

    async def upgrade_plugin(
        self,
        plugin_author: str,
        plugin_name: str,
        task_context: taskmgr.TaskContext | None = None,
    ) -> dict[str, Any]:
        async for ret in self.handler.upgrade_plugin(plugin_author, plugin_name):
            current_action = ret.get('current_action', None)
            if current_action is not None:
                if task_context is not None:
                    task_context.set_current_action(current_action)

            trace = ret.get('trace', None)
            if trace is not None:
                if task_context is not None:
                    task_context.trace(trace)

    async def delete_plugin(
        self,
        plugin_author: str,
        plugin_name: str,
        delete_data: bool = False,
        task_context: taskmgr.TaskContext | None = None,
    ) -> dict[str, Any]:
        async for ret in self.handler.delete_plugin(plugin_author, plugin_name):
            current_action = ret.get('current_action', None)
            if current_action is not None:
                if task_context is not None:
                    task_context.set_current_action(current_action)

            trace = ret.get('trace', None)
            if trace is not None:
                if task_context is not None:
                    task_context.trace(trace)

        # Clean up plugin settings and binary storage if requested
        if delete_data:
            if task_context is not None:
                task_context.trace('Cleaning up plugin configuration and storage...')
            await self.handler.cleanup_plugin_data(plugin_author, plugin_name)

    async def list_plugins(self, component_kinds: list[str] | None = None) -> list[dict[str, Any]]:
        """List plugins, optionally filtered by component kinds.

        Args:
            component_kinds: Optional list of component kinds to filter by.
                           If provided, only plugins that contain at least one
                           component of the specified kinds will be returned.
                           E.g., ['Command', 'EventListener', 'Tool'] for pipeline-related plugins.
        """
        if not self.is_enable_plugin:
            return []

        plugins = await self.handler.list_plugins()

        # Filter plugins by component kinds if specified
        if component_kinds is not None:
            filtered_plugins = []
            for plugin in plugins:
                components = plugin.get('components', [])
                has_matching_component = False
                for component in components:
                    component_kind = component.get('manifest', {}).get('manifest', {}).get('kind', '')
                    if component_kind in component_kinds:
                        has_matching_component = True
                        break
                if has_matching_component:
                    filtered_plugins.append(plugin)
            plugins = filtered_plugins

        # Sort plugins: debug plugins first, then by installation time (newest first)
        # Get installation timestamps from database in a single query
        plugin_timestamps = {}

        if plugins:
            # Build list of (author, name) tuples for all plugins
            plugin_ids = []
            for plugin in plugins:
                author = plugin.get('manifest', {}).get('manifest', {}).get('metadata', {}).get('author', '')
                name = plugin.get('manifest', {}).get('manifest', {}).get('metadata', {}).get('name', '')
                if author and name:
                    plugin_ids.append((author, name))

            # Fetch all timestamps in a single query using OR conditions
            if plugin_ids:
                conditions = [
                    sqlalchemy.and_(
                        persistence_plugin.PluginSetting.plugin_author == author,
                        persistence_plugin.PluginSetting.plugin_name == name,
                    )
                    for author, name in plugin_ids
                ]

                result = await self.ap.persistence_mgr.execute_async(
                    sqlalchemy.select(
                        persistence_plugin.PluginSetting.plugin_author,
                        persistence_plugin.PluginSetting.plugin_name,
                        persistence_plugin.PluginSetting.created_at,
                    ).where(sqlalchemy.or_(*conditions))
                )

                for row in result:
                    plugin_id = f'{row.plugin_author}/{row.plugin_name}'
                    plugin_timestamps[plugin_id] = row.created_at

        # Sort: debug plugins first (descending), then by created_at (descending)
        def sort_key(plugin):
            author = plugin.get('manifest', {}).get('manifest', {}).get('metadata', {}).get('author', '')
            name = plugin.get('manifest', {}).get('manifest', {}).get('metadata', {}).get('name', '')
            plugin_id = f'{author}/{name}'

            is_debug = plugin.get('debug', False)
            created_at = plugin_timestamps.get(plugin_id)

            # Return tuple: (not is_debug, -timestamp)
            # not is_debug: False (0) for debug plugins, True (1) for non-debug
            # -timestamp: to sort newest first (will be None for plugins without timestamp)
            timestamp_value = -created_at.timestamp() if created_at else 0
            return (not is_debug, timestamp_value)

        plugins.sort(key=sort_key)

        return plugins

    async def get_plugin_info(self, author: str, plugin_name: str) -> dict[str, Any]:
        return await self.handler.get_plugin_info(author, plugin_name)

    async def set_plugin_config(self, plugin_author: str, plugin_name: str, config: dict[str, Any]) -> dict[str, Any]:
        return await self.handler.set_plugin_config(plugin_author, plugin_name, config)

    @alru_cache(ttl=5 * 60)  # 5 minutes
    async def get_plugin_icon(self, plugin_author: str, plugin_name: str) -> dict[str, Any]:
        return await self.handler.get_plugin_icon(plugin_author, plugin_name)

    @alru_cache(ttl=5 * 60)  # 5 minutes
    async def get_plugin_readme(self, plugin_author: str, plugin_name: str, language: str = 'en') -> str:
        return await self.handler.get_plugin_readme(plugin_author, plugin_name, language)

    @alru_cache(ttl=5 * 60)
    async def get_plugin_assets(self, plugin_author: str, plugin_name: str, filepath: str) -> dict[str, Any]:
        return await self.handler.get_plugin_assets(plugin_author, plugin_name, filepath)

    async def get_debug_info(self) -> dict[str, Any]:
        """Get debug information including debug key and WS URL"""
        if not self.is_enable_plugin:
            return {}
        return await self.handler.get_debug_info()

    async def emit_event(
        self,
        event: events.BaseEventModel,
        bound_plugins: list[str] | None = None,
    ) -> context.EventContext:
        event_ctx = context.EventContext.from_event(event)

        if not self.is_enable_plugin:
            return event_ctx

        # Pass include_plugins to runtime for filtering
        event_ctx_result = await self.handler.emit_event(
            event_ctx.model_dump(serialize_as_any=False), include_plugins=bound_plugins
        )

        event_ctx = context.EventContext.model_validate(event_ctx_result['event_context'])

        return event_ctx

    async def list_tools(self, bound_plugins: list[str] | None = None) -> list[ComponentManifest]:
        if not self.is_enable_plugin:
            return []

        # Pass include_plugins to runtime for filtering
        list_tools_data = await self.handler.list_tools(include_plugins=bound_plugins)

        tools = [ComponentManifest.model_validate(tool) for tool in list_tools_data]

        return tools

    async def call_tool(
        self,
        tool_name: str,
        parameters: dict[str, Any],
        session: provider_session.Session,
        query_id: int,
        bound_plugins: list[str] | None = None,
    ) -> dict[str, Any]:
        if not self.is_enable_plugin:
            return {'error': 'Tool not found: plugin system is disabled'}

        # Pass include_plugins to runtime for validation
        return await self.handler.call_tool(
            tool_name, parameters, session.model_dump(serialize_as_any=True), query_id, include_plugins=bound_plugins
        )

    async def list_commands(self, bound_plugins: list[str] | None = None) -> list[ComponentManifest]:
        if not self.is_enable_plugin:
            return []

        # Pass include_plugins to runtime for filtering
        list_commands_data = await self.handler.list_commands(include_plugins=bound_plugins)

        commands = [ComponentManifest.model_validate(command) for command in list_commands_data]

        return commands

    async def execute_command(
        self, command_ctx: command_context.ExecuteContext, bound_plugins: list[str] | None = None
    ) -> typing.AsyncGenerator[command_context.CommandReturn, None]:
        if not self.is_enable_plugin:
            yield command_context.CommandReturn(error=command_errors.CommandNotFoundError(command_ctx.command))
            return

        # Pass include_plugins to runtime for validation
        gen = self.handler.execute_command(command_ctx.model_dump(serialize_as_any=True), include_plugins=bound_plugins)

        async for ret in gen:
            cmd_ret = command_context.CommandReturn.model_validate(ret)

            yield cmd_ret

    # KnowledgeRetriever methods
    async def list_knowledge_retrievers(self, bound_plugins: list[str] | None = None) -> list[dict[str, Any]]:
        """List all available KnowledgeRetriever components."""
        if not self.is_enable_plugin:
            return []

        retrievers_data = await self.handler.list_knowledge_retrievers(include_plugins=bound_plugins)
        return retrievers_data

    async def retrieve_knowledge(
        self,
        plugin_author: str,
        plugin_name: str,
        retriever_name: str,
        instance_id: str,
        retrieval_context: dict[str, Any],
    ) -> list[dict[str, Any]]:
        """Retrieve knowledge using a KnowledgeRetriever instance."""
        if not self.is_enable_plugin:
            return []

        return await self.handler.retrieve_knowledge(
            plugin_author, plugin_name, retriever_name, instance_id, retrieval_context
        )

    def dispose(self):
        # No need to consider the shutdown on Windows
        # for Windows can kill processes and subprocesses chainly

        if self.is_enable_plugin and isinstance(self.ctrl, stdio_client_controller.StdioClientController):
            self.ap.logger.info('Terminating plugin runtime process...')
            self.ctrl.process.terminate()

        if self.heartbeat_task is not None:
            self.heartbeat_task.cancel()
            self.heartbeat_task = None

    async def sync_polymorphic_component_instances(self) -> dict[str, Any]:
        """Sync polymorphic component instances with runtime.

        This collects all external knowledge bases from database and sends to runtime
        to ensure instance integrity across restarts.
        """
        if not self.is_enable_plugin:
            return {}

        # ===== external knowledge bases =====

        external_kbs = await self.ap.external_kb_service.get_external_knowledge_bases()

        # Build required_instances list
        required_instances = []
        for kb in external_kbs:
            required_instances.append(
                {
                    'instance_id': kb['uuid'],
                    'plugin_author': kb['plugin_author'],
                    'plugin_name': kb['plugin_name'],
                    'component_kind': 'KnowledgeRetriever',
                    'component_name': kb['retriever_name'],
                    'config': kb['retriever_config'],
                }
            )

        self.ap.logger.info(f'Syncing {len(required_instances)} polymorphic component instances to runtime')

        # Send to runtime
        sync_result = await self.handler.sync_polymorphic_component_instances(required_instances)

        self.ap.logger.info(
            f'Sync complete: {len(sync_result.get("success_instances", []))} succeeded, '
            f'{len(sync_result.get("failed_instances", []))} failed'
        )

        return sync_result
