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

    async def test_mcp_server(self, server_name: str, server_data: dict) -> int:
        """测试 MCP 服务器连接并返回任务 ID"""

        runtime_mcp_session: RuntimeMCPSession | None = None

        if server_name != '_':
            runtime_mcp_session = self.ap.tool_mgr.mcp_tool_loader.get_session(server_name)
            if runtime_mcp_session is None:
                raise ValueError(f'Server not found: {server_name}')

            if runtime_mcp_session.status == MCPSessionStatus.ERROR:
                coroutine = runtime_mcp_session.start()
            else:
                coroutine = runtime_mcp_session.refresh()
        else:
            runtime_mcp_session = await self.ap.tool_mgr.mcp_tool_loader.load_mcp_server(server_config=server_data)
            coroutine = runtime_mcp_session.start()

        ctx = taskmgr.TaskContext.new()
        wrapper = self.ap.task_mgr.create_user_task(
            coroutine,
            kind='mcp-operation',
            name=f'mcp-test-{server_name}',
            label=f'Testing MCP server {server_name}',
            context=ctx,
        )
        return wrapper.id
