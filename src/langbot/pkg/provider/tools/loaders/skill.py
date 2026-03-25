from __future__ import annotations

import os
import re
import textwrap
import typing

if typing.TYPE_CHECKING:
    from ....core import app
    from langbot_plugin.api.entities.events import pipeline_query

ACTIVATED_SKILLS_KEY = '_activated_skills'
PIPELINE_BOUND_SKILLS_KEY = '_pipeline_bound_skills'
SKILL_MOUNT_PREFIX = '/workspace/.skills'
_SKILL_MOUNT_PATTERN = re.compile(r'/workspace/\.skills/([A-Za-z0-9_-]+)')
_PYTHON_SKILL_MANIFESTS = (
    'requirements.txt',
    'pyproject.toml',
    'setup.py',
    'setup.cfg',
)


def _normalize_host_path(path: str | None) -> str:
    if path is None:
        return ''
    stripped = str(path).strip()
    if not stripped:
        return ''
    return os.path.realpath(os.path.abspath(stripped))


def get_virtual_skill_mount_path(skill_name: str) -> str:
    return f'{SKILL_MOUNT_PREFIX}/{skill_name}'


def get_bound_skill_names(query: pipeline_query.Query) -> list[str] | None:
    if query.variables is None:
        return None

    bound_skills = query.variables.get(PIPELINE_BOUND_SKILLS_KEY)
    if bound_skills is None:
        return None
    if isinstance(bound_skills, list):
        return [str(item) for item in bound_skills]
    return None


def get_visible_skills(ap: app.Application, query: pipeline_query.Query) -> dict[str, dict]:
    skill_mgr = getattr(ap, 'skill_mgr', None)
    if skill_mgr is None:
        return {}

    visible_skills = getattr(skill_mgr, 'skills', {})
    bound_skills = get_bound_skill_names(query)
    if bound_skills is None:
        return visible_skills

    return {skill_name: skill_data for skill_name, skill_data in visible_skills.items() if skill_name in bound_skills}


def get_visible_skill(ap: app.Application, query: pipeline_query.Query, skill_name: str) -> dict | None:
    return get_visible_skills(ap, query).get(skill_name)


def get_activated_skills(query: pipeline_query.Query) -> dict[str, dict]:
    if query.variables is None:
        return {}

    activated = query.variables.get(ACTIVATED_SKILLS_KEY, {})
    if not isinstance(activated, dict):
        return {}
    return activated


def get_activated_skill(query: pipeline_query.Query, skill_name: str) -> dict | None:
    return get_activated_skills(query).get(skill_name)


def register_activated_skill(query: pipeline_query.Query, skill_data: dict) -> None:
    if query.variables is None:
        query.variables = {}

    activated = query.variables.setdefault(ACTIVATED_SKILLS_KEY, {})
    skill_name = str(skill_data.get('name', '') or '').strip()
    if skill_name and skill_name not in activated:
        activated[skill_name] = skill_data


def parse_skill_mount_path(sandbox_path: str) -> tuple[str | None, str]:
    normalized_path = str(sandbox_path or '/workspace').strip() or '/workspace'
    if normalized_path == SKILL_MOUNT_PREFIX:
        raise ValueError(f'Path must include a skill name under {SKILL_MOUNT_PREFIX}/<skill-name>.')
    prefix = f'{SKILL_MOUNT_PREFIX}/'
    if not normalized_path.startswith(prefix):
        return None, normalized_path

    remainder = normalized_path[len(prefix) :]
    skill_name, separator, tail = remainder.partition('/')
    if not skill_name:
        raise ValueError(f'Path must include a skill name under {SKILL_MOUNT_PREFIX}/<skill-name>.')

    rewritten_path = '/workspace'
    if separator:
        rewritten_path = f'/workspace/{tail}'
    return skill_name, rewritten_path


def resolve_virtual_skill_path(
    ap: app.Application,
    query: pipeline_query.Query,
    sandbox_path: str,
    *,
    include_visible: bool,
    include_activated: bool,
) -> tuple[dict | None, str]:
    skill_name, rewritten_path = parse_skill_mount_path(sandbox_path)
    if skill_name is None:
        return None, rewritten_path

    if include_activated:
        activated_skill = get_activated_skill(query, skill_name)
        if activated_skill is not None:
            return activated_skill, rewritten_path

    if include_visible:
        visible_skill = get_visible_skill(ap, query, skill_name)
        if visible_skill is not None:
            return visible_skill, rewritten_path

    activated_names = ', '.join(sorted(get_activated_skills(query).keys())) or 'none'
    visible_names = ', '.join(sorted(get_visible_skills(ap, query).keys())) or 'none'
    raise ValueError(
        f'Skill "{skill_name}" is not available at this path. '
        f'Activated skills: {activated_names}. Visible skills: {visible_names}.'
    )


def find_referenced_skill_names(text: str) -> list[str]:
    if not text:
        return []

    seen: list[str] = []
    for match in _SKILL_MOUNT_PATTERN.findall(text):
        if match not in seen:
            seen.append(match)
    return seen


def rewrite_command_for_skill_mount(command: str, skill_name: str) -> str:
    virtual_root = get_virtual_skill_mount_path(skill_name)
    rewritten = command.replace(f'{virtual_root}/', '/workspace/')
    return rewritten.replace(virtual_root, '/workspace')


def build_skill_session_id(skill_data: dict, query: pipeline_query.Query) -> str:
    skill_identifier = str(skill_data.get('name', 'unknown') or 'unknown')
    launcher_type = getattr(query, 'launcher_type', None)
    launcher_id = getattr(query, 'launcher_id', None)
    query_id = getattr(query, 'query_id', 'unknown')

    if launcher_type is not None and launcher_id is not None:
        return f'skill-{launcher_type}_{launcher_id}-{skill_identifier}'
    return f'skill-{query_id}-{skill_identifier}'


def should_prepare_skill_python_env(package_root: str | None) -> bool:
    normalized_root = _normalize_host_path(package_root)
    if not normalized_root:
        return False
    if os.path.isdir(os.path.join(normalized_root, '.venv')):
        return True
    return any(os.path.isfile(os.path.join(normalized_root, filename)) for filename in _PYTHON_SKILL_MANIFESTS)


def wrap_skill_command_with_python_env(command: str) -> str:
    bootstrap = textwrap.dedent(
        """
        set -e

        _LB_VENV_DIR="/workspace/.venv"
        _LB_META_DIR="/workspace/.langbot"
        _LB_META_FILE="$_LB_META_DIR/python-env.json"
        _LB_LOCK_DIR="$_LB_META_DIR/python-env.lock"
        _LB_TMP_DIR="/workspace/.tmp"
        _LB_PIP_CACHE_DIR="/workspace/.cache/pip"

        mkdir -p "$_LB_META_DIR" "$_LB_TMP_DIR" "$_LB_PIP_CACHE_DIR"
        export TMPDIR="$_LB_TMP_DIR"
        export TEMP="$_LB_TMP_DIR"
        export TMP="$_LB_TMP_DIR"
        export PIP_CACHE_DIR="$_LB_PIP_CACHE_DIR"

        _lb_python_meta() {
          python - <<'PY'
        import hashlib
        import json
        import os
        import sys

        root = "/workspace"
        digest = hashlib.sha256()
        manifest_files = []
        for rel in ("requirements.txt", "pyproject.toml", "setup.py", "setup.cfg"):
            path = os.path.join(root, rel)
            if not os.path.isfile(path):
                continue
            manifest_files.append(rel)
            with open(path, "rb") as handle:
                digest.update(rel.encode("utf-8"))
                digest.update(b"\0")
                digest.update(handle.read())
                digest.update(b"\0")

        print(
            json.dumps(
                {
                    "python_executable": sys.executable,
                    "python_version": list(sys.version_info[:3]),
                    "manifest_files": manifest_files,
                    "manifest_sha256": digest.hexdigest(),
                },
                sort_keys=True,
            )
        )
        PY
        }

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

          _lb_cleanup_lock() {
            rmdir "$_LB_LOCK_DIR" >/dev/null 2>&1 || true
          }
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

            if [ -f /workspace/requirements.txt ]; then
              "$_LB_VENV_DIR/bin/python" -m pip install -r /workspace/requirements.txt
            elif [ -f /workspace/pyproject.toml ] || [ -f /workspace/setup.py ] || [ -f /workspace/setup.cfg ]; then
              "$_LB_VENV_DIR/bin/python" -m pip install -e /workspace
            fi

            printf '%s' "$_LB_CURRENT_META" > "$_LB_META_FILE"
          fi
        fi

        export VIRTUAL_ENV="$_LB_VENV_DIR"
        export PATH="$_LB_VENV_DIR/bin:$PATH"
        """
    ).strip()

    return f'{bootstrap}\n\n{command}'
