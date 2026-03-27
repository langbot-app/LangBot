from __future__ import annotations

import os
import tempfile
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

import langbot_plugin.api.entities.builtin.resource.tool as resource_tool

from langbot.pkg.provider.tools.loaders.native import NativeToolLoader
from langbot.pkg.provider.tools.toolmgr import ToolManager


class StubLoader:
    def __init__(self, tools: list[resource_tool.LLMTool] | None = None, invoke_result=None):
        self._tools = tools or []
        self._invoke_result = invoke_result

    async def get_tools(self, *_args, **_kwargs):
        return self._tools

    async def has_tool(self, name: str) -> bool:
        return any(tool.name == name for tool in self._tools)

    async def invoke_tool(self, name: str, parameters: dict, query):
        return self._invoke_result(name, parameters, query) if callable(self._invoke_result) else self._invoke_result

    async def shutdown(self):
        return None


def make_tool(name: str) -> resource_tool.LLMTool:
    return resource_tool.LLMTool(
        name=name,
        human_desc=name,
        description=name,
        parameters={'type': 'object', 'properties': {}},
        func=lambda parameters: parameters,
    )


@pytest.mark.asyncio
async def test_tool_manager_omits_skill_authoring_tools_by_default():
    manager = ToolManager(SimpleNamespace())
    manager.native_tool_loader = StubLoader([make_tool('exec')])
    manager.skill_authoring_tool_loader = StubLoader([make_tool('reload_skills')])
    manager.plugin_tool_loader = StubLoader([make_tool('plugin_tool')])
    manager.mcp_tool_loader = StubLoader([make_tool('mcp_tool')])

    tools = await manager.get_all_tools()

    assert [tool.name for tool in tools] == ['exec', 'plugin_tool', 'mcp_tool']


@pytest.mark.asyncio
async def test_tool_manager_includes_skill_authoring_tools_when_requested():
    manager = ToolManager(SimpleNamespace())
    manager.native_tool_loader = StubLoader([make_tool('exec')])
    manager.skill_authoring_tool_loader = StubLoader([make_tool('reload_skills')])
    manager.plugin_tool_loader = StubLoader([make_tool('plugin_tool')])
    manager.mcp_tool_loader = StubLoader([make_tool('mcp_tool')])

    tools = await manager.get_all_tools(include_skill_authoring=True)

    assert [tool.name for tool in tools] == ['exec', 'reload_skills', 'plugin_tool', 'mcp_tool']


@pytest.mark.asyncio
async def test_tool_manager_routes_native_tool_calls():
    app = SimpleNamespace()
    manager = ToolManager(app)
    manager.native_tool_loader = StubLoader([make_tool('exec')], invoke_result={'backend': 'fake'})
    manager.skill_authoring_tool_loader = StubLoader([make_tool('reload_skills')])
    manager.plugin_tool_loader = StubLoader([make_tool('plugin_tool')])
    manager.mcp_tool_loader = StubLoader([make_tool('mcp_tool')])

    result = await manager.execute_func_call('exec', {'command': 'pwd'}, query=Mock())

    assert result == {'backend': 'fake'}


@pytest.mark.asyncio
async def test_native_tool_loader_hides_tools_when_box_unavailable():
    loader = NativeToolLoader(SimpleNamespace(box_service=SimpleNamespace(available=False)))

    assert await loader.get_tools() == []
    assert await loader.has_tool('exec') is False
    assert await loader.has_tool('read') is False
    assert await loader.has_tool('write') is False
    assert await loader.has_tool('edit') is False


@pytest.mark.asyncio
async def test_native_tool_loader_exposes_all_tools_when_box_available():
    loader = NativeToolLoader(SimpleNamespace(box_service=SimpleNamespace(available=True)))

    tools = await loader.get_tools()

    assert [tool.name for tool in tools] == ['exec', 'read', 'write', 'edit']
    assert await loader.has_tool('exec') is True
    assert await loader.has_tool('read') is True
    assert await loader.has_tool('write') is True
    assert await loader.has_tool('edit') is True


# ── read/write/edit file tool tests ─────────────────────────────


def _make_loader_with_workspace(tmpdir: str) -> tuple[NativeToolLoader, Mock]:
    logger = Mock()
    box_service = SimpleNamespace(available=True, default_host_workspace=tmpdir)
    ap = SimpleNamespace(box_service=box_service, logger=logger)
    return NativeToolLoader(ap), logger


def _make_query() -> Mock:
    q = Mock()
    q.query_id = 'test-query-1'
    return q


@pytest.mark.asyncio
async def test_read_file():
    with tempfile.TemporaryDirectory() as tmpdir:
        loader, _ = _make_loader_with_workspace(tmpdir)
        with open(os.path.join(tmpdir, 'hello.txt'), 'w') as f:
            f.write('hello world')

        result = await loader.invoke_tool('read', {'path': '/workspace/hello.txt'}, _make_query())

        assert result['ok'] is True
        assert result['content'] == 'hello world'


@pytest.mark.asyncio
async def test_read_nonexistent_file():
    with tempfile.TemporaryDirectory() as tmpdir:
        loader, _ = _make_loader_with_workspace(tmpdir)

        result = await loader.invoke_tool('read', {'path': '/workspace/no_such.txt'}, _make_query())

        assert result['ok'] is False
        assert 'not found' in result['error'].lower()


@pytest.mark.asyncio
async def test_read_directory():
    with tempfile.TemporaryDirectory() as tmpdir:
        loader, _ = _make_loader_with_workspace(tmpdir)
        os.makedirs(os.path.join(tmpdir, 'subdir'))
        with open(os.path.join(tmpdir, 'a.txt'), 'w') as f:
            f.write('a')

        result = await loader.invoke_tool('read', {'path': '/workspace'}, _make_query())

        assert result['ok'] is True
        assert result['is_directory'] is True
        assert 'a.txt' in result['content']


@pytest.mark.asyncio
async def test_write_creates_file():
    with tempfile.TemporaryDirectory() as tmpdir:
        loader, _ = _make_loader_with_workspace(tmpdir)

        result = await loader.invoke_tool(
            'write', {'path': '/workspace/new.txt', 'content': 'new content'}, _make_query()
        )

        assert result['ok'] is True
        with open(os.path.join(tmpdir, 'new.txt')) as f:
            assert f.read() == 'new content'


@pytest.mark.asyncio
async def test_write_creates_subdirectories():
    with tempfile.TemporaryDirectory() as tmpdir:
        loader, _ = _make_loader_with_workspace(tmpdir)

        result = await loader.invoke_tool(
            'write', {'path': '/workspace/sub/deep/file.txt', 'content': 'nested'}, _make_query()
        )

        assert result['ok'] is True
        with open(os.path.join(tmpdir, 'sub', 'deep', 'file.txt')) as f:
            assert f.read() == 'nested'


@pytest.mark.asyncio
async def test_edit_replaces_unique_string():
    with tempfile.TemporaryDirectory() as tmpdir:
        loader, _ = _make_loader_with_workspace(tmpdir)
        with open(os.path.join(tmpdir, 'code.py'), 'w') as f:
            f.write('def foo():\n    return 1\n')

        result = await loader.invoke_tool(
            'edit',
            {'path': '/workspace/code.py', 'old_string': 'return 1', 'new_string': 'return 42'},
            _make_query(),
        )

        assert result['ok'] is True
        with open(os.path.join(tmpdir, 'code.py')) as f:
            assert f.read() == 'def foo():\n    return 42\n'


@pytest.mark.asyncio
async def test_edit_rejects_ambiguous_match():
    with tempfile.TemporaryDirectory() as tmpdir:
        loader, _ = _make_loader_with_workspace(tmpdir)
        with open(os.path.join(tmpdir, 'dup.txt'), 'w') as f:
            f.write('aaa\naaa\n')

        result = await loader.invoke_tool(
            'edit',
            {'path': '/workspace/dup.txt', 'old_string': 'aaa', 'new_string': 'bbb'},
            _make_query(),
        )

        assert result['ok'] is False
        assert '2' in result['error']


@pytest.mark.asyncio
async def test_edit_rejects_missing_string():
    with tempfile.TemporaryDirectory() as tmpdir:
        loader, _ = _make_loader_with_workspace(tmpdir)
        with open(os.path.join(tmpdir, 'x.txt'), 'w') as f:
            f.write('hello')

        result = await loader.invoke_tool(
            'edit',
            {'path': '/workspace/x.txt', 'old_string': 'nope', 'new_string': 'yes'},
            _make_query(),
        )

        assert result['ok'] is False
        assert 'not found' in result['error'].lower()


@pytest.mark.asyncio
async def test_path_escape_blocked():
    with tempfile.TemporaryDirectory() as tmpdir:
        loader, _ = _make_loader_with_workspace(tmpdir)

        with pytest.raises(ValueError, match='escapes'):
            await loader.invoke_tool('read', {'path': '/workspace/../../etc/passwd'}, _make_query())
