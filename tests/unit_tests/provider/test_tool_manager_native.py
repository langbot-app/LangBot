from __future__ import annotations

import os
import tempfile
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

import pytest

import langbot_plugin.api.entities.builtin.resource.tool as resource_tool

from langbot.pkg.provider.tools.loader import ToolLoader
from langbot.pkg.provider.tools.loaders.native import (
    _DEFAULT_TOOL_RESULT_MAX_BYTES,
    _GLOB_MAX_MATCHES,
    _GREP_MAX_MATCHES,
    NativeToolLoader,
)
from langbot.pkg.provider.tools.toolmgr import ToolManager


class StubLoader:
    def __init__(self, tools: list[resource_tool.LLMTool] | None = None, invoke_result=None):
        self._tools = tools or []
        self._invoke_result = invoke_result

    async def get_tools(self, *_args, **_kwargs):
        return self._tools

    async def get_tool(self, name: str):
        for tool in self._tools:
            if tool.name == name:
                return tool
        return None

    async def has_tool(self, name: str) -> bool:
        return any(tool.name == name for tool in self._tools)

    async def invoke_tool(self, name: str, parameters: dict, query):
        return self._invoke_result(name, parameters, query) if callable(self._invoke_result) else self._invoke_result

    async def shutdown(self):
        return None


class DirectLookupLoader(StubLoader):
    async def get_tools(self, *_args, **_kwargs):
        raise AssertionError('ToolManager should use the loader get_tool contract')

    async def get_tool(self, name: str):
        return make_tool(name) if name == 'direct_tool' else None


def make_tool(name: str) -> resource_tool.LLMTool:
    return resource_tool.LLMTool(
        name=name,
        human_desc=name,
        description=name,
        parameters={'type': 'object', 'properties': {}},
        func=lambda parameters: parameters,
    )


class ListOnlyLoader(ToolLoader):
    async def get_tools(self, *_args, **_kwargs):
        return [make_tool('listed_tool')]

    async def has_tool(self, name: str) -> bool:
        return name == 'listed_tool'

    async def invoke_tool(self, name: str, parameters: dict, query):
        return parameters

    async def shutdown(self):
        return None


@pytest.mark.asyncio
async def test_tool_loader_get_tool_falls_back_to_public_tool_list():
    loader = ListOnlyLoader(SimpleNamespace())

    tool = await loader.get_tool('listed_tool')
    missing_tool = await loader.get_tool('missing_tool')

    assert tool is not None
    assert tool.name == 'listed_tool'
    assert missing_tool is None


@pytest.mark.asyncio
async def test_tool_manager_omits_skill_authoring_tools_by_default():
    manager = ToolManager(SimpleNamespace())
    manager.native_tool_loader = StubLoader([make_tool('exec')])
    manager.skill_tool_loader = StubLoader([make_tool('activate')])
    manager.plugin_tool_loader = StubLoader([make_tool('plugin_tool')])
    manager.mcp_tool_loader = StubLoader([make_tool('mcp_tool')])

    tools = await manager.get_all_tools()

    assert [tool.name for tool in tools] == ['exec', 'plugin_tool', 'mcp_tool']


@pytest.mark.asyncio
async def test_tool_manager_includes_skill_authoring_tools_when_requested():
    manager = ToolManager(SimpleNamespace())
    manager.native_tool_loader = StubLoader([make_tool('exec')])
    manager.skill_tool_loader = StubLoader([make_tool('activate')])
    manager.plugin_tool_loader = StubLoader([make_tool('plugin_tool')])
    manager.mcp_tool_loader = StubLoader([make_tool('mcp_tool')])

    tools = await manager.get_all_tools(include_skill_authoring=True)

    assert [tool.name for tool in tools] == ['exec', 'activate', 'plugin_tool', 'mcp_tool']


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
async def test_tool_manager_get_tool_by_name_resolves_native_and_skill_tools():
    manager = ToolManager(SimpleNamespace())
    manager.native_tool_loader = StubLoader([make_tool('exec')])
    manager.skill_tool_loader = StubLoader([make_tool('activate')])
    manager.plugin_tool_loader = StubLoader([make_tool('plugin_tool')])
    manager.mcp_tool_loader = StubLoader([make_tool('mcp_tool')])

    native_tool = await manager.get_tool_by_name('exec')
    skill_tool = await manager.get_tool_by_name('activate')

    assert native_tool is not None
    assert native_tool.name == 'exec'
    assert skill_tool is not None
    assert skill_tool.name == 'activate'


@pytest.mark.asyncio
async def test_tool_manager_uses_loader_get_tool_contract():
    manager = ToolManager(SimpleNamespace())
    manager.native_tool_loader = StubLoader([])
    manager.skill_tool_loader = StubLoader([])
    manager.plugin_tool_loader = DirectLookupLoader()
    manager.mcp_tool_loader = StubLoader([])

    tool = await manager.get_tool_by_name('direct_tool')

    assert tool is not None
    assert tool.name == 'direct_tool'


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
    q.variables = {}
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
        assert result['truncated'] is False
        assert result['start_line'] == 1
        assert result['end_line'] == 1


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
        assert result['total'] == 2
        assert result['truncated'] is False


@pytest.mark.asyncio
async def test_read_file_supports_line_window():
    with tempfile.TemporaryDirectory() as tmpdir:
        loader, _ = _make_loader_with_workspace(tmpdir)
        content = '\n'.join(f'line-{line_no}' for line_no in range(1, 7))
        with open(os.path.join(tmpdir, 'large.txt'), 'w') as f:
            f.write(content)

        result = await loader.invoke_tool(
            'read',
            {'path': '/workspace/large.txt', 'offset': 2, 'limit': 3},
            _make_query(),
        )

        assert result['ok'] is True
        assert result['content'] == 'line-2\nline-3\nline-4'
        assert result['truncated'] is True
        assert result['truncated_by'] == 'lines'
        assert result['start_line'] == 2
        assert result['end_line'] == 4
        assert result['next_offset'] == 5


@pytest.mark.asyncio
async def test_read_file_is_bounded_by_bytes():
    with tempfile.TemporaryDirectory() as tmpdir:
        loader, _ = _make_loader_with_workspace(tmpdir)
        with open(os.path.join(tmpdir, 'wide.txt'), 'w') as f:
            f.write(('x' * 128) + '\nsecond line')

        result = await loader.invoke_tool(
            'read',
            {'path': '/workspace/wide.txt', 'max_bytes': 32},
            _make_query(),
        )

        assert result['ok'] is True
        assert result['truncated'] is True
        assert result['truncated_by'] == 'bytes'
        assert result['next_offset'] == 1
        assert result['content'].startswith('[Line 1 exceeds')
        assert len(result['content']) < 200


@pytest.mark.asyncio
async def test_skill_read_uses_host_preview_when_package_root_available():
    with tempfile.TemporaryDirectory() as tmpdir:
        skill_root = os.path.join(tmpdir, 'skill-demo')
        os.makedirs(skill_root)
        with open(os.path.join(skill_root, 'large.txt'), 'w') as f:
            f.write('first\nsecond\nthird')

        box_service = SimpleNamespace(
            available=True,
            default_workspace=tmpdir,
            read_skill_file=AsyncMock(return_value={'content': 'should not be used'}),
        )
        skill_mgr = SimpleNamespace(skills={'demo': {'name': 'demo', 'package_root': skill_root}})
        loader = NativeToolLoader(SimpleNamespace(box_service=box_service, skill_mgr=skill_mgr, logger=Mock()))

        result = await loader.invoke_tool(
            'read',
            {'path': '/workspace/.skills/demo/large.txt', 'limit': 1},
            _make_query(),
        )

        assert result['ok'] is True
        assert result['content'] == 'first'
        assert result['truncated'] is True
        assert result['next_offset'] == 2
        box_service.read_skill_file.assert_not_awaited()


@pytest.mark.asyncio
async def test_read_truncated_file_returns_host_artifact_ref_for_agent_run():
    with tempfile.TemporaryDirectory() as tmpdir:
        engine = object()
        logger = Mock()
        box_service = SimpleNamespace(available=True, default_workspace=tmpdir)
        persistence_mgr = SimpleNamespace(get_db_engine=Mock(return_value=engine))
        loader = NativeToolLoader(
            SimpleNamespace(box_service=box_service, persistence_mgr=persistence_mgr, logger=logger)
        )
        with open(os.path.join(tmpdir, 'large.txt'), 'w') as f:
            f.write('first\nsecond\nthird')

        query = _make_query()
        query.bot_uuid = 'bot-001'
        query._agent_run_session = {
            'run_id': 'run-001',
            'runner_id': 'plugin:test/runner/default',
            'authorization': {'conversation_id': 'conv-001'},
        }

        with patch('langbot.pkg.agent.runner.artifact_store.ArtifactStore') as store_cls:
            store = store_cls.return_value
            store.register_file_artifact = AsyncMock(return_value='artifact-file-001')

            result = await loader.invoke_tool(
                'read',
                {'path': '/workspace/large.txt', 'limit': 1},
                query,
            )

        assert result['ok'] is True
        assert result['content'] == 'first'
        assert result['preview'] == 'first'
        assert result['truncated'] is True
        assert result['artifact_refs'] == [
            {
                'artifact_id': 'artifact-file-001',
                'artifact_type': 'file',
                'mime_type': 'text/plain',
                'name': 'large.txt',
                'size_bytes': os.path.getsize(os.path.join(tmpdir, 'large.txt')),
            }
        ]
        store_cls.assert_called_once_with(engine)
        store.register_file_artifact.assert_awaited_once()
        call_kwargs = store.register_file_artifact.await_args.kwargs
        assert call_kwargs['host_path'] == os.path.realpath(os.path.join(tmpdir, 'large.txt'))
        assert call_kwargs['host_root'] == tmpdir
        assert call_kwargs['conversation_id'] == 'conv-001'
        assert call_kwargs['run_id'] == 'run-001'
        assert call_kwargs['runner_id'] == 'plugin:test/runner/default'
        assert call_kwargs['metadata']['sandbox_path'] == '/workspace/large.txt'


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


@pytest.mark.asyncio
async def test_glob_result_is_bounded():
    with tempfile.TemporaryDirectory() as tmpdir:
        loader, _ = _make_loader_with_workspace(tmpdir)
        for index in range(_GLOB_MAX_MATCHES + 5):
            with open(os.path.join(tmpdir, f'file-{index:03d}.txt'), 'w') as f:
                f.write(str(index))

        result = await loader.invoke_tool(
            'glob',
            {'path': '/workspace', 'pattern': '*.txt'},
            _make_query(),
        )

        assert result['ok'] is True
        assert len(result['matches']) == _GLOB_MAX_MATCHES
        assert result['total'] == _GLOB_MAX_MATCHES + 5
        assert result['truncated'] is True
        assert result['truncated_by'] == 'matches'
        assert result['preview'].splitlines() == result['matches']


@pytest.mark.asyncio
async def test_grep_result_is_bounded_by_match_count():
    with tempfile.TemporaryDirectory() as tmpdir:
        loader, _ = _make_loader_with_workspace(tmpdir)
        with open(os.path.join(tmpdir, 'hits.txt'), 'w') as f:
            for index in range(_GREP_MAX_MATCHES + 5):
                f.write(f'needle {index}\n')

        result = await loader.invoke_tool(
            'grep',
            {'path': '/workspace', 'pattern': 'needle', 'include': '*.txt'},
            _make_query(),
        )

        assert result['ok'] is True
        assert len(result['matches']) == _GREP_MAX_MATCHES
        assert result['total'] == _GREP_MAX_MATCHES
        assert result['truncated'] is True
        assert result['truncated_by'] == 'matches'


@pytest.mark.asyncio
async def test_grep_truncates_long_matching_line():
    with tempfile.TemporaryDirectory() as tmpdir:
        loader, _ = _make_loader_with_workspace(tmpdir)
        with open(os.path.join(tmpdir, 'wide.txt'), 'w') as f:
            f.write('needle ' + ('x' * 600))

        result = await loader.invoke_tool(
            'grep',
            {'path': '/workspace', 'pattern': 'needle', 'include': '*.txt'},
            _make_query(),
        )

        assert result['ok'] is True
        assert len(result['matches']) == 1
        assert result['matches'][0]['content'].endswith('... [truncated]')
        assert result['truncated'] is True
        assert result['truncated_by'] == 'line'


@pytest.mark.asyncio
async def test_exec_result_adds_preview_and_truncated_flag():
    with tempfile.TemporaryDirectory() as tmpdir:
        box_service = SimpleNamespace(
            available=True,
            default_workspace=tmpdir,
            execute_tool=AsyncMock(
                return_value={
                    'ok': True,
                    'stdout': 'stdout text',
                    'stderr': 'stderr text',
                    'stdout_truncated': True,
                    'stderr_truncated': False,
                }
            ),
        )
        loader = NativeToolLoader(SimpleNamespace(box_service=box_service, logger=Mock()))

        result = await loader.invoke_tool('exec', {'command': 'echo ok'}, _make_query())

        assert result['ok'] is True
        assert result['truncated'] is True
        assert result['preview'] == 'stdout:\nstdout text\n\nstderr:\nstderr text'
        box_service.execute_tool.assert_awaited_once()


@pytest.mark.asyncio
async def test_exec_result_caps_untrusted_large_output():
    with tempfile.TemporaryDirectory() as tmpdir:
        box_service = SimpleNamespace(
            available=True,
            default_workspace=tmpdir,
            execute_tool=AsyncMock(
                return_value={
                    'ok': True,
                    'stdout': 'x' * (_DEFAULT_TOOL_RESULT_MAX_BYTES + 128),
                    'stderr': '',
                    'stdout_truncated': False,
                    'stderr_truncated': False,
                }
            ),
        )
        loader = NativeToolLoader(SimpleNamespace(box_service=box_service, logger=Mock()))

        result = await loader.invoke_tool('exec', {'command': 'echo ok'}, _make_query())

        assert result['ok'] is True
        assert len(result['stdout'].encode('utf-8')) <= _DEFAULT_TOOL_RESULT_MAX_BYTES
        assert result['stdout_truncated'] is True
        assert result['truncated'] is True
        assert result['preview'] == result['stdout']
