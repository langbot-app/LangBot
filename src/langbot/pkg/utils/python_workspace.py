"""Python project detection and sandbox-local environment bootstrap helpers."""

from __future__ import annotations

import os
import textwrap


PYTHON_MANIFEST_FILES = (
    'requirements.txt',
    'pyproject.toml',
    'setup.py',
    'setup.cfg',
)


def normalize_host_path(path: str | None) -> str:
    if path is None:
        return ''
    stripped = str(path).strip()
    if not stripped:
        return ''
    return os.path.realpath(os.path.abspath(stripped))


def list_python_manifest_files(host_path: str | None) -> list[str]:
    normalized_root = normalize_host_path(host_path)
    if not normalized_root:
        return []
    return [
        filename
        for filename in PYTHON_MANIFEST_FILES
        if os.path.isfile(os.path.join(normalized_root, filename))
    ]


def should_prepare_python_env(host_path: str | None) -> bool:
    normalized_root = normalize_host_path(host_path)
    if not normalized_root:
        return False
    if os.path.isdir(os.path.join(normalized_root, '.venv')):
        return True
    return bool(list_python_manifest_files(normalized_root))


def wrap_python_command_with_env(
    command: str,
    *,
    mount_path: str = '/workspace',
    state_path: str | None = None,
) -> str:
    """Wrap a command with a reusable sandbox-local Python env bootstrap."""

    writable_state_path = state_path or mount_path
    bootstrap = textwrap.dedent(
        f"""
        set -e

        _LB_VENV_DIR="{writable_state_path}/.venv"
        _LB_META_DIR="{writable_state_path}/.langbot"
        _LB_META_FILE="$_LB_META_DIR/python-env.json"
        _LB_LOCK_DIR="$_LB_META_DIR/python-env.lock"
        _LB_TMP_DIR="{writable_state_path}/.tmp"
        _LB_PIP_CACHE_DIR="{writable_state_path}/.cache/pip"

        mkdir -p "$_LB_META_DIR" "$_LB_TMP_DIR" "$_LB_PIP_CACHE_DIR"
        _LB_SYSTEM_PYTHON="$(command -v python3 || command -v python || true)"
        if [ -z "$_LB_SYSTEM_PYTHON" ]; then
          echo "python3 or python is required to prepare the workspace Python environment" >&2
          exit 127
        fi

        export TMPDIR="$_LB_TMP_DIR"
        export TEMP="$_LB_TMP_DIR"
        export TMP="$_LB_TMP_DIR"
        export PIP_CACHE_DIR="$_LB_PIP_CACHE_DIR"

        _lb_python_meta() {{
          "$_LB_SYSTEM_PYTHON" - <<'PY'
        import hashlib
        import json
        import os
        import sys

        root = "{mount_path}"
        max_manifest_bytes = 10 * 1024 * 1024
        digest = hashlib.sha256()
        manifest_files = []
        for rel in ("requirements.txt", "pyproject.toml", "setup.py", "setup.cfg"):
            path = os.path.join(root, rel)
            if not os.path.isfile(path):
                continue
            if os.path.getsize(path) > max_manifest_bytes:
                raise RuntimeError(
                    f"Python project manifest exceeds {{max_manifest_bytes}} bytes: {{rel}}"
                )
            manifest_files.append(rel)
            with open(path, "rb") as handle:
                digest.update(rel.encode("utf-8"))
                digest.update(b"\0")
                while chunk := handle.read(1024 * 1024):
                    digest.update(chunk)
                digest.update(b"\0")

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
              _LB_LOCK_OWNER="$(cat "$_LB_LOCK_DIR/pid" 2>/dev/null || true)"
              if [ -n "$_LB_LOCK_OWNER" ] && kill -0 "$_LB_LOCK_OWNER" 2>/dev/null; then
                echo "Timed out waiting for active Python environment lock: $_LB_LOCK_DIR" >&2
                exit 1
              fi
              echo "Timed out waiting for Python environment lock, clearing stale lock: $_LB_LOCK_DIR" >&2
              rm -rf "$_LB_LOCK_DIR" 2>/dev/null || true
              if mkdir "$_LB_LOCK_DIR" 2>/dev/null; then
                break
              fi
              echo "Timed out waiting for Python environment lock: $_LB_LOCK_DIR" >&2
              exit 1
            fi
            sleep 1
            _LB_LOCK_WAIT=$((_LB_LOCK_WAIT + 1))
          done
          printf '%s\n' "$$" > "$_LB_LOCK_DIR/pid" 2>/dev/null || true

          _lb_cleanup_lock() {{
            rm -rf "$_LB_LOCK_DIR" >/dev/null 2>&1 || true
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
            "$_LB_SYSTEM_PYTHON" -m venv "$_LB_VENV_DIR"
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


__all__ = [
    'PYTHON_MANIFEST_FILES',
    'list_python_manifest_files',
    'normalize_host_path',
    'should_prepare_python_env',
    'wrap_python_command_with_env',
]
