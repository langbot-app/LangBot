from __future__ import annotations

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

        return await self.ap.box_service.execute_in_skill_sandbox(
            skill_data=skill_data,
            command=command,
            query=query,
        )

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
