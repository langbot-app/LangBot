from __future__ import annotations
"""Reusable workspace/session helpers built on top of Box.

This module is the middle layer between the raw Box runtime primitives and
application-specific flows such as skills or MCP stdio.

It intentionally stays generic:
- path and virtualenv rewriting are workspace concerns
- Python project detection/bootstrap are workspace concerns
- session exec / managed-process helpers are workspace concerns

Higher layers add their own semantics on top, for example:
- skills choose a stable per-skill session id and use repeated exec
- MCP stdio chooses how to prepare dependencies and attaches to a managed process
"""

import os
import textwrap
from typing import Any

PYTHON_MANIFEST_FILES = (
    'requirements.txt',
    'pyproject.toml',
    'setup.py',
    'setup.cfg',
)
_VENV_DIRS = frozenset({'.venv', 'venv', 'env', '.env'})
_VENV_BIN_DIRS = frozenset({'bin', 'Scripts'})


def normalize_host_path(path: str | None) -> str:
    if path is None:
        return ''
    stripped = str(path).strip()
    if not stripped:
        return ''
    return os.path.realpath(os.path.abspath(stripped))


def rewrite_mounted_path(path: str, host_path: str | None, *, mount_path: str = '/workspace') -> str:
    """Translate a host path into the path visible inside the sandbox mount."""
    if not host_path or not path:
        return path
    normalized_host = os.path.realpath(host_path)
    if path.startswith(normalized_host + '/'):
        return mount_path + path[len(normalized_host) :]
    if path == normalized_host:
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
    if not command.startswith(normalized_host + '/'):
        return command
    rel = command[len(normalized_host) + 1 :]
    parts = rel.replace('\\', '/').split('/')
    if len(parts) >= 3 and parts[0] in _VENV_DIRS and parts[1] in _VENV_BIN_DIRS and parts[2].startswith('python'):
        return 'python'
    return rewrite_mounted_path(command, host_path, mount_path=mount_path)


def list_python_manifest_files(host_path: str | None) -> list[str]:
    normalized_root = normalize_host_path(host_path)
    if not normalized_root:
        return []
    return [
        filename for filename in PYTHON_MANIFEST_FILES if os.path.isfile(os.path.join(normalized_root, filename))
    ]


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


def should_prepare_python_env(host_path: str | None) -> bool:
    normalized_root = normalize_host_path(host_path)
    if not normalized_root:
        return False
    if os.path.isdir(os.path.join(normalized_root, '.venv')):
        return True
    return bool(list_python_manifest_files(normalized_root))


def wrap_python_command_with_env(command: str, *, mount_path: str = '/workspace') -> str:
    """Wrap a command with a reusable sandbox-local Python env bootstrap.

    This is the generic "workspace is a Python project" path used by mutable
    workspaces such as skills. Read-only installation strategies stay in the
    higher-level caller because they are application policy, not workspace
    semantics.
    """
    bootstrap = textwrap.dedent(
        f"""
        set -e

        _LB_VENV_DIR="{mount_path}/.venv"
        _LB_META_DIR="{mount_path}/.langbot"
        _LB_META_FILE="$_LB_META_DIR/python-env.json"
        _LB_LOCK_DIR="$_LB_META_DIR/python-env.lock"
        _LB_TMP_DIR="{mount_path}/.tmp"
        _LB_PIP_CACHE_DIR="{mount_path}/.cache/pip"

        mkdir -p "$_LB_META_DIR" "$_LB_TMP_DIR" "$_LB_PIP_CACHE_DIR"
        export TMPDIR="$_LB_TMP_DIR"
        export TEMP="$_LB_TMP_DIR"
        export TMP="$_LB_TMP_DIR"
        export PIP_CACHE_DIR="$_LB_PIP_CACHE_DIR"

        _lb_python_meta() {{
          python - <<'PY'
        import hashlib
        import json
        import os
        import sys

        root = "{mount_path}"
        digest = hashlib.sha256()
        manifest_files = []
        for rel in ("requirements.txt", "pyproject.toml", "setup.py", "setup.cfg"):
            path = os.path.join(root, rel)
            if not os.path.isfile(path):
                continue
            manifest_files.append(rel)
            with open(path, "rb") as handle:
                digest.update(rel.encode("utf-8"))
                digest.update(b"\\0")
                digest.update(handle.read())
                digest.update(b"\\0")

        print(
            json.dumps(
                {{
                    "python_executable": sys.executable,
                    "python_version": list(sys.version_info[:3]),
                    "manifest_files": manifest_files,
                    "manifest_sha256": digest.hexdigest(),
                }},
                sort_keys=True,
            )
        )
        PY
        }}

        _LB_CURRENT_META="$(_lb_python_meta)"
        _LB_NEEDS_BOOTSTRAP=0

        if [ ! -x "$_LB_VENV_DIR/bin/python" ]; then
          _LB_NEEDS_BOOTSTRAP=1
        elif [ ! -f "$_LB_META_FILE" ]; then
          _LB_NEEDS_BOOTSTRAP=1
        elif [ "$(cat "$_LB_META_FILE")" != "$_LB_CURRENT_META" ]; then
          _LB_NEEDS_BOOTSTRAP=1
        fi

        if [ "$_LB_NEEDS_BOOTSTRAP" -eq 1 ]; then
          _LB_LOCK_WAIT=0
          while ! mkdir "$_LB_LOCK_DIR" 2>/dev/null; do
            if [ "$_LB_LOCK_WAIT" -ge 120 ]; then
              echo "Timed out waiting for Python environment lock: $_LB_LOCK_DIR" >&2
              exit 1
            fi
            sleep 1
            _LB_LOCK_WAIT=$((_LB_LOCK_WAIT + 1))
          done

          _lb_cleanup_lock() {{
            rmdir "$_LB_LOCK_DIR" >/dev/null 2>&1 || true
          }}
          trap _lb_cleanup_lock EXIT INT TERM

          _LB_CURRENT_META="$(_lb_python_meta)"
          _LB_NEEDS_BOOTSTRAP=0
          if [ ! -x "$_LB_VENV_DIR/bin/python" ]; then
            _LB_NEEDS_BOOTSTRAP=1
          elif [ ! -f "$_LB_META_FILE" ]; then
            _LB_NEEDS_BOOTSTRAP=1
          elif [ "$(cat "$_LB_META_FILE")" != "$_LB_CURRENT_META" ]; then
            _LB_NEEDS_BOOTSTRAP=1
          fi

          if [ "$_LB_NEEDS_BOOTSTRAP" -eq 1 ]; then
            rm -rf "$_LB_VENV_DIR"
            python -m venv "$_LB_VENV_DIR"
            . "$_LB_VENV_DIR/bin/activate"
            python -m pip install --upgrade pip setuptools wheel
            if [ -f "{mount_path}/requirements.txt" ]; then
              python -m pip install -r "{mount_path}/requirements.txt"
            elif [ -f "{mount_path}/pyproject.toml" ] || [ -f "{mount_path}/setup.py" ] || [ -f "{mount_path}/setup.cfg" ]; then
              python -m pip install "{mount_path}"
            fi
            printf '%s' "$_LB_CURRENT_META" > "$_LB_META_FILE"
          fi
        fi

        export VIRTUAL_ENV="$_LB_VENV_DIR"
        export PATH="$_LB_VENV_DIR/bin:$PATH"
        {command}
        """
    ).strip()
    return bootstrap + '\n'


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
    ):
        self.box_service = box_service
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
        return await self.box_service.client.execute(self.box_service.build_spec(payload))

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
        return await self.box_service.create_session(self.build_session_payload())

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
        env: dict[str, str] | None = None,
        cwd: str = '/workspace',
    ):
        payload = self.build_process_payload(command, args, env=env, cwd=cwd)
        return await self.box_service.start_managed_process(self.session_id, payload)

    async def get_managed_process(self):
        return await self.box_service.get_managed_process(self.session_id)

    def get_managed_process_websocket_url(self) -> str:
        return self.box_service.get_managed_process_websocket_url(self.session_id)

    async def cleanup(self) -> None:
        await self.box_service.client.delete_session(self.session_id)
