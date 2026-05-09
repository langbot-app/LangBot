"""
Unit tests for MCPService.

Tests MCP server CRUD operations including:
- MCP server listing with runtime info
- MCP server creation with limitations
- MCP server update with enable/disable
- MCP server deletion
- MCP server connection testing

Source: src/langbot/pkg/api/http/service/mcp.py
"""

from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, Mock, MagicMock
from types import SimpleNamespace
import uuid

from langbot.pkg.api.http.service.mcp import MCPService
from langbot.pkg.entity.persistence.mcp import MCPServer


pytestmark = pytest.mark.asyncio


def _create_mock_mcp_server(
    server_uuid: str = None,
    name: str = 'Test MCP Server',
    enable: bool = True,
    mode: str = 'stdio',
    extra_args: dict = None,
) -> Mock:
    """Helper to create mock MCPServer entity."""
    server = Mock(spec=MCPServer)
    server.uuid = server_uuid or str(uuid.uuid4())
    server.name = name
    server.enable = enable
    server.mode = mode
    server.extra_args = extra_args or {}
    return server


def _create_mock_result(items: list = None, first_item=None):
    """Create mock result object for persistence queries."""
    result = Mock()
    result.all = Mock(return_value=items or [])
    result.first = Mock(return_value=first_item)
    return result


class TestMCPServiceGetRuntimeInfo:
    """Tests for get_runtime_info method."""

    async def test_get_runtime_info_session_exists(self):
        """Returns runtime info when session exists."""
        # Setup
        ap = SimpleNamespace()
        ap.tool_mgr = SimpleNamespace()
        ap.tool_mgr.mcp_tool_loader = SimpleNamespace()

        mock_session = SimpleNamespace()
        mock_session.get_runtime_info_dict = Mock(return_value={'status': 'running', 'tools': 5})
        ap.tool_mgr.mcp_tool_loader.get_session = Mock(return_value=mock_session)

        service = MCPService(ap)

        # Execute
        result = await service.get_runtime_info('test-server')

        # Verify
        assert result is not None
        assert result['status'] == 'running'

    async def test_get_runtime_info_session_not_exists(self):
        """Returns None when session not exists."""
        # Setup
        ap = SimpleNamespace()
        ap.tool_mgr = SimpleNamespace()
        ap.tool_mgr.mcp_tool_loader = SimpleNamespace()
        ap.tool_mgr.mcp_tool_loader.get_session = Mock(return_value=None)

        service = MCPService(ap)

        # Execute
        result = await service.get_runtime_info('nonexistent-server')

        # Verify
        assert result is None


class TestMCPServiceGetMCPServers:
    """Tests for get_mcp_servers method."""

    async def test_get_mcp_servers_empty_list(self):
        """Returns empty list when no MCP servers exist."""
        # Setup
        ap = SimpleNamespace()
        ap.persistence_mgr = SimpleNamespace()
        mock_result = _create_mock_result([])
        ap.persistence_mgr.execute_async = AsyncMock(return_value=mock_result)
        ap.persistence_mgr.serialize_model = Mock(
            side_effect=lambda model_cls, entity: {
                'uuid': entity.uuid,
                'name': entity.name,
            }
        )
        ap.tool_mgr = None

        service = MCPService(ap)

        # Execute
        result = await service.get_mcp_servers()

        # Verify
        assert result == []

    async def test_get_mcp_servers_returns_serialized_list(self):
        """Returns serialized list of MCP servers."""
        # Setup
        ap = SimpleNamespace()
        ap.persistence_mgr = SimpleNamespace()

        server1 = _create_mock_mcp_server(server_uuid='uuid-1', name='Server 1')
        server2 = _create_mock_mcp_server(server_uuid='uuid-2', name='Server 2')

        mock_result = _create_mock_result([server1, server2])
        ap.persistence_mgr.execute_async = AsyncMock(return_value=mock_result)
        ap.persistence_mgr.serialize_model = Mock(
            side_effect=lambda model_cls, entity: {
                'uuid': entity.uuid,
                'name': entity.name,
                'enable': entity.enable,
                'mode': entity.mode,
            }
        )
        ap.tool_mgr = None

        service = MCPService(ap)

        # Execute
        result = await service.get_mcp_servers()

        # Verify
        assert len(result) == 2
        assert result[0]['name'] == 'Server 1'
        assert result[1]['name'] == 'Server 2'

    async def test_get_mcp_servers_with_runtime_info(self):
        """Returns MCP servers with runtime info when requested."""
        # Setup
        ap = SimpleNamespace()
        ap.persistence_mgr = SimpleNamespace()

        server1 = _create_mock_mcp_server(server_uuid='uuid-1', name='Server 1')

        mock_result = _create_mock_result([server1])
        ap.persistence_mgr.execute_async = AsyncMock(return_value=mock_result)
        ap.persistence_mgr.serialize_model = Mock(
            side_effect=lambda model_cls, entity: {
                'uuid': entity.uuid,
                'name': entity.name,
            }
        )
        ap.tool_mgr = SimpleNamespace()
        ap.tool_mgr.mcp_tool_loader = SimpleNamespace()
        ap.tool_mgr.mcp_tool_loader.get_session = Mock(return_value=None)

        service = MCPService(ap)
        service.get_runtime_info = AsyncMock(return_value={'status': 'connected'})

        # Execute
        result = await service.get_mcp_servers(contain_runtime_info=True)

        # Verify - runtime info included
        assert result[0]['runtime_info'] == {'status': 'connected'}


class TestMCPServiceCreateMCPServer:
    """Tests for create_mcp_server method."""

    async def test_create_mcp_server_max_extensions_reached_raises(self):
        """Raises ValueError when max_extensions limit reached."""
        # Setup
        ap = SimpleNamespace()
        ap.persistence_mgr = SimpleNamespace()
        ap.instance_config = SimpleNamespace()
        ap.instance_config.data = {
            'system': {
                'limitation': {
                    'max_extensions': 2
                }
            }
        }
        ap.plugin_connector = SimpleNamespace()
        ap.plugin_connector.list_plugins = AsyncMock(return_value=[Mock(), Mock()])  # 2 plugins

        # Mock get_mcp_servers to return 0 servers (2 plugins already)
        mock_result = _create_mock_result([])
        ap.persistence_mgr.execute_async = AsyncMock(return_value=mock_result)
        ap.persistence_mgr.serialize_model = Mock(return_value={})
        ap.tool_mgr = None

        service = MCPService(ap)

        # Execute & Verify - 2 plugins + new server would exceed limit
        with pytest.raises(ValueError, match='Maximum number of extensions'):
            await service.create_mcp_server({'name': 'New Server'})

    async def test_create_mcp_server_no_limit(self):
        """Creates MCP server without limit when max_extensions=-1."""
        # Setup
        ap = SimpleNamespace()
        ap.persistence_mgr = SimpleNamespace()
        ap.instance_config = SimpleNamespace()
        ap.instance_config.data = {
            'system': {
                'limitation': {
                    'max_extensions': -1  # No limit
                }
            }
        }
        ap.tool_mgr = None

        mock_result = _create_mock_result([])
        ap.persistence_mgr.execute_async = AsyncMock(return_value=mock_result)
        ap.persistence_mgr.serialize_model = Mock(return_value={'uuid': 'new-uuid'})

        service = MCPService(ap)

        # Execute
        server_uuid = await service.create_mcp_server({'name': 'New Server'})

        # Verify
        assert server_uuid is not None
        assert len(server_uuid) == 36  # UUID format

    async def test_create_mcp_server_loads_server(self):
        """Loads server into tool_mgr when enabled."""
        # Setup
        ap = SimpleNamespace()
        ap.persistence_mgr = SimpleNamespace()
        ap.instance_config = SimpleNamespace()
        ap.instance_config.data = {'system': {'limitation': {'max_extensions': -1}}}
        ap.tool_mgr = SimpleNamespace()
        ap.tool_mgr.mcp_tool_loader = SimpleNamespace()
        ap.tool_mgr.mcp_tool_loader.host_mcp_server = AsyncMock()
        ap.tool_mgr.mcp_tool_loader._hosted_mcp_tasks = []

        # Create mock server entity
        server_entity = _create_mock_mcp_server(server_uuid='new-uuid', enable=True)

        call_count = 0
        async def mock_execute(query):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return _create_mock_result([])  # Empty list for limit check
            elif call_count == 2:
                return Mock()  # Insert
            return _create_mock_result(first_item=server_entity)  # Select created

        ap.persistence_mgr.execute_async = AsyncMock(side_effect=mock_execute)
        ap.persistence_mgr.serialize_model = Mock(
            return_value={'uuid': 'new-uuid', 'name': 'New Server', 'enable': True}
        )

        service = MCPService(ap)

        # Execute
        await service.create_mcp_server({'name': 'New Server', 'enable': True})

        # Verify - host_mcp_server was called
        ap.tool_mgr.mcp_tool_loader.host_mcp_server.assert_called_once()

    async def test_create_mcp_server_disabled_no_load(self):
        """Does not load server when disabled."""
        # Setup
        ap = SimpleNamespace()
        ap.persistence_mgr = SimpleNamespace()
        ap.instance_config = SimpleNamespace()
        ap.instance_config.data = {'system': {'limitation': {'max_extensions': -1}}}
        ap.tool_mgr = None

        mock_result = _create_mock_result([])
        ap.persistence_mgr.execute_async = AsyncMock(return_value=mock_result)
        ap.persistence_mgr.serialize_model = Mock(return_value={'uuid': 'new-uuid'})

        service = MCPService(ap)

        # Execute with enable=False
        server_uuid = await service.create_mcp_server({'name': 'New Server', 'enable': False})

        # Verify - no tool_mgr load attempt
        assert server_uuid is not None


class TestMCPServiceGetMCPServerByName:
    """Tests for get_mcp_server_by_name method."""

    async def test_get_mcp_server_by_name_found(self):
        """Returns MCP server when found by name."""
        # Setup
        ap = SimpleNamespace()
        ap.persistence_mgr = SimpleNamespace()

        server = _create_mock_mcp_server(name='Found Server')
        mock_result = _create_mock_result(first_item=server)
        ap.persistence_mgr.execute_async = AsyncMock(return_value=mock_result)
        ap.persistence_mgr.serialize_model = Mock(
            return_value={
                'uuid': 'test-uuid',
                'name': 'Found Server',
                'runtime_info': None,
            }
        )
        ap.tool_mgr = None

        service = MCPService(ap)
        service.get_runtime_info = AsyncMock(return_value=None)

        # Execute
        result = await service.get_mcp_server_by_name('Found Server')

        # Verify
        assert result is not None
        assert result['name'] == 'Found Server'

    async def test_get_mcp_server_by_name_not_found(self):
        """Returns None when MCP server not found."""
        # Setup
        ap = SimpleNamespace()
        ap.persistence_mgr = SimpleNamespace()

        mock_result = _create_mock_result(first_item=None)
        ap.persistence_mgr.execute_async = AsyncMock(return_value=mock_result)

        service = MCPService(ap)

        # Execute
        result = await service.get_mcp_server_by_name('Nonexistent Server')

        # Verify
        assert result is None


class TestMCPServiceUpdateMCPServer:
    """Tests for update_mcp_server method."""

    async def test_update_mcp_server_disable_enabled_server(self):
        """Removes server when disabling previously enabled server."""
        # Setup
        ap = SimpleNamespace()
        ap.persistence_mgr = SimpleNamespace()
        ap.tool_mgr = SimpleNamespace()
        ap.tool_mgr.mcp_tool_loader = SimpleNamespace()
        ap.tool_mgr.mcp_tool_loader.sessions = {'Old Server': Mock()}
        ap.tool_mgr.mcp_tool_loader.remove_mcp_server = AsyncMock()

        old_server = _create_mock_mcp_server(name='Old Server', enable=True)

        call_count = 0
        async def mock_execute(query):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return _create_mock_result(first_item=old_server)
            return Mock()  # Update

        ap.persistence_mgr.execute_async = AsyncMock(side_effect=mock_execute)

        service = MCPService(ap)

        # Execute - disable server
        await service.update_mcp_server('test-uuid', {'enable': False})

        # Verify - server was removed
        ap.tool_mgr.mcp_tool_loader.remove_mcp_server.assert_called_once()

    async def test_update_mcp_server_enable_disabled_server(self):
        """Loads server when enabling previously disabled server."""
        # Setup
        ap = SimpleNamespace()
        ap.persistence_mgr = SimpleNamespace()
        ap.tool_mgr = SimpleNamespace()
        ap.tool_mgr.mcp_tool_loader = SimpleNamespace()
        ap.tool_mgr.mcp_tool_loader.sessions = {}
        ap.tool_mgr.mcp_tool_loader.host_mcp_server = AsyncMock()
        ap.tool_mgr.mcp_tool_loader._hosted_mcp_tasks = []

        old_server = _create_mock_mcp_server(name='Old Server', enable=False)

        updated_server = _create_mock_mcp_server(name='Old Server', enable=True)

        call_count = 0
        async def mock_execute(query):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return _create_mock_result(first_item=old_server)
            elif call_count == 2:
                return Mock()  # Update
            return _create_mock_result(first_item=updated_server)  # Select updated

        ap.persistence_mgr.execute_async = AsyncMock(side_effect=mock_execute)
        ap.persistence_mgr.serialize_model = Mock(
            return_value={'uuid': 'test-uuid', 'name': 'Old Server', 'enable': True}
        )

        service = MCPService(ap)

        # Execute - enable server
        await service.update_mcp_server('test-uuid', {'enable': True})

        # Verify - server was loaded
        ap.tool_mgr.mcp_tool_loader.host_mcp_server.assert_called_once()

    async def test_update_mcp_server_update_enabled_server(self):
        """Removes and reloads server when updating enabled server."""
        # Setup
        ap = SimpleNamespace()
        ap.persistence_mgr = SimpleNamespace()
        ap.tool_mgr = SimpleNamespace()
        ap.tool_mgr.mcp_tool_loader = SimpleNamespace()
        ap.tool_mgr.mcp_tool_loader.sessions = {'Old Server': Mock()}
        ap.tool_mgr.mcp_tool_loader.remove_mcp_server = AsyncMock()
        ap.tool_mgr.mcp_tool_loader.host_mcp_server = AsyncMock()
        ap.tool_mgr.mcp_tool_loader._hosted_mcp_tasks = []

        old_server = _create_mock_mcp_server(name='Old Server', enable=True)

        # Mock for: first select -> update -> second select (for updated server)
        call_count = 0
        async def mock_execute(query):
            nonlocal call_count
            call_count += 1
            # All selects return the server
            return _create_mock_result(first_item=old_server)

        ap.persistence_mgr.execute_async = AsyncMock(side_effect=mock_execute)
        ap.persistence_mgr.serialize_model = Mock(
            return_value={'uuid': 'test-uuid', 'name': 'Old Server', 'enable': True}
        )

        service = MCPService(ap)

        # Execute - update enabled server (keep enabled, update extra_args)
        await service.update_mcp_server('test-uuid', {'enable': True, 'extra_args': {'new': 'args'}})

        # Verify - remove and reload
        ap.tool_mgr.mcp_tool_loader.remove_mcp_server.assert_called_once_with('Old Server')
        ap.tool_mgr.mcp_tool_loader.host_mcp_server.assert_called_once()

    async def test_update_mcp_server_no_tool_mgr(self):
        """Updates persistence without tool_mgr operations."""
        # Setup
        ap = SimpleNamespace()
        ap.persistence_mgr = SimpleNamespace()
        # Set mcp_tool_loader to None, not tool_mgr itself
        ap.tool_mgr = SimpleNamespace()
        ap.tool_mgr.mcp_tool_loader = None

        old_server = _create_mock_mcp_server(name='Server', enable=True)

        # Mock execute for select and update
        call_count = 0
        async def mock_execute(query):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return _create_mock_result(first_item=old_server)
            return Mock()  # Update

        ap.persistence_mgr.execute_async = AsyncMock(side_effect=mock_execute)

        service = MCPService(ap)

        # Execute - should not raise
        await service.update_mcp_server('test-uuid', {'name': 'New Name'})

        # Verify - persistence was called
        assert ap.persistence_mgr.execute_async.call_count >= 2


class TestMCPServiceDeleteMCPServer:
    """Tests for delete_mcp_server method."""

    async def test_delete_mcp_server_calls_remove_and_delete(self):
        """Calls both persistence delete and tool_mgr remove."""
        # Setup
        ap = SimpleNamespace()
        ap.persistence_mgr = SimpleNamespace()
        ap.tool_mgr = SimpleNamespace()
        ap.tool_mgr.mcp_tool_loader = SimpleNamespace()
        ap.tool_mgr.mcp_tool_loader.sessions = {'Server to Delete': Mock()}
        ap.tool_mgr.mcp_tool_loader.remove_mcp_server = AsyncMock()

        server = _create_mock_mcp_server(name='Server to Delete')

        call_count = 0
        async def mock_execute(query):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return _create_mock_result(first_item=server)
            return Mock()  # Delete

        ap.persistence_mgr.execute_async = AsyncMock(side_effect=mock_execute)

        service = MCPService(ap)

        # Execute
        await service.delete_mcp_server('test-uuid')

        # Verify
        ap.tool_mgr.mcp_tool_loader.remove_mcp_server.assert_called_once_with('Server to Delete')
        ap.persistence_mgr.execute_async.assert_called()

    async def test_delete_mcp_server_not_in_sessions(self):
        """Does not attempt remove if server not in sessions."""
        # Setup
        ap = SimpleNamespace()
        ap.persistence_mgr = SimpleNamespace()
        ap.tool_mgr = SimpleNamespace()
        ap.tool_mgr.mcp_tool_loader = SimpleNamespace()
        ap.tool_mgr.mcp_tool_loader.sessions = {}  # Server not in sessions
        ap.tool_mgr.mcp_tool_loader.remove_mcp_server = AsyncMock()

        server = _create_mock_mcp_server(name='Not in Sessions')

        call_count = 0
        async def mock_execute(query):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return _create_mock_result(first_item=server)
            return Mock()

        ap.persistence_mgr.execute_async = AsyncMock(side_effect=mock_execute)

        service = MCPService(ap)

        # Execute
        await service.delete_mcp_server('test-uuid')

        # Verify - remove not called (server not in sessions)
        ap.tool_mgr.mcp_tool_loader.remove_mcp_server.assert_not_called()

    async def test_delete_mcp_server_nonexistent_uuid(self):
        """Delete operation completes even for nonexistent UUID."""
        # Setup
        ap = SimpleNamespace()
        ap.persistence_mgr = SimpleNamespace()
        ap.tool_mgr = SimpleNamespace()
        ap.tool_mgr.mcp_tool_loader = SimpleNamespace()
        ap.tool_mgr.mcp_tool_loader.sessions = {}
        ap.tool_mgr.mcp_tool_loader.remove_mcp_server = AsyncMock()

        # No server found
        call_count = 0
        async def mock_execute(query):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return _create_mock_result(first_item=None)
            return Mock()

        ap.persistence_mgr.execute_async = AsyncMock(side_effect=mock_execute)

        service = MCPService(ap)

        # Execute - should not raise
        await service.delete_mcp_server('nonexistent-uuid')

        # Verify - delete was called regardless
        ap.persistence_mgr.execute_async.assert_called()


class TestMCPServiceTestMCPServer:
    """Tests for test_mcp_server method."""

    async def test_test_mcp_server_existing_server(self):
        """Tests existing MCP server connection."""
        # Setup
        ap = SimpleNamespace()
        ap.tool_mgr = SimpleNamespace()
        ap.tool_mgr.mcp_tool_loader = SimpleNamespace()

        from langbot.pkg.provider.tools.loaders.mcp import MCPSessionStatus

        mock_session = MagicMock()
        mock_session.status = MCPSessionStatus.ERROR
        mock_session.start = AsyncMock()
        mock_session.refresh = AsyncMock()
        ap.tool_mgr.mcp_tool_loader.get_session = Mock(return_value=mock_session)

        ap.task_mgr = SimpleNamespace()
        ap.task_mgr.create_user_task = Mock(
            return_value=SimpleNamespace(id=123)
        )

        service = MCPService(ap)

        # Execute
        task_id = await service.test_mcp_server('existing-server', {})

        # Verify - returns task ID
        assert task_id == 123

    async def test_test_mcp_server_not_found_raises(self):
        """Raises ValueError when server not found."""
        # Setup
        ap = SimpleNamespace()
        ap.tool_mgr = SimpleNamespace()
        ap.tool_mgr.mcp_tool_loader = SimpleNamespace()
        ap.tool_mgr.mcp_tool_loader.get_session = Mock(return_value=None)

        service = MCPService(ap)

        # Execute & Verify
        with pytest.raises(ValueError, match='Server not found'):
            await service.test_mcp_server('nonexistent-server', {})

    async def test_test_mcp_server_new_server(self):
        """Tests new MCP server with underscore name."""
        # Setup
        ap = SimpleNamespace()
        ap.tool_mgr = SimpleNamespace()
        ap.tool_mgr.mcp_tool_loader = SimpleNamespace()

        mock_session = MagicMock()
        mock_session.start = AsyncMock()
        ap.tool_mgr.mcp_tool_loader.load_mcp_server = AsyncMock(return_value=mock_session)

        ap.task_mgr = SimpleNamespace()
        ap.task_mgr.create_user_task = Mock(
            return_value=SimpleNamespace(id=456)
        )

        service = MCPService(ap)

        # Execute with '_' name (new server)
        task_id = await service.test_mcp_server('_', {'name': 'New Server'})

        # Verify - load_mcp_server called
        ap.tool_mgr.mcp_tool_loader.load_mcp_server.assert_called_once()
        assert task_id == 456