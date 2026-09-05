"""Reusable workspace/session helpers built on top of Box.

This module is the middle layer between raw Box runtime primitives and
application-specific consumers.

It intentionally stays generic:
- path and virtualenv rewriting are workspace concerns
- Python project detection/bootstrap are workspace concerns
- session exec / managed-process helpers are workspace concerns

Higher layers add their own semantics on top; BoxWorkspaceSession retains only
workspace, execution, and managed-process concepts.
"""

from __future__ import annotations

import os
from typing import Any

from ..utils.python_workspace import list_python_manifest_files

_VENV_DIRS = frozenset({'.venv', 'venv', 'env', '.env'})
_VENV_BIN_DIRS = frozenset({'bin', 'Scripts'})


def rewrite_mounted_path(path: str, host_path: str | None, *, mount_path: str = '/workspace') -> str:
    """Translate a host path into the path visible inside the sandbox mount."""
    if not host_path or not path:
        return path
    normalized_host = os.path.realpath(host_path)
    normalized_path = os.path.realpath(path)
    if normalized_path.startswith(normalized_host + '/'):
        return mount_path + normalized_path[len(normalized_host) :]
    if normalized_path == normalized_host:
        return mount_path
    return path


def unwrap_venv_path(directory: str) -> str:
    """Collapse ``.../.venv/bin`` style paths back to the project root."""
    parts = directory.replace('\\', '/').split('/')
    for i in range(len(parts) - 1, 0, -1):
        if parts[i] in _VENV_BIN_DIRS and i >= 1:
            venv_dir = parts[i - 1]
            if venv_dir in _VENV_DIRS:
                project_root = '/'.join(parts[: i - 1])
                return project_root if project_root else '/'
    return directory


def infer_workspace_host_path(command: str, args: list[str] | None = None) -> str | None:
    """Infer the project/workspace root from absolute command/arg paths."""
    candidates: list[str] = []
    for part in [command, *(args or [])]:
        if not os.path.isabs(part):
            continue
        if os.path.exists(part):
            directory = os.path.dirname(part)
            candidates.append(os.path.realpath(unwrap_venv_path(directory)))
    if not candidates:
        return None
    common = os.path.commonpath(candidates)
    return common if common != '/' else None


def rewrite_venv_command(command: str, host_path: str | None, *, mount_path: str = '/workspace') -> str:
    """Rewrite host venv interpreters to plain ``python`` inside the sandbox.

    Once a project is mounted into the sandbox, host virtualenv paths are no
    longer valid. For those paths we intentionally drop down to ``python`` and
    let the sandbox-side environment/bootstrap decide what interpreter to use.
    """
    if not host_path or not command:
        return command
    normalized_host = os.path.realpath(host_path)
    normalized_command = os.path.realpath(command)
    if not normalized_command.startswith(normalized_host + '/'):
        return command
    rel = normalized_command[len(normalized_host) + 1 :]
    parts = rel.replace('\\', '/').split('/')
    if len(parts) >= 3 and parts[0] in _VENV_DIRS and parts[1] in _VENV_BIN_DIRS and parts[2].startswith('python'):
        return 'python'
    return rewrite_mounted_path(normalized_command, host_path, mount_path=mount_path)


def classify_python_workspace(host_path: str | None) -> str | None:
    """Return the generic Python workspace shape, without app-specific policy."""
    manifest_files = set(list_python_manifest_files(host_path))
    if not manifest_files:
        return None
    if {'pyproject.toml', 'setup.py', 'setup.cfg'} & manifest_files:
        return 'package'
    if 'requirements.txt' in manifest_files:
        return 'requirements'
    return None


class BoxWorkspaceSession:
    """High-level handle for one reusable workspace-backed Box session.

    The Box runtime already understands sessions and managed processes. This
    wrapper adds LangBot's workspace-centric view on top: a mounted host path,
    a stable ``session_id``, optional environment defaults, and convenience
    helpers for exec or long-running processes inside that workspace.
    """

    def __init__(
        self,
        box_service,
        execution_context,
        session_id: str,
        *,
        host_path: str | None = None,
        host_path_mode: str = 'rw',
        workdir: str = '/workspace',
        env: dict[str, str] | None = None,
        mount_path: str = '/workspace',
        network: str | None = None,
        read_only_rootfs: bool | None = None,
        image: str | None = None,
        cpus: float | None = None,
        memory_mb: int | None = None,
        pids_limit: int | None = None,
        persistent: bool = False,
    ):
        self.box_service = box_service
        self.execution_context = execution_context
        self.session_id = session_id
        self.host_path = host_path
        self.host_path_mode = host_path_mode
        self.workdir = workdir
        self.env = dict(env or {})
        self.mount_path = mount_path
        self.network = network
        self.read_only_rootfs = read_only_rootfs
        self.image = image
        self.cpus = cpus
        self.memory_mb = memory_mb
        self.pids_limit = pids_limit
        self.persistent = persistent

    def rewrite_path(self, path: str) -> str:
        return rewrite_mounted_path(path, self.host_path, mount_path=self.mount_path)

    def rewrite_venv_command(self, command: str) -> str:
        return rewrite_venv_command(command, self.host_path, mount_path=self.mount_path)

    def build_session_payload(self) -> dict[str, Any]:
        # Keep this payload generic so callers can reuse the same workspace
        # handle for plain exec, file-producing tasks, or managed processes.
        payload: dict[str, Any] = {
            'session_id': self.session_id,
            'workdir': self.workdir,
            'env': self.env,
            'persistent': self.persistent,
        }
        if self.network is not None:
            payload['network'] = self.network
        if self.read_only_rootfs is not None:
            payload['read_only_rootfs'] = self.read_only_rootfs
        if self.host_path:
            payload['host_path'] = self.host_path
            payload['host_path_mode'] = self.host_path_mode
        for key in ('image', 'cpus', 'memory_mb', 'pids_limit'):
            value = getattr(self, key)
            if value is not None:
                payload[key] = value
        return payload

    def build_exec_payload(
        self,
        cmd: str,
        *,
        workdir: str | None = None,
        env: dict[str, str] | None = None,
        timeout_sec: int | None = None,
    ) -> dict[str, Any]:
        # Exec payloads inherit the session-level workspace config, then layer
        # per-call command/workdir/env overrides on top.
        payload = self.build_session_payload()
        payload['cmd'] = cmd
        payload['workdir'] = workdir or self.workdir
        if timeout_sec is not None:
            payload['timeout_sec'] = timeout_sec
        resolved_env = self.env if env is None else env
        if resolved_env:
            payload['env'] = resolved_env
        elif 'env' in payload and not payload['env']:
            payload.pop('env')
        return payload

    async def execute_raw(
        self,
        cmd: str,
        *,
        workdir: str | None = None,
        env: dict[str, str] | None = None,
        timeout_sec: int | None = None,
    ):
        payload = self.build_exec_payload(cmd, workdir=workdir, env=env, timeout_sec=timeout_sec)
        return await self.box_service.execute_in_context(self.execution_context, payload)

    async def execute_for_query(
        self,
        query,
        cmd: str,
        *,
        workdir: str | None = None,
        env: dict[str, str] | None = None,
        timeout_sec: int | None = None,
    ) -> dict:
        payload = self.build_exec_payload(cmd, workdir=workdir, env=env, timeout_sec=timeout_sec)
        return await self.box_service.execute_spec_payload(payload, query)

    async def create_session(self):
        return await self.box_service.create_session(self.execution_context, self.build_session_payload())

    def build_process_payload(
        self,
        command: str,
        args: list[str] | None = None,
        *,
        env: dict[str, str] | None = None,
        cwd: str = '/workspace',
    ) -> dict[str, Any]:
        # Managed processes run inside the same workspace model as one-shot
        # execs, so path/venv rewriting is shared here.
        normalized_command = command
        normalized_args = list(args or [])
        normalized_cwd = cwd
        if self.host_path:
            normalized_command = self.rewrite_venv_command(command)
            normalized_args = [self.rewrite_path(arg) for arg in normalized_args]
            normalized_cwd = self.rewrite_path(cwd)
        return {
            'command': normalized_command,
            'args': normalized_args,
            'env': dict(env or {}),
            'cwd': normalized_cwd,
        }

    async def start_managed_process(
        self,
        command: str,
        args: list[str] | None = None,
        *,
        process_id: str = 'default',
        env: dict[str, str] | None = None,
        cwd: str = '/workspace',
    ):
        payload = self.build_process_payload(command, args, env=env, cwd=cwd)
        payload['process_id'] = process_id
        return await self.box_service.start_managed_process(self.execution_context, self.session_id, payload)

    async def get_managed_process(self, process_id: str = 'default'):
        return await self.box_service.get_managed_process(self.execution_context, self.session_id, process_id)

    async def stop_managed_process(self, process_id: str = 'default') -> None:
        await self.box_service.stop_managed_process(self.execution_context, self.session_id, process_id)

    async def get_managed_process_websocket_connection(
        self,
        process_id: str = 'default',
    ) -> tuple[str, dict[str, str]]:
        return await self.box_service.get_managed_process_websocket_connection(
            self.execution_context,
            self.session_id,
            process_id,
        )

    async def cleanup(self) -> None:
        await self.box_service.client.delete_session(
            self.session_id,
            action_context=self.box_service._action_context(self.execution_context),
        )
