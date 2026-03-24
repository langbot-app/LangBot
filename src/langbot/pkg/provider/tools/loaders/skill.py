from __future__ import annotations

import os
import textwrap
import typing
import langbot_plugin.api.entities.builtin.resource.tool as resource_tool

if typing.TYPE_CHECKING:
    from langbot_plugin.api.entities.events import pipeline_query
    from ....core import app

# Tool name exposed to LLM
SKILL_EXEC_TOOL_NAME = 'skill_exec'
SKILL_GET_TOOL_NAME = 'skill_get'

# Key used to store activated skills in query.variables
ACTIVATED_SKILLS_KEY = '_activated_skills'
PIPELINE_BOUND_SKILLS_KEY = '_pipeline_bound_skills'
_PYTHON_SKILL_MANIFESTS = (
    'requirements.txt',
    'pyproject.toml',
    'setup.py',
    'setup.cfg',
)


class SkillToolLoader:
    """Handles skill runtime tools.

    The runtime currently exposes:
    - ``skill_exec`` for executing commands in an activated skill sandbox
    - ``skill_get`` for fetching readable information about a visible skill
    """

    ap: app.Application

    def __init__(self, ap: app.Application):
        self.ap = ap

    async def initialize(self):
        pass

    def has_tool(self, name: str, query: pipeline_query.Query) -> bool:
        """Return True when a skill runtime tool is available for the current query."""
        if name == SKILL_EXEC_TOOL_NAME:
            return bool(self._get_activated_skills(query))
        if name == SKILL_GET_TOOL_NAME:
            return getattr(self.ap, 'skill_mgr', None) is not None and bool(self._get_visible_skills(query))
        return False

    async def invoke_tool(self, name: str, parameters: dict, query: pipeline_query.Query) -> typing.Any:
        """Execute a skill runtime tool."""
        if name == SKILL_EXEC_TOOL_NAME:
            return await self._invoke_skill_exec(parameters, query)
        if name == SKILL_GET_TOOL_NAME:
            return await self._invoke_skill_get(parameters, query)
        raise ValueError(f'Unknown skill tool: {name}')

    async def _invoke_skill_exec(self, parameters: dict, query: pipeline_query.Query) -> typing.Any:
        """Execute a command in the activated skill's sandbox."""

        skill_name = parameters.get('skill_name', '')
        command = parameters.get('command', '')

        if not skill_name:
            raise ValueError('skill_name is required')
        if not command:
            raise ValueError('command is required')

        activated = self._get_activated_skills(query)
        skill_data = activated.get(skill_name)
        if not skill_data:
            activated_names = ', '.join(activated.keys()) if activated else 'none'
            raise ValueError(
                f'Skill "{skill_name}" is not activated for this query. Activated skills: {activated_names}'
            )

        return await self._execute_in_skill_sandbox(skill_data, command, query)

    async def _invoke_skill_get(self, parameters: dict, query: pipeline_query.Query) -> typing.Any:
        """Return readable information about a visible skill."""
        skill_name = str(parameters.get('skill_name', '')).strip()
        if not skill_name:
            raise ValueError('skill_name is required')

        skill_data = self._get_visible_skills(query).get(skill_name)
        if not skill_data:
            visible_skill_names = ', '.join(sorted(self._get_visible_skills(query).keys())) or 'none'
            raise ValueError(
                f'Skill "{skill_name}" is not visible for this query. Visible skills: {visible_skill_names}'
            )

        return {
            'name': skill_data.get('name', ''),
            'display_name': skill_data.get('display_name', ''),
            'description': skill_data.get('description', ''),
            'type': skill_data.get('type', 'skill'),
            'instructions': skill_data.get('instructions', ''),
            'auto_activate': bool(skill_data.get('auto_activate', True)),
            'sandbox_timeout_sec': skill_data.get('sandbox_timeout_sec', 120),
            'sandbox_network': bool(skill_data.get('sandbox_network', False)),
        }

    def _get_activated_skills(self, query: pipeline_query.Query) -> dict:
        """Get the activated skills dict from query.variables."""
        if query.variables is None:
            return {}
        return query.variables.get(ACTIVATED_SKILLS_KEY, {})

    def _get_visible_skills(self, query: pipeline_query.Query) -> dict[str, dict]:
        """Get skills visible to the current query based on pipeline bindings."""
        skill_mgr = getattr(self.ap, 'skill_mgr', None)
        if skill_mgr is None:
            return {}

        visible_skills = skill_mgr.skills
        if query.variables is None:
            return visible_skills

        bound_skills = query.variables.get(PIPELINE_BOUND_SKILLS_KEY, None)
        if bound_skills is None:
            return visible_skills

        return {
            skill_name: skill_data
            for skill_name, skill_data in visible_skills.items()
            if skill_data.get('uuid') in bound_skills
        }

    async def shutdown(self):
        pass

    async def _execute_in_skill_sandbox(
        self,
        skill_data: dict,
        command: str,
        query: pipeline_query.Query,
    ) -> typing.Any:
        session_id = self._build_skill_session_id(skill_data, query)
        timeout_sec = skill_data.get('sandbox_timeout_sec', 120)
        network = 'on' if skill_data.get('sandbox_network', False) else 'off'
        package_root = skill_data.get('package_root')
        wrapped_command = command
        if self._should_prepare_skill_python_env(package_root):
            wrapped_command = self._wrap_skill_command_with_python_env(command)

        result = await self.ap.box_service.execute_spec_payload(
            {
                'cmd': wrapped_command,
                'workdir': '/workspace',
                'timeout_sec': timeout_sec,
                'network': network,
                'session_id': session_id,
                'host_path': package_root,
                'host_path_mode': 'rw',
            },
            query,
        )

        skill_mgr = getattr(self.ap, 'skill_mgr', None)
        if skill_mgr is not None:
            refresh_skill = getattr(skill_mgr, 'refresh_skill_from_disk', None)
            if callable(refresh_skill):
                refresh_skill(skill_data.get('name', ''))

        return result

    @staticmethod
    def _build_skill_session_id(skill_data: dict, query: pipeline_query.Query) -> str:
        skill_uuid = skill_data.get('uuid', 'unknown')
        launcher_type = getattr(query, 'launcher_type', None)
        launcher_id = getattr(query, 'launcher_id', None)
        query_id = getattr(query, 'query_id', 'unknown')

        if launcher_type is not None and launcher_id is not None:
            return f'skill-{launcher_type}_{launcher_id}-{skill_uuid}'
        return f'skill-{query_id}-{skill_uuid}'

    def _should_prepare_skill_python_env(self, package_root: str | None) -> bool:
        normalized_root = self._normalize_host_path(package_root)
        if not normalized_root:
            return False
        if os.path.isdir(os.path.join(normalized_root, '.venv')):
            return True
        return any(os.path.isfile(os.path.join(normalized_root, filename)) for filename in _PYTHON_SKILL_MANIFESTS)

    @staticmethod
    def _wrap_skill_command_with_python_env(command: str) -> str:
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
                    digest.update(b"\\0")
                    digest.update(handle.read())
                    digest.update(b"\\0")

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

    @staticmethod
    def _normalize_host_path(path: str | None) -> str:
        if path is None:
            return ''
        stripped = str(path).strip()
        if not stripped:
            return ''
        return os.path.realpath(os.path.abspath(stripped))


def register_activated_skill(
    query: pipeline_query.Query,
    skill_data: dict,
) -> None:
    """Register an activated skill on the query for skill_exec to use.

    Args:
        query: The current query object
        skill_data: The skill data dict (must contain name, package_root, sandbox_* config)
    """
    if query.variables is None:
        query.variables = {}

    activated = query.variables.setdefault(ACTIVATED_SKILLS_KEY, {})
    skill_name = skill_data.get('name', '')
    if skill_name and skill_name not in activated:
        activated[skill_name] = skill_data


def build_skill_get_tool() -> resource_tool.LLMTool:
    """Build the read-only tool for fetching skill details at runtime."""
    return resource_tool.LLMTool(
        name=SKILL_GET_TOOL_NAME,
        human_desc='Get details for a visible skill',
        description=(
            'Fetch the full instructions and metadata for a visible skill by name. '
            'Use this to inspect a skill before deciding whether to activate or follow it.'
        ),
        parameters={
            'type': 'object',
            'properties': {
                'skill_name': {
                    'type': 'string',
                    'description': 'Name of the skill to inspect.',
                },
            },
            'required': ['skill_name'],
            'additionalProperties': False,
        },
        func=lambda parameters: parameters,
    )
