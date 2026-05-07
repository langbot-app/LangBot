# For connect to plugin runtime.
from __future__ import annotations

import asyncio
import io
import time
import zipfile
from typing import Any
import typing
import os
import sys
import httpx
import sqlalchemy
from async_lru import alru_cache
from langbot_plugin.api.entities.builtin.pipeline.query import provider_session

from ..core import app
from . import handler
from ..utils import platform
from ..utils.managed_runtime import ManagedRuntimeConnector
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


class PluginRuntimeConnector(ManagedRuntimeConnector):
    """Plugin runtime connector"""

    handler: handler.RuntimeConnectionHandler

    handler_task: asyncio.Task

    heartbeat_task: asyncio.Task | None = None

    stdio_client_controller: stdio_client_controller.StdioClientController

    ctrl: stdio_client_controller.StdioClientController | ws_client_controller.WebSocketClientController

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
        super().__init__(ap)
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

            await self._start_runtime_subprocess('-m', 'langbot_plugin.cli.__init__', 'rt')

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

    def _extract_deps_metadata(
        self,
        file_bytes: bytes,
        task_context: taskmgr.TaskContext | None,
    ):
        """Extract dependency count from requirements.txt inside plugin zip."""
        if task_context is None:
            return
        try:
            with zipfile.ZipFile(io.BytesIO(file_bytes)) as zf:
                for name in zf.namelist():
                    if name.endswith('requirements.txt'):
                        content = zf.read(name).decode('utf-8', errors='ignore')
                        deps = [
                            line.strip()
                            for line in content.splitlines()
                            if line.strip() and not line.strip().startswith('#')
                        ]
                        task_context.metadata['deps_total'] = len(deps)
                        task_context.metadata['deps_list'] = deps
                        break
        except Exception:
            pass

    async def _install_mcp_from_marketplace(
        self,
        mcp_data: dict[str, Any],
        task_context: taskmgr.TaskContext | None = None,
    ):
        """Install an MCP server from marketplace data."""
        from ..entity.persistence import mcp as persistence_mcp
        import uuid

        config = mcp_data.get('config', {})
        url = config.get('url', '')
        # Use __ instead of / to avoid URL routing issues with slashes
        name = f"{mcp_data.get('author', '')}__{mcp_data.get('name', '')}"

        # Determine mode from URL
        if 'sse' in url.lower():
            mode = 'sse'
        elif url.startswith('http'):
            mode = 'http'
        else:
            mode = 'stdio'

        # Build extra_args from config
        extra_args = {
            'url': url,
            'timeout': config.get('timeout', 30),
            'sse_read_timeout': config.get('sse_read_timeout', 300),
        }

        # Check if MCP server already exists
        existing = await self.ap.persistence_mgr.execute_async(
            sqlalchemy.select(persistence_mcp.MCPServer).where(persistence_mcp.MCPServer.name == name)
        )
        if existing.scalar_one_or_none():
            self.ap.logger.info(f'MCP server {name} already exists, skipping installation')
            return

        # Create MCP server record
        server_uuid = str(uuid.uuid4())
        server_data = {
            'uuid': server_uuid,
            'name': name,
            'enable': True,
            'mode': mode,
            'extra_args': extra_args,
        }

        await self.ap.persistence_mgr.execute_async(
            sqlalchemy.insert(persistence_mcp.MCPServer).values(server_data)
        )

        # Start the MCP server
        result = await self.ap.persistence_mgr.execute_async(
            sqlalchemy.select(persistence_mcp.MCPServer).where(persistence_mcp.MCPServer.uuid == server_uuid)
        )
        server_entity = result.first()
        if server_entity:
            server_config = self.ap.persistence_mgr.serialize_model(persistence_mcp.MCPServer, server_entity)
            if self.ap.tool_mgr.mcp_tool_loader:
                mcp_task = asyncio.create_task(
                    self.ap.tool_mgr.mcp_tool_loader.host_mcp_server(server_config)
                )
                self.ap.tool_mgr.mcp_tool_loader._hosted_mcp_tasks.append(mcp_task)

        self.ap.logger.info(f'Installed MCP server {name} from marketplace')

    async def _install_skill_from_zip(
        self,
        file_bytes: bytes,
        filename: str,
        task_context: taskmgr.TaskContext | None = None,
    ):
        """Install a skill from marketplace ZIP data."""
        from ..api.http.service.skill import SkillService

        skill_service = SkillService(self.ap)

        self.ap.logger.info(f'Installing skill from marketplace ZIP ({len(file_bytes)} bytes)')

        # Install from ZIP using skill service
        result = await skill_service.install_from_zip_upload(
            file_bytes=file_bytes,
            filename=filename + '.zip',
        )
        self.ap.logger.info(f'Skill installed successfully: {result}')

    async def install_plugin(
        self,
        install_source: PluginInstallSource,
        install_info: dict[str, Any],
        task_context: taskmgr.TaskContext | None = None,
    ):
        if install_source == PluginInstallSource.MARKETPLACE:
            # Handle marketplace plugin/mcp/skill installation
            plugin_author = install_info.get('plugin_author', '')
            plugin_name = install_info.get('plugin_name', '')
            space_url = self.ap.instance_config.data.get('space', {}).get('url', 'https://space.langbot.app').rstrip('/')

            # Try MCP endpoint first
            async with httpx.AsyncClient(trust_env=True, timeout=15) as client:
                mcp_resp = await client.get(f'{space_url}/api/v1/marketplace/mcps/{plugin_author}/{plugin_name}')
                if mcp_resp.status_code == 200:
                    mcp_data = mcp_resp.json().get('data', {}).get('mcp', {})
                    if mcp_data.get('config'):
                        # It's an MCP - create server locally
                        self.ap.logger.info(f'Installing MCP from marketplace: {plugin_author}/{plugin_name}')
                        if task_context:
                            task_context.set_current_action('installing mcp server')
                        await self._install_mcp_from_marketplace(mcp_data, task_context)
                        return
                    else:
                        raise Exception(f'MCP {plugin_author}/{plugin_name} has no config')
                elif mcp_resp.status_code == 404:
                    # Try skill endpoint - download ZIP and install
                    self.ap.logger.info(f'Installing skill from marketplace: {plugin_author}/{plugin_name}')
                    if task_context:
                        task_context.set_current_action('installing skill from marketplace')

                    # Get skill detail to find version
                    skill_resp = await client.get(f'{space_url}/api/v1/marketplace/skills/{plugin_author}/{plugin_name}')
                    if skill_resp.status_code == 200:
                        # Download the skill ZIP (no version needed - uses latest)
                        if task_context:
                            task_context.set_current_action('downloading skill package')

                        download_resp = await client.get(
                            f'{space_url}/api/v1/marketplace/skills/download/{plugin_author}/{plugin_name}'
                        )
                        if download_resp.status_code != 200:
                            raise Exception(f'Failed to download skill {plugin_author}/{plugin_name}: {download_resp.status_code}')

                        file_bytes = download_resp.content
                        file_size = len(file_bytes)
                        self.ap.logger.info(f'Downloaded skill ZIP ({file_size} bytes)')

                        # Install skill from ZIP using skill service
                        await self._install_skill_from_zip(file_bytes, f'{plugin_author}-{plugin_name}', task_context)
                        return
                    else:
                        raise Exception(f'Skill {plugin_author}/{plugin_name} not found in marketplace')
                else:
                    mcp_resp.raise_for_status()
                    raise Exception(f'Failed to get MCP {plugin_author}/{plugin_name}')

        if install_source == PluginInstallSource.LOCAL:
            # transfer file before install
            file_bytes = install_info['plugin_file']
            self._extract_deps_metadata(file_bytes, task_context)
            file_key = await self.handler.send_file(file_bytes, 'lbpkg')
            install_info['plugin_file_key'] = file_key
            del install_info['plugin_file']
            self.ap.logger.info(f'Transfered file {file_key} to plugin runtime')
        elif install_source == PluginInstallSource.GITHUB:
            # download and transfer file with streaming progress
            try:
                async with httpx.AsyncClient(
                    trust_env=True,
                    follow_redirects=True,
                    timeout=60,
                ) as client:
                    async with client.stream('GET', install_info['asset_url']) as response:
                        response.raise_for_status()
                        total = int(response.headers.get('content-length', 0))
                        downloaded = 0
                        chunks: list[bytes] = []
                        start_time = time.time()

                        if task_context is not None:
                            task_context.set_current_action('downloading plugin package')
                            task_context.metadata['download_total'] = total
                            task_context.metadata['download_current'] = 0
                            task_context.metadata['download_speed'] = 0

                        async for chunk in response.aiter_bytes(chunk_size=8192):
                            chunks.append(chunk)
                            downloaded += len(chunk)

                            if task_context is not None:
                                elapsed = time.time() - start_time
                                task_context.metadata['download_current'] = downloaded
                                task_context.metadata['download_total'] = total
                                task_context.metadata['download_speed'] = downloaded / elapsed if elapsed > 0 else 0

                    file_bytes = b''.join(chunks)
                    self._extract_deps_metadata(file_bytes, task_context)
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

            # Forward structured metadata from runtime
            metadata = ret.get('metadata', None)
            if metadata is not None and task_context is not None:
                task_context.metadata.update(metadata)

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

    async def handle_page_api(
        self,
        plugin_author: str,
        plugin_name: str,
        page_id: str,
        endpoint: str,
        method: str,
        body: Any = None,
    ) -> dict[str, Any]:
        return await self.handler.handle_page_api(plugin_author, plugin_name, page_id, endpoint, method, body)

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

    async def retrieve_knowledge(
        self,
        plugin_author: str,
        plugin_name: str,
        retriever_name: str,
        retrieval_context: dict[str, Any],
    ) -> dict[str, Any]:
        """Retrieve knowledge using a KnowledgeEngine instance."""
        if not self.is_enable_plugin:
            return {'results': []}

        return await self.handler.retrieve_knowledge(plugin_author, plugin_name, retriever_name, retrieval_context)

    def dispose(self):
        # On non-Windows stdio mode, terminate via the controller's process handle.
        # On Windows, the managed subprocess is cleaned up by the base class.
        if (
            self.is_enable_plugin
            and hasattr(self, 'ctrl')
            and isinstance(self.ctrl, stdio_client_controller.StdioClientController)
        ):
            self.ap.logger.info('Terminating plugin runtime process...')
            self.ctrl.process.terminate()

        self._dispose_subprocess()

        if self.heartbeat_task is not None:
            self.heartbeat_task.cancel()
            self.heartbeat_task = None

    @staticmethod
    def _parse_plugin_id(plugin_id: str) -> tuple[str, str]:
        """Parse a plugin ID string into (author, name).

        Args:
            plugin_id: Plugin ID in 'author/name' format.

        Returns:
            Tuple of (plugin_author, plugin_name).

        Raises:
            ValueError: If plugin_id is not in the expected 'author/name' format.
        """
        if '/' not in plugin_id:
            raise ValueError(
                f"Invalid plugin_id format: '{plugin_id}'. Expected 'author/name' format (e.g. 'langbot/rag-engine')."
            )
        return plugin_id.split('/', 1)

    async def call_rag_ingest(self, plugin_id: str, context_data: dict[str, Any]) -> dict[str, Any]:
        """Call plugin to ingest document.

        Args:
            plugin_id: Target plugin ID (author/name).
            context_data: IngestionContext data.
        """
        plugin_author, plugin_name = self._parse_plugin_id(plugin_id)
        return await self.handler.rag_ingest_document(plugin_author, plugin_name, context_data)

    async def call_rag_delete_document(self, plugin_id: str, document_id: str, kb_id: str) -> bool:
        plugin_author, plugin_name = self._parse_plugin_id(plugin_id)
        return await self.handler.rag_delete_document(plugin_author, plugin_name, document_id, kb_id)

    async def get_rag_creation_schema(self, plugin_id: str) -> dict[str, Any]:
        plugin_author, plugin_name = self._parse_plugin_id(plugin_id)
        return await self.handler.get_rag_creation_schema(plugin_author, plugin_name)

    async def get_rag_retrieval_schema(self, plugin_id: str) -> dict[str, Any]:
        plugin_author, plugin_name = self._parse_plugin_id(plugin_id)
        return await self.handler.get_rag_retrieval_schema(plugin_author, plugin_name)

    async def rag_on_kb_create(self, plugin_id: str, kb_id: str, config: dict[str, Any]) -> dict[str, Any]:
        """Notify plugin about KB creation."""
        plugin_author, plugin_name = self._parse_plugin_id(plugin_id)
        return await self.handler.rag_on_kb_create(plugin_author, plugin_name, kb_id, config)

    async def rag_on_kb_delete(self, plugin_id: str, kb_id: str) -> dict[str, Any]:
        """Notify plugin about KB deletion."""
        plugin_author, plugin_name = self._parse_plugin_id(plugin_id)
        return await self.handler.rag_on_kb_delete(plugin_author, plugin_name, kb_id)

    async def call_rag_retrieve(self, plugin_id: str, retrieval_context: dict[str, Any]) -> dict[str, Any]:
        """Call plugin to retrieve knowledge.

        Args:
            plugin_id: Target plugin ID (author/name).
            retrieval_context: RetrievalContext data.
        """
        plugin_author, plugin_name = self._parse_plugin_id(plugin_id)
        return await self.handler.retrieve_knowledge(plugin_author, plugin_name, '', retrieval_context)

    async def list_knowledge_engines(self) -> list[dict[str, Any]]:
        """List all available Knowledge Engines from plugins.

        Returns a list of Knowledge Engines with their capabilities and configuration schemas.
        """
        if not self.is_enable_plugin:
            return []

        return await self.handler.list_knowledge_engines()

    async def list_parsers(self) -> list[dict[str, Any]]:
        """List all available parsers from plugins."""
        if not self.is_enable_plugin:
            return []
        return await self.handler.list_parsers()

    async def call_parser(self, plugin_id: str, context_data: dict[str, Any], file_bytes: bytes) -> dict[str, Any]:
        """Call plugin to parse a document."""
        plugin_author, plugin_name = self._parse_plugin_id(plugin_id)
        return await self.handler.parse_document(plugin_author, plugin_name, context_data, file_bytes)
