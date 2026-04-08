"""Tests for MCP Box integration: path rewriting, host_path inference, config model, payloads.

Uses importlib.util.spec_from_file_location to load mcp.py directly without
triggering the circular import chain through the app module.
"""

from __future__ import annotations

import importlib
import importlib.util
import os
import sys
import tempfile
import types
from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest


# ---------------------------------------------------------------------------
# Load mcp.py directly from file path, with stub dependencies
# ---------------------------------------------------------------------------


def _stub_module(fqn: str, attrs: dict | None = None, is_package: bool = False):
    """Create or return a stub module and register it in sys.modules."""
    if fqn in sys.modules:
        mod = sys.modules[fqn]
    else:
        mod = types.ModuleType(fqn)
        mod.__spec__ = importlib.machinery.ModuleSpec(fqn, None, is_package=is_package)
        if is_package:
            mod.__path__ = []
        sys.modules[fqn] = mod
    parts = fqn.rsplit('.', 1)
    if len(parts) == 2 and parts[0] in sys.modules:
        setattr(sys.modules[parts[0]], parts[1], mod)
    if attrs:
        for k, v in attrs.items():
            setattr(mod, k, v)
    return mod


@pytest.fixture(scope='module', autouse=True)
def mcp_module():
    """Load mcp.py with minimal stubs to avoid circular imports."""
    saved = {}

    def _save_and_stub(name, attrs=None, is_package=False):
        saved[name] = sys.modules.get(name)
        # Don't overwrite modules that already exist (from other test modules)
        if name in sys.modules:
            return
        _stub_module(name, attrs, is_package)

    # Stub entire dependency chains as packages / modules
    _save_and_stub('langbot_plugin', is_package=True)
    _save_and_stub('langbot_plugin.api', is_package=True)
    _save_and_stub('langbot_plugin.api.entities', is_package=True)
    _save_and_stub('langbot_plugin.api.entities.events', is_package=True)
    _save_and_stub('langbot_plugin.api.entities.events.pipeline_query', {})
    _save_and_stub('langbot_plugin.api.entities.builtin', is_package=True)
    _save_and_stub('langbot_plugin.api.entities.builtin.resource', is_package=True)
    _save_and_stub(
        'langbot_plugin.api.entities.builtin.resource.tool',
        {
            'LLMTool': type('LLMTool', (), {}),
        },
    )
    _save_and_stub('langbot_plugin.api.entities.builtin.provider', is_package=True)
    _save_and_stub('langbot_plugin.api.entities.builtin.provider.message', {})
    _save_and_stub('sqlalchemy', {'select': Mock()})
    _save_and_stub('httpx', {'AsyncClient': Mock()})
    _save_and_stub('mcp', {'ClientSession': Mock, 'StdioServerParameters': Mock}, is_package=True)
    _save_and_stub('mcp.client', is_package=True)
    _save_and_stub('mcp.client.stdio', {'stdio_client': Mock()})
    _save_and_stub('mcp.client.sse', {'sse_client': Mock()})
    _save_and_stub('mcp.client.streamable_http', {'streamable_http_client': Mock()})
    _save_and_stub('mcp.client.websocket', {'websocket_client': Mock()})

    # Stub the provider.tools.loader (source of circular import)
    _save_and_stub('langbot', is_package=True)
    _save_and_stub('langbot.pkg', is_package=True)
    _save_and_stub('langbot.pkg.provider', is_package=True)
    _save_and_stub('langbot.pkg.provider.tools', is_package=True)
    _save_and_stub(
        'langbot.pkg.provider.tools.loader',
        {
            'ToolLoader': type('ToolLoader', (), {'__init__': lambda self, ap: None}),
        },
    )
    _save_and_stub('langbot.pkg.provider.tools.loaders', is_package=True)
    _save_and_stub('langbot.pkg.core', is_package=True)
    _save_and_stub('langbot.pkg.core.app', {'Application': type('Application', (), {})})
    _save_and_stub('langbot.pkg.entity', is_package=True)
    _save_and_stub('langbot.pkg.entity.persistence', is_package=True)
    _save_and_stub('langbot.pkg.entity.persistence.mcp', {})

    # box models
    import enum as _enum

    class _BPS(str, _enum.Enum):
        RUNNING = 'running'
        EXITED = 'exited'

    _save_and_stub('langbot_plugin.box', is_package=True)
    _save_and_stub('langbot_plugin.box.models', {'BoxManagedProcessStatus': _BPS})

    # Now load mcp.py via spec_from_file_location
    mod_fqn = 'langbot.pkg.provider.tools.loaders.mcp'
    sys.modules.pop(mod_fqn, None)
    mcp_path = os.path.join(
        os.path.dirname(__file__),
        '..',
        '..',
        '..',
        'src',
        'langbot',
        'pkg',
        'provider',
        'tools',
        'loaders',
        'mcp.py',
    )
    mcp_path = os.path.normpath(mcp_path)
    spec = importlib.util.spec_from_file_location(mod_fqn, mcp_path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[mod_fqn] = mod
    spec.loader.exec_module(mod)

    yield mod

    # Cleanup
    sys.modules.pop(mod_fqn, None)
    for name in reversed(list(saved)):
        if saved[name] is None:
            sys.modules.pop(name, None)
        else:
            sys.modules[name] = saved[name]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_ap():
    ap = Mock()
    ap.logger = Mock()
    ap.box_service = Mock()
    return ap


def _make_session(mcp_module, server_config: dict, ap=None):
    if ap is None:
        ap = _make_ap()
    return mcp_module.RuntimeMCPSession(
        server_name=server_config.get('name', 'test-server'),
        server_config=server_config,
        enable=True,
        ap=ap,
    )


# ── MCPServerBoxConfig ──────────────────────────────────────────────


class TestMCPServerBoxConfig:
    def test_default_values(self, mcp_module):
        cfg = mcp_module.MCPServerBoxConfig.model_validate({})
        assert cfg.image is None
        assert cfg.network == 'on'
        assert cfg.host_path is None
        assert cfg.host_path_mode == 'ro'
        assert cfg.env == {}
        assert cfg.startup_timeout_sec == 120
        assert cfg.cpus is None
        assert cfg.memory_mb is None
        assert cfg.pids_limit is None
        assert cfg.read_only_rootfs is None

    def test_custom_values(self, mcp_module):
        cfg = mcp_module.MCPServerBoxConfig.model_validate(
            {
                'image': 'node:20',
                'network': 'on',
                'host_path': '/home/user/mcp',
                'host_path_mode': 'rw',
                'env': {'FOO': 'bar'},
                'startup_timeout_sec': 60,
                'cpus': 2.0,
                'memory_mb': 1024,
                'pids_limit': 256,
                'read_only_rootfs': False,
            }
        )
        assert cfg.image == 'node:20'
        assert cfg.network == 'on'
        assert cfg.cpus == 2.0
        assert cfg.memory_mb == 1024

    def test_extra_fields_ignored(self, mcp_module):
        cfg = mcp_module.MCPServerBoxConfig.model_validate(
            {
                'image': 'node:20',
                'unknown_field': 'whatever',
            }
        )
        assert cfg.image == 'node:20'
        assert not hasattr(cfg, 'unknown_field')


# ── Path Rewriting ──────────────────────────────────────────────────


class TestRewritePath:
    def test_no_host_path_returns_unchanged(self, mcp_module):
        s = _make_session(
            mcp_module,
            {
                'name': 'test',
                'uuid': 'u1',
                'mode': 'sse',
                'command': 'python',
                'args': [],
            },
        )
        assert s._rewrite_path('/some/path', None) == '/some/path'

    def test_empty_path_returns_empty(self, mcp_module):
        s = _make_session(
            mcp_module,
            {
                'name': 'test',
                'uuid': 'u1',
                'mode': 'sse',
                'command': 'python',
                'args': [],
            },
        )
        assert s._rewrite_path('', '/home/user/mcp') == ''

    def test_prefix_match_rewrites(self, mcp_module):
        s = _make_session(
            mcp_module,
            {
                'name': 'test',
                'uuid': 'u1',
                'mode': 'sse',
                'command': 'python',
                'args': [],
            },
        )
        result = s._rewrite_path('/home/user/mcp/server.py', '/home/user/mcp')
        assert result == '/workspace/server.py'

    def test_exact_match_rewrites_to_workspace(self, mcp_module):
        s = _make_session(
            mcp_module,
            {
                'name': 'test',
                'uuid': 'u1',
                'mode': 'sse',
                'command': 'python',
                'args': [],
            },
        )
        result = s._rewrite_path('/home/user/mcp', '/home/user/mcp')
        assert result == '/workspace'

    def test_non_matching_path_unchanged(self, mcp_module):
        s = _make_session(
            mcp_module,
            {
                'name': 'test',
                'uuid': 'u1',
                'mode': 'sse',
                'command': 'python',
                'args': [],
            },
        )
        result = s._rewrite_path('/opt/other/server.py', '/home/user/mcp')
        assert result == '/opt/other/server.py'

    def test_similar_prefix_not_rewritten(self, mcp_module):
        s = _make_session(
            mcp_module,
            {
                'name': 'test',
                'uuid': 'u1',
                'mode': 'sse',
                'command': 'python',
                'args': [],
            },
        )
        result = s._rewrite_path('/home/user/mcp-other/file.py', '/home/user/mcp')
        assert result == '/home/user/mcp-other/file.py'

    def test_nested_subpath_rewrites(self, mcp_module):
        s = _make_session(
            mcp_module,
            {
                'name': 'test',
                'uuid': 'u1',
                'mode': 'sse',
                'command': 'python',
                'args': [],
            },
        )
        result = s._rewrite_path('/home/user/mcp/src/lib/main.py', '/home/user/mcp')
        assert result == '/workspace/src/lib/main.py'


# ── host_path Inference ─────────────────────────────────────────────


class TestInferHostPath:
    def test_no_absolute_paths_returns_none(self, mcp_module):
        s = _make_session(
            mcp_module,
            {
                'name': 'test',
                'uuid': 'u1',
                'mode': 'sse',
                'command': 'python',
                'args': ['server.py'],
            },
        )
        assert s._infer_host_path() is None

    def test_nonexistent_path_returns_none(self, mcp_module):
        s = _make_session(
            mcp_module,
            {
                'name': 'test',
                'uuid': 'u1',
                'mode': 'sse',
                'command': '/nonexistent/path/to/python',
                'args': [],
            },
        )
        assert s._infer_host_path() is None

    def test_existing_absolute_path_infers_directory(self, mcp_module):
        with tempfile.NamedTemporaryFile(suffix='.py') as f:
            s = _make_session(
                mcp_module,
                {
                    'name': 'test',
                    'uuid': 'u1',
                    'mode': 'sse',
                    'command': 'python',
                    'args': [f.name],
                },
            )
            result = s._infer_host_path()
            assert result is not None
            assert result == os.path.dirname(os.path.realpath(f.name))


# ── Build Box Session Payload ───────────────────────────────────────


class TestBuildBoxSessionPayload:
    def test_minimal_config(self, mcp_module):
        s = _make_session(
            mcp_module,
            {
                'name': 'test',
                'uuid': 'u1',
                'mode': 'sse',
                'command': 'python',
                'args': [],
            },
        )
        payload = s._build_box_session_payload('session-123')
        assert payload['session_id'] == 'session-123'
        assert payload['workdir'] == '/workspace'
        assert payload['env'] == {}
        assert 'host_path' not in payload

    def test_with_host_path(self, mcp_module):
        s = _make_session(
            mcp_module,
            {
                'name': 'test',
                'uuid': 'u1',
                'mode': 'sse',
                'command': 'python',
                'args': [],
                'box': {'host_path': '/home/user/mcp', 'host_path_mode': 'ro'},
            },
        )
        payload = s._build_box_session_payload('session-123')
        assert payload['host_path'] == '/home/user/mcp'
        assert payload['host_path_mode'] == 'ro'

    def test_optional_fields_included_when_set(self, mcp_module):
        s = _make_session(
            mcp_module,
            {
                'name': 'test',
                'uuid': 'u1',
                'mode': 'sse',
                'command': 'python',
                'args': [],
                'box': {'image': 'node:20', 'cpus': 2.0, 'memory_mb': 1024, 'pids_limit': 256},
            },
        )
        payload = s._build_box_session_payload('session-123')
        assert payload['image'] == 'node:20'
        assert payload['cpus'] == 2.0
        assert payload['memory_mb'] == 1024
        assert payload['pids_limit'] == 256

    def test_none_fields_excluded(self, mcp_module):
        s = _make_session(
            mcp_module,
            {
                'name': 'test',
                'uuid': 'u1',
                'mode': 'sse',
                'command': 'python',
                'args': [],
            },
        )
        payload = s._build_box_session_payload('session-123')
        assert 'image' not in payload
        assert 'cpus' not in payload


# ── Build Box Process Payload ───────────────────────────────────────


class TestBuildBoxProcessPayload:
    def test_basic_payload(self, mcp_module):
        s = _make_session(
            mcp_module,
            {
                'name': 'test',
                'uuid': 'u1',
                'mode': 'sse',
                'command': 'python',
                'args': ['server.py'],
                'env': {'KEY': 'val'},
            },
        )
        payload = s._build_box_process_payload()
        assert payload['command'] == 'python'
        assert payload['args'] == ['server.py']
        assert payload['env'] == {'KEY': 'val'}
        assert payload['cwd'] == '/workspace'

    def test_path_rewriting_applied(self, mcp_module):
        s = _make_session(
            mcp_module,
            {
                'name': 'test',
                'uuid': 'u1',
                'mode': 'sse',
                'command': '/home/user/mcp/venv/bin/python',
                'args': ['/home/user/mcp/server.py', '--config', '/home/user/mcp/config.json'],
                'env': {},
                'box': {'host_path': '/home/user/mcp'},
            },
        )
        payload = s._build_box_process_payload()
        # venv python is replaced with plain 'python' (deps installed in-container)
        assert payload['command'] == 'python'
        assert payload['args'] == ['/workspace/server.py', '--config', '/workspace/config.json']

    def test_non_matching_args_not_rewritten(self, mcp_module):
        s = _make_session(
            mcp_module,
            {
                'name': 'test',
                'uuid': 'u1',
                'mode': 'sse',
                'command': 'python',
                'args': ['/opt/other/server.py', '--flag'],
                'env': {},
                'box': {'host_path': '/home/user/mcp'},
            },
        )
        payload = s._build_box_process_payload()
        assert payload['command'] == 'python'
        assert payload['args'] == ['/opt/other/server.py', '--flag']


# ── get_runtime_info_dict ───────────────────────────────────────────


class TestGetRuntimeInfoDict:
    def test_non_stdio_session(self, mcp_module):
        s = _make_session(
            mcp_module,
            {
                'name': 'test',
                'uuid': 'test-uuid',
                'mode': 'sse',
                'command': 'python',
                'args': [],
            },
        )
        info = s.get_runtime_info_dict()
        assert info['status'] == 'connecting'
        assert 'box_session_id' not in info

    def test_stdio_session_includes_box_info(self, mcp_module):
        ap = _make_ap()
        ap.box_service.available = True
        s = _make_session(
            mcp_module,
            {
                'name': 'test',
                'uuid': 'test-uuid',
                'mode': 'stdio',
                'command': 'python',
                'args': [],
            },
            ap=ap,
        )
        info = s.get_runtime_info_dict()
        assert info['box_session_id'] == 'mcp-test-uuid'
        assert info['box_enabled'] is True

    def test_stdio_session_without_box_runtime(self, mcp_module):
        ap = _make_ap()
        ap.box_service.available = False
        s = _make_session(
            mcp_module,
            {
                'name': 'test',
                'uuid': 'test-uuid',
                'mode': 'stdio',
                'command': 'python',
                'args': [],
            },
            ap=ap,
        )
        info = s.get_runtime_info_dict()
        assert 'box_session_id' not in info


# ── Box config parsing ──────────────────────────────────────────────


class TestBoxConfigParsing:
    def test_box_config_parsed_from_server_config(self, mcp_module):
        s = _make_session(
            mcp_module,
            {
                'name': 'test',
                'uuid': 'u1',
                'mode': 'sse',
                'command': 'python',
                'args': [],
                'box': {'image': 'node:20', 'host_path': '/home/user/mcp'},
            },
        )
        assert isinstance(s.box_config, mcp_module.MCPServerBoxConfig)
        assert s.box_config.image == 'node:20'
        assert s.box_config.host_path == '/home/user/mcp'

    def test_missing_box_key_uses_defaults(self, mcp_module):
        s = _make_session(
            mcp_module,
            {
                'name': 'test',
                'uuid': 'u1',
                'mode': 'sse',
                'command': 'python',
                'args': [],
            },
        )
        assert isinstance(s.box_config, mcp_module.MCPServerBoxConfig)
        assert s.box_config.image is None
        assert s.box_config.host_path_mode == 'ro'


@pytest.mark.asyncio
async def test_init_box_stdio_server_keeps_host_mount_validation_enabled(mcp_module):
    class FakeClientSession:
        def __init__(self, *_args):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def initialize(self):
            return None

    @asynccontextmanager
    async def fake_websocket_client(_url: str):
        yield ('read-stream', 'write-stream')

    mcp_module.ClientSession = FakeClientSession
    mcp_module.websocket_client = fake_websocket_client

    ap = _make_ap()
    ap.box_service.available = True
    ap.box_service.create_session = AsyncMock(return_value={})
    ap.box_service.build_spec = Mock(return_value='validated-spec')
    ap.box_service.client = SimpleNamespace(
        execute=AsyncMock(return_value=SimpleNamespace(ok=True, stderr='', exit_code=0))
    )
    ap.box_service.start_managed_process = AsyncMock(return_value={})
    ap.box_service.get_managed_process_websocket_url = Mock(return_value='ws://box.example/process')

    session = _make_session(
        mcp_module,
        {
            'name': 'test',
            'uuid': 'u1',
            'mode': 'stdio',
            'command': '/home/user/mcp/.venv/bin/python',
            'args': ['/home/user/mcp/server.py'],
            'box': {'host_path': '/home/user/mcp'},
        },
        ap=ap,
    )
    session._detect_install_command = Mock(return_value='pip install --no-cache-dir -r /workspace/requirements.txt')

    await session._init_box_stdio_server()
    await session.exit_stack.aclose()

    assert ap.box_service.create_session.await_count == 1
    assert ap.box_service.create_session.await_args.kwargs.get('skip_host_mount_validation', False) is False
    assert ap.box_service.build_spec.call_count == 1
    assert ap.box_service.build_spec.call_args.kwargs.get('skip_host_mount_validation', False) is False
