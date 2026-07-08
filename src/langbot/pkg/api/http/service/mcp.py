from __future__ import annotations

import sqlalchemy
import uuid
import asyncio

from ....core import app
from ....entity.persistence import mcp as persistence_mcp
from ....core import taskmgr
from ....provider.tools.loaders.mcp import RuntimeMCPSession, MCPSessionStatus


class MCPService:
    ap: app.Application

    def __init__(self, ap: app.Application) -> None:
        self.ap = ap

    async def get_runtime_info(self, server_name: str) -> dict | None:
        session = self.ap.tool_mgr.mcp_tool_loader.get_session(server_name)
        if session:
            return session.get_runtime_info_dict()
        return None

    async def get_mcp_servers(self, contain_runtime_info: bool = False) -> list[dict]:
        result = await self.ap.persistence_mgr.execute_async(sqlalchemy.select(persistence_mcp.MCPServer))

        servers = result.all()
        serialized_servers = [
            self.ap.persistence_mgr.serialize_model(persistence_mcp.MCPServer, server) for server in servers
        ]
        if contain_runtime_info:
            for server in serialized_servers:
                runtime_info = await self.get_runtime_info(server['name'])

                server['runtime_info'] = runtime_info if runtime_info else None

        return serialized_servers

    async def create_mcp_server(self, server_data: dict) -> str:
        # Check limitation (extensions = MCP servers + plugins)
        limitation = self.ap.instance_config.data.get('system', {}).get('limitation', {})
        max_extensions = limitation.get('max_extensions', -1)
        if max_extensions >= 0:
            existing_mcp_servers = await self.get_mcp_servers()
            plugins = await self.ap.plugin_connector.list_plugins()
            total_extensions = len(existing_mcp_servers) + len(plugins)
            if total_extensions >= max_extensions:
                raise ValueError(f'Maximum number of extensions ({max_extensions}) reached')

        server_name = str(server_data.get('name') or '').strip()
        if not server_name:
            raise ValueError('MCP server name is required')
        server_data['name'] = server_name

        existing_result = await self.ap.persistence_mgr.execute_async(
            sqlalchemy.select(persistence_mcp.MCPServer).where(persistence_mcp.MCPServer.name == server_name)
        )
        if existing_result.first() is not None:
            raise ValueError(f'MCP server already exists: {server_name}')

        server_data['uuid'] = str(uuid.uuid4())
        await self.ap.persistence_mgr.execute_async(sqlalchemy.insert(persistence_mcp.MCPServer).values(server_data))

        result = await self.ap.persistence_mgr.execute_async(
            sqlalchemy.select(persistence_mcp.MCPServer).where(persistence_mcp.MCPServer.uuid == server_data['uuid'])
        )
        server_entity = result.first()
        if server_entity:
            server_config = self.ap.persistence_mgr.serialize_model(persistence_mcp.MCPServer, server_entity)
            if self.ap.tool_mgr.mcp_tool_loader:
                task = asyncio.create_task(self.ap.tool_mgr.mcp_tool_loader.host_mcp_server(server_config))
                self.ap.tool_mgr.mcp_tool_loader._hosted_mcp_tasks.append(task)

        return server_data['uuid']

    async def get_mcp_server_by_name(self, server_name: str) -> dict | None:
        result = await self.ap.persistence_mgr.execute_async(
            sqlalchemy.select(persistence_mcp.MCPServer).where(persistence_mcp.MCPServer.name == server_name)
        )
        server = result.first()
        if server is None:
            return None

        runtime_info = await self.get_runtime_info(server.name)
        server_data = self.ap.persistence_mgr.serialize_model(persistence_mcp.MCPServer, server)
        server_data['runtime_info'] = runtime_info if runtime_info else None
        return server_data

    async def update_mcp_server(self, server_uuid: str, server_data: dict) -> None:
        result = await self.ap.persistence_mgr.execute_async(
            sqlalchemy.select(persistence_mcp.MCPServer).where(persistence_mcp.MCPServer.uuid == server_uuid)
        )
        old_server = result.first()
        old_server_name = old_server.name if old_server else None
        old_enable = old_server.enable if old_server else False

        await self.ap.persistence_mgr.execute_async(
            sqlalchemy.update(persistence_mcp.MCPServer)
            .where(persistence_mcp.MCPServer.uuid == server_uuid)
            .values(server_data)
        )

        if self.ap.tool_mgr.mcp_tool_loader:
            new_enable = server_data.get('enable', False)

            need_remove = old_server_name and old_server_name in self.ap.tool_mgr.mcp_tool_loader.sessions

            if old_enable and not new_enable:
                if need_remove:
                    await self.ap.tool_mgr.mcp_tool_loader.remove_mcp_server(old_server_name)

            elif not old_enable and new_enable:
                result = await self.ap.persistence_mgr.execute_async(
                    sqlalchemy.select(persistence_mcp.MCPServer).where(persistence_mcp.MCPServer.uuid == server_uuid)
                )
                updated_server = result.first()
                if updated_server:
                    server_config = self.ap.persistence_mgr.serialize_model(persistence_mcp.MCPServer, updated_server)
                    task = asyncio.create_task(self.ap.tool_mgr.mcp_tool_loader.host_mcp_server(server_config))
                    self.ap.tool_mgr.mcp_tool_loader._hosted_mcp_tasks.append(task)

            elif old_enable and new_enable:
                if need_remove:
                    await self.ap.tool_mgr.mcp_tool_loader.remove_mcp_server(old_server_name)
                result = await self.ap.persistence_mgr.execute_async(
                    sqlalchemy.select(persistence_mcp.MCPServer).where(persistence_mcp.MCPServer.uuid == server_uuid)
                )
                updated_server = result.first()
                if updated_server:
                    server_config = self.ap.persistence_mgr.serialize_model(persistence_mcp.MCPServer, updated_server)
                    task = asyncio.create_task(self.ap.tool_mgr.mcp_tool_loader.host_mcp_server(server_config))
                    self.ap.tool_mgr.mcp_tool_loader._hosted_mcp_tasks.append(task)

    async def delete_mcp_server(self, server_uuid: str) -> None:
        result = await self.ap.persistence_mgr.execute_async(
            sqlalchemy.select(persistence_mcp.MCPServer).where(persistence_mcp.MCPServer.uuid == server_uuid)
        )
        server = result.first()
        server_name = server.name if server else None

        await self.ap.persistence_mgr.execute_async(
            sqlalchemy.delete(persistence_mcp.MCPServer).where(persistence_mcp.MCPServer.uuid == server_uuid)
        )

        if server_name and self.ap.tool_mgr.mcp_tool_loader:
            if server_name in self.ap.tool_mgr.mcp_tool_loader.sessions:
                await self.ap.tool_mgr.mcp_tool_loader.remove_mcp_server(server_name)

    async def get_mcp_server_resources(self, server_name: str) -> list[dict]:
        """Get resources from a specific MCP server."""
        return await self.ap.tool_mgr.mcp_tool_loader.get_resources(server_name)

    async def get_mcp_server_resource_templates(self, server_name: str) -> list[dict]:
        """Get resource templates from a specific MCP server."""
        return await self.ap.tool_mgr.mcp_tool_loader.get_resource_templates(server_name)

    async def read_mcp_server_resource_envelope(
        self,
        server_name: str,
        uri: str,
        *,
        max_bytes: int | None = None,
        include_blob: bool = False,
    ) -> dict:
        """Read a resource from a specific MCP server with metadata."""
        kwargs = {'include_blob': include_blob, 'source': 'ui_preview'}
        if max_bytes is not None:
            kwargs['max_bytes'] = max_bytes
        return await self.ap.tool_mgr.mcp_tool_loader.read_resource_envelope(server_name, uri, **kwargs)

    async def read_mcp_server_resource(self, server_name: str, uri: str) -> list[dict]:
        """Read a resource from a specific MCP server."""
        return await self.ap.tool_mgr.mcp_tool_loader.read_resource(server_name, uri)

    async def test_mcp_server(self, server_name: str, server_data: dict) -> int:
        """测试 MCP 服务器连接并返回任务 ID"""

        runtime_mcp_session: RuntimeMCPSession | None = None

        ctx = taskmgr.TaskContext.new()

        if server_name != '_':
            runtime_mcp_session = self.ap.tool_mgr.mcp_tool_loader.get_session(server_name)
            if runtime_mcp_session is None:
                raise ValueError(f'Server not found: {server_name}')

            persisted_session = runtime_mcp_session

            async def _refresh_and_report() -> None:
                # Testing a persisted server should REUSE its live shared-session
                # process, not rebuild it. Try a lightweight refresh (a real
                # list_tools probe over the existing connection) first; only fall
                # back to a full start() when the session has no live connection
                # to probe (never connected, or the process is actually gone).
                needs_start = persisted_session.status == MCPSessionStatus.ERROR or persisted_session.session is None
                if needs_start:
                    await persisted_session.start()
                else:
                    try:
                        await persisted_session.refresh()
                    except Exception:
                        # The live connection was stale/dropped: reconnect once
                        # (reusing the live managed process where possible) and
                        # re-probe, instead of reporting a false failure.
                        await persisted_session.start()
                # Surface the discovered tools so the config page can render them
                # even for an already-hosted server.
                ctx.metadata['runtime_info'] = persisted_session.get_runtime_info_dict()

            coroutine = _refresh_and_report()
        else:
            runtime_mcp_session = await self.ap.tool_mgr.mcp_tool_loader.load_mcp_server(server_config=server_data)

            # A transient test owns an isolated Box session. Always tear it down
            # after the test completes (success or failure) so it does not leak.
            test_session = runtime_mcp_session

            async def _run_and_cleanup() -> None:
                try:
                    await test_session.start()
                    # Capture the runtime info (status + discovered tools) BEFORE
                    # shutting the transient session down. The create/edit config
                    # page has no persisted server to reload from, so without this
                    # a successful test could only show "no tools found". The
                    # frontend reads ctx.metadata.runtime_info to render the tools.
                    ctx.metadata['runtime_info'] = test_session.get_runtime_info_dict()
                finally:
                    try:
                        await test_session.shutdown()
                    except Exception as exc:
                        self.ap.logger.warning(
                            f'Failed to tear down transient MCP test session '
                            f'{test_session.server_name}: {type(exc).__name__}: {exc}'
                        )

            coroutine = _run_and_cleanup()

        wrapper = self.ap.task_mgr.create_user_task(
            coroutine,
            kind='mcp-operation',
            name=f'mcp-test-{server_name}',
            label=f'Testing MCP server {server_name}',
            context=ctx,
        )
        return wrapper.id

    async def get_mcp_server_logs(self, server_name: str, limit: int = 200, level: str | None = None) -> list[dict]:
        """Get recent log lines captured from the MCP server's stderr."""
        session = self.ap.tool_mgr.mcp_tool_loader.get_session(server_name)
        if not session:
            return []

        # Get logs from the session's buffer
        logs = list(session._log_buffer)

        # Filter by level if specified
        if level:
            logs = [log for log in logs if log.get('level') == level]

        # Return the most recent 'limit' logs
        return logs[-limit:]
