from __future__ import annotations

import os
import tempfile
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from langbot.pkg.box.workspace import (
    BoxWorkspaceSession,
    classify_python_workspace,
    infer_workspace_host_path,
    rewrite_mounted_path,
    wrap_python_command_with_env,
)


def test_rewrite_mounted_path_translates_host_prefix():
    result = rewrite_mounted_path('/tmp/demo/project/app.py', '/tmp/demo/project')
    assert result == '/workspace/app.py'


def test_infer_workspace_host_path_unwraps_virtualenv_bin_dir():
    with tempfile.TemporaryDirectory() as tmpdir:
        project_root = os.path.join(tmpdir, 'project')
        os.makedirs(os.path.join(project_root, '.venv', 'bin'))
        python_bin = os.path.join(project_root, '.venv', 'bin', 'python')
        script = os.path.join(project_root, 'server.py')

        with open(python_bin, 'w', encoding='utf-8') as handle:
            handle.write('')
        with open(script, 'w', encoding='utf-8') as handle:
            handle.write('print("ok")\n')

        result = infer_workspace_host_path(python_bin, [script])

        assert result == os.path.realpath(project_root)


def test_classify_python_workspace_detects_package_and_requirements():
    with tempfile.TemporaryDirectory() as tmpdir:
        assert classify_python_workspace(tmpdir) is None

        with open(os.path.join(tmpdir, 'requirements.txt'), 'w', encoding='utf-8') as handle:
            handle.write('requests\n')
        assert classify_python_workspace(tmpdir) == 'requirements'

        with open(os.path.join(tmpdir, 'pyproject.toml'), 'w', encoding='utf-8') as handle:
            handle.write('[project]\nname = "demo"\n')
        assert classify_python_workspace(tmpdir) == 'package'


def test_wrap_python_command_with_env_contains_bootstrap_and_command():
    command = wrap_python_command_with_env('python script.py')

    assert 'python -m venv "$_LB_VENV_DIR"' in command
    assert 'export VIRTUAL_ENV="$_LB_VENV_DIR"' in command
    assert command.rstrip().endswith('python script.py')


@pytest.mark.asyncio
async def test_workspace_session_execute_for_query_uses_session_payload():
    box_service = SimpleNamespace(execute_spec_payload=AsyncMock(return_value={'ok': True}))
    workspace = BoxWorkspaceSession(
        box_service,
        'skill-person_123-demo',
        host_path='/tmp/project',
        host_path_mode='rw',
        env={'FOO': 'bar'},
    )

    query = SimpleNamespace(query_id='q1')
    result = await workspace.execute_for_query(query, 'python run.py', workdir='/workspace', timeout_sec=30)

    assert result == {'ok': True}
    payload = box_service.execute_spec_payload.await_args.args[0]
    assert payload == {
        'session_id': 'skill-person_123-demo',
        'workdir': '/workspace',
        'env': {'FOO': 'bar'},
        'host_path': '/tmp/project',
        'host_path_mode': 'rw',
        'cmd': 'python run.py',
        'timeout_sec': 30,
    }


@pytest.mark.asyncio
async def test_workspace_session_start_managed_process_rewrites_command_and_args():
    box_service = SimpleNamespace(start_managed_process=AsyncMock(return_value={'status': 'running'}))
    workspace = BoxWorkspaceSession(
        box_service,
        'mcp-u1',
        host_path='/tmp/project',
        host_path_mode='ro',
    )

    result = await workspace.start_managed_process(
        '/tmp/project/.venv/bin/python',
        ['/tmp/project/server.py', '--config', '/tmp/project/config.json'],
        env={'TOKEN': '1'},
    )

    assert result == {'status': 'running'}
    session_id = box_service.start_managed_process.await_args.args[0]
    payload = box_service.start_managed_process.await_args.args[1]
    assert session_id == 'mcp-u1'
    assert payload == {
        'command': 'python',
        'args': ['/workspace/server.py', '--config', '/workspace/config.json'],
        'env': {'TOKEN': '1'},
        'cwd': '/workspace',
        'process_id': 'default',
    }


def test_workspace_session_build_session_payload_keeps_generic_workspace_shape():
    workspace = BoxWorkspaceSession(
        Mock(),
        'workspace-1',
        host_path='/tmp/project',
        host_path_mode='rw',
        env={'FOO': 'bar'},
        network='on',
        read_only_rootfs=False,
        image='python:3.11',
        cpus=1.0,
        memory_mb=512,
        pids_limit=128,
    )

    assert workspace.build_session_payload() == {
        'session_id': 'workspace-1',
        'workdir': '/workspace',
        'env': {'FOO': 'bar'},
        'network': 'on',
        'read_only_rootfs': False,
        'host_path': '/tmp/project',
        'host_path_mode': 'rw',
        'image': 'python:3.11',
        'cpus': 1.0,
        'memory_mb': 512,
        'pids_limit': 128,
    }
