from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from langbot.pkg.provider.tools.loaders.mcp_policy import (
    MCPStdioDisabledError,
    require_stdio_mcp_enabled,
    stdio_mcp_enabled,
)
from langbot.pkg.provider.tools.loaders.mcp import MCPLoader


def _app(config: dict) -> SimpleNamespace:
    return SimpleNamespace(instance_config=SimpleNamespace(data=config))


def test_oss_default_remains_enabled_when_key_is_absent():
    assert stdio_mcp_enabled(_app({})) is True


@pytest.mark.parametrize(
    'value',
    [False, 'false', 0, None, {}, []],
)
def test_disabled_or_invalid_values_fail_closed(value):
    ap = _app({'mcp': {'stdio': {'enabled': value}}})

    assert stdio_mcp_enabled(ap) is False
    with pytest.raises(MCPStdioDisabledError, match='disabled by instance policy'):
        require_stdio_mcp_enabled(ap, {'mode': 'stdio'})


def test_remote_transport_is_independent_of_stdio_gate():
    ap = _app({'mcp': {'stdio': {'enabled': False}}})

    require_stdio_mcp_enabled(ap, {'mode': 'remote'})


@pytest.mark.asyncio
async def test_bootstrap_retains_but_does_not_launch_disabled_stdio_rows():
    server = SimpleNamespace(uuid='server-a', workspace_uuid='workspace-a')
    result = Mock()
    result.all.return_value = [server]
    ap = _app({'mcp': {'stdio': {'enabled': False}}})
    ap.logger = Mock()
    ap.persistence_mgr = SimpleNamespace(
        execute_async=AsyncMock(return_value=result),
        serialize_model=Mock(
            return_value={
                'uuid': 'server-a',
                'workspace_uuid': 'workspace-a',
                'name': 'local',
                'mode': 'stdio',
                'enable': True,
                'extra_args': {},
            }
        ),
    )
    ap.workspace_service = SimpleNamespace(get_execution_binding=AsyncMock())
    loader = MCPLoader(ap)
    loader.host_mcp_server = AsyncMock()

    await loader.load_mcp_servers_from_db()

    loader.host_mcp_server.assert_not_awaited()
    ap.workspace_service.get_execution_binding.assert_not_awaited()
    assert loader.sessions == {}
