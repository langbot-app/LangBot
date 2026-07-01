from __future__ import annotations

import base64
import os
import tempfile
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

import langbot_plugin.api.entities.builtin.resource.tool as resource_tool

from langbot.pkg.provider.tools.loaders.native import NativeToolLoader
from langbot.pkg.provider.tools.toolmgr import ToolManager


class StubLoader:
    def __init__(
        self,
        tools: list[resource_tool.LLMTool] | None = None,
        invoke_result=None,
        catalog_source: str = 'mcp',
        catalog_source_name: str = 'fixture-server',
    ):
        self._tools = tools or []
        self._invoke_result = invoke_result
        self._catalog_source = catalog_source
        self._catalog_source_name = catalog_source_name

    async def get_tools(self, *_args, **_kwargs):
        return self._tools

    async def get_tool_catalog(self, *_args, **_kwargs):
        return [
            {
                'name': tool.name,
                'description': tool.description,
                'human_desc': tool.human_desc,
                'parameters': tool.parameters,
                'source': self._catalog_source,
                'source_name': self._catalog_source_name,
                'source_id': self._catalog_source_name,
            }
            for tool in self._tools
        ]

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
async def test_tool_manager_includes_skill_tools_by_default():
    """Skill tools are exposed like native tools; the SkillToolLoader self-gates."""
    manager = ToolManager(SimpleNamespace())
    manager.native_tool_loader = StubLoader([make_tool('exec')])
    manager.skill_tool_loader = StubLoader([make_tool('activate')])
    manager.plugin_tool_loader = StubLoader([make_tool('plugin_tool')])
    manager.mcp_tool_loader = StubLoader([make_tool('mcp_tool')])

    tools = await manager.get_all_tools()

    assert [tool.name for tool in tools] == ['exec', 'activate', 'plugin_tool', 'mcp_tool']


@pytest.mark.asyncio
async def test_tool_manager_omits_skill_tools_when_loader_unavailable():
    """When the SkillToolLoader gate is closed (no sandbox / skill_mgr) it returns no tools."""
    manager = ToolManager(SimpleNamespace())
    manager.native_tool_loader = StubLoader([make_tool('exec')])
    manager.skill_tool_loader = StubLoader([])
    manager.plugin_tool_loader = StubLoader([make_tool('plugin_tool')])
    manager.mcp_tool_loader = StubLoader([make_tool('mcp_tool')])

    tools = await manager.get_all_tools()

    assert [tool.name for tool in tools] == ['exec', 'plugin_tool', 'mcp_tool']


@pytest.mark.asyncio
async def test_tool_manager_catalog_labels_tool_sources():
    manager = ToolManager(SimpleNamespace())
    manager.native_tool_loader = StubLoader([make_tool('exec')])
    manager.skill_tool_loader = StubLoader([make_tool('activate')])
    manager.plugin_tool_loader = StubLoader(
        [make_tool('plugin_tool')],
        catalog_source='plugin',
        catalog_source_name='fixture-plugin',
    )
    manager.mcp_tool_loader = StubLoader([make_tool('mcp_tool')])

    catalog = await manager.get_tool_catalog(include_skill_authoring=True)

    assert [(item['name'], item['source'], item['source_name']) for item in catalog] == [
        ('exec', 'builtin', 'LangBot'),
        ('activate', 'skill', 'LangBot'),
        ('plugin_tool', 'plugin', 'fixture-plugin'),
        ('mcp_tool', 'mcp', 'fixture-server'),
    ]


@pytest.mark.asyncio
async def test_tool_manager_routes_native_tool_calls():
    app = SimpleNamespace()
    manager = ToolManager(app)
    manager.native_tool_loader = StubLoader([make_tool('exec')], invoke_result={'backend': 'fake'})
    manager.skill_tool_loader = StubLoader([make_tool('activate')])
    manager.plugin_tool_loader = StubLoader([make_tool('plugin_tool')])
    manager.mcp_tool_loader = StubLoader([make_tool('mcp_tool')])

    result = await manager.execute_func_call('exec', {'command': 'pwd'}, query=Mock())

    assert result == {'backend': 'fake'}


@pytest.mark.asyncio
async def test_native_tool_loader_hides_tools_when_box_unavailable():
    loader = NativeToolLoader(SimpleNamespace(box_service=SimpleNamespace(available=False)))

    assert await loader.get_tools() == []
    for tool_name in ('exec', 'read', 'write', 'edit', 'glob', 'grep'):
        assert await loader.has_tool(tool_name) is False


@pytest.mark.asyncio
async def test_native_tool_loader_exposes_all_tools_when_box_available():
    box_service = SimpleNamespace(
        available=True,
        get_status=AsyncMock(return_value={'backend': {'available': True}}),
    )
    loader = NativeToolLoader(SimpleNamespace(box_service=box_service, logger=Mock()))
    await loader.initialize()

    tools = await loader.get_tools()

    assert [tool.name for tool in tools] == ['exec', 'read', 'write', 'edit', 'glob', 'grep']
    for tool_name in ('exec', 'read', 'write', 'edit', 'glob', 'grep'):
        assert await loader.has_tool(tool_name) is True


# ── read/write/edit file tool tests ─────────────────────────────


def _make_loader_with_workspace(tmpdir: str) -> tuple[NativeToolLoader, Mock]:
    logger = Mock()
    box_service = SimpleNamespace(available=True, default_workspace=tmpdir)
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
async def test_read_binary_file_as_base64_chunk():
    with tempfile.TemporaryDirectory() as tmpdir:
        loader, _ = _make_loader_with_workspace(tmpdir)
        with open(os.path.join(tmpdir, 'blob.bin'), 'wb') as f:
            f.write(b'\x00\x01\x02\x03\x04')

        result = await loader.invoke_tool(
            'read',
            {
                'path': '/workspace/blob.bin',
                'encoding': 'base64',
                'byte_offset': 1,
                'max_bytes': 2,
            },
            _make_query(),
        )

        assert result['ok'] is True
        assert result['content'] == base64.b64encode(b'\x01\x02').decode('ascii')
        assert result['encoding'] == 'base64'
        assert result['byte_offset'] == 1
        assert result['length'] == 2
        assert result['size_bytes'] == 5
        assert result['has_more'] is True
        assert result['next_byte_offset'] == 3


@pytest.mark.asyncio
async def test_write_base64_file_append():
    with tempfile.TemporaryDirectory() as tmpdir:
        loader, _ = _make_loader_with_workspace(tmpdir)

        first = base64.b64encode(b'\x00\x01').decode('ascii')
        second = base64.b64encode(b'\x02\x03').decode('ascii')
        await loader.invoke_tool(
            'write',
            {'path': '/workspace/blob.bin', 'content': first, 'encoding': 'base64'},
            _make_query(),
        )
        result = await loader.invoke_tool(
            'write',
            {
                'path': '/workspace/blob.bin',
                'content': second,
                'encoding': 'base64',
                'mode': 'append',
            },
            _make_query(),
        )

        assert result['ok'] is True
        with open(os.path.join(tmpdir, 'blob.bin'), 'rb') as f:
            assert f.read() == b'\x00\x01\x02\x03'


@pytest.mark.asyncio
async def test_write_base64_rejects_invalid_content():
    with tempfile.TemporaryDirectory() as tmpdir:
        loader, _ = _make_loader_with_workspace(tmpdir)

        result = await loader.invoke_tool(
            'write',
            {'path': '/workspace/blob.bin', 'content': 'not base64!', 'encoding': 'base64'},
            _make_query(),
        )

        assert result['ok'] is False
        assert 'invalid base64' in result['error']
        assert not os.path.exists(os.path.join(tmpdir, 'blob.bin'))


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


@pytest.mark.asyncio
async def test_box_availability_helper_handles_unavailable_and_errors():
    from langbot.pkg.provider.tools.loaders.availability import is_box_backend_available

    assert await is_box_backend_available(SimpleNamespace()) is False
    assert await is_box_backend_available(SimpleNamespace(box_service=SimpleNamespace(available=False))) is False

    unavailable_backend = SimpleNamespace(
        available=True,
        get_status=AsyncMock(return_value={'backend': {'available': False}}),
    )
    assert await is_box_backend_available(SimpleNamespace(box_service=unavailable_backend)) is False

    failing_backend = SimpleNamespace(
        available=True,
        get_status=AsyncMock(side_effect=RuntimeError('box unavailable')),
    )
    assert await is_box_backend_available(SimpleNamespace(box_service=failing_backend)) is False


@pytest.mark.asyncio
async def test_read_file_supports_offset_limit_and_truncation_metadata():
    with tempfile.TemporaryDirectory() as tmpdir:
        loader, _ = _make_loader_with_workspace(tmpdir)
        with open(os.path.join(tmpdir, 'lines.txt'), 'w', encoding='utf-8') as f:
            f.write('one\ntwo\nthree\nfour\n')

        result = await loader.invoke_tool(
            'read',
            {'path': '/workspace/lines.txt', 'offset': 2, 'limit': 2},
            _make_query(),
        )

        assert result == {
            'ok': True,
            'content': 'two\nthree',
            'truncated': True,
            'truncated_by': 'lines',
            'start_line': 2,
            'end_line': 3,
            'next_offset': 4,
            'max_lines': 2,
            'max_bytes': 50 * 1024,
        }


@pytest.mark.asyncio
async def test_read_file_handles_line_larger_than_byte_limit():
    with tempfile.TemporaryDirectory() as tmpdir:
        loader, _ = _make_loader_with_workspace(tmpdir)
        with open(os.path.join(tmpdir, 'long-line.txt'), 'w', encoding='utf-8') as f:
            f.write('abcdef\n')

        result = await loader.invoke_tool(
            'read',
            {'path': '/workspace/long-line.txt', 'max_bytes': 3},
            _make_query(),
        )

        assert result['ok'] is True
        assert result['truncated'] is True
        assert result['truncated_by'] == 'bytes'
        assert result['next_offset'] == 1
        assert 'exceeds the 3B read limit' in result['content']


@pytest.mark.asyncio
async def test_exec_result_is_capped_and_exposes_preview_metadata():
    with tempfile.TemporaryDirectory() as tmpdir:
        box_service = SimpleNamespace(
            available=True,
            default_workspace=tmpdir,
            execute_tool=AsyncMock(
                return_value={
                    'ok': True,
                    'stdout': 'a' * 60000,
                    'stderr': 'b' * 60000,
                    'exit_code': 0,
                }
            ),
        )
        loader = NativeToolLoader(SimpleNamespace(box_service=box_service, logger=Mock()))

        result = await loader.invoke_tool('exec', {'command': 'python -V'}, _make_query())

        assert result['ok'] is True
        assert len(result['stdout'].encode('utf-8')) == 50 * 1024
        assert len(result['stderr'].encode('utf-8')) == 50 * 1024
        assert len(result['preview'].encode('utf-8')) == 50 * 1024
        assert result['stdout_truncated'] is True
        assert result['stderr_truncated'] is True
        assert result['truncated'] is True
        assert result['truncated_by'] == 'bytes'


@pytest.mark.asyncio
async def test_glob_caps_match_count_and_returns_preview():
    with tempfile.TemporaryDirectory() as tmpdir:
        loader, _ = _make_loader_with_workspace(tmpdir)
        for index in range(105):
            with open(os.path.join(tmpdir, f'file-{index:03d}.txt'), 'w', encoding='utf-8') as f:
                f.write(str(index))

        result = await loader.invoke_tool('glob', {'path': '/workspace', 'pattern': '*.txt'}, _make_query())

        assert result['ok'] is True
        assert result['total'] == 105
        assert len(result['matches']) == 100
        assert result['preview'] == '\n'.join(result['matches'])
        assert result['truncated'] is True
        assert result['truncated_by'] == 'matches'


@pytest.mark.asyncio
async def test_grep_reports_invalid_regex_and_truncates_long_matching_lines():
    with tempfile.TemporaryDirectory() as tmpdir:
        loader, _ = _make_loader_with_workspace(tmpdir)
        with open(os.path.join(tmpdir, 'data.txt'), 'w', encoding='utf-8') as f:
            f.write('needle ' + ('x' * 600) + '\n')

        invalid = await loader.invoke_tool('grep', {'path': '/workspace', 'pattern': '['}, _make_query())
        result = await loader.invoke_tool('grep', {'path': '/workspace', 'pattern': 'needle'}, _make_query())

        assert invalid['ok'] is False
        assert 'Invalid regex' in invalid['error']
        assert result['ok'] is True
        assert result['truncated'] is True
        assert result['truncated_by'] == 'line'
        assert result['matches'][0]['file'] == '/workspace/data.txt'
        assert result['matches'][0]['content'].endswith('... [truncated]')
