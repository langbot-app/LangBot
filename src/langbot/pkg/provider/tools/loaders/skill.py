from __future__ import annotations

import typing

if typing.TYPE_CHECKING:
    from langbot_plugin.api.entities.events import pipeline_query
    from ....core import app

# Tool name exposed to LLM
SKILL_EXEC_TOOL_NAME = 'skill_exec'

# Key used to store activated skills in query.variables
ACTIVATED_SKILLS_KEY = '_activated_skills'


class SkillToolLoader:
    """Handles the skill_exec generic sandbox tool.

    Instead of registering individual tools per skill script, this loader
    exposes a single ``skill_exec`` tool that lets the LLM run arbitrary
    commands inside an activated skill's sandboxed directory.
    """

    ap: app.Application

    def __init__(self, ap: app.Application):
        self.ap = ap

    async def initialize(self):
        pass

    def has_tool(self, name: str, query: pipeline_query.Query) -> bool:
        """Return True when *name* is ``skill_exec`` and at least one skill is activated."""
        return name == SKILL_EXEC_TOOL_NAME and bool(self._get_activated_skills(query))

    async def invoke_tool(self, name: str, parameters: dict, query: pipeline_query.Query) -> typing.Any:
        """Execute a command in the activated skill's sandbox."""
        if name != SKILL_EXEC_TOOL_NAME:
            raise ValueError(f'Unknown skill tool: {name}')

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
                f'Skill "{skill_name}" is not activated for this query. '
                f'Activated skills: {activated_names}'
            )

        return await self.ap.box_service.execute_in_skill_sandbox(
            skill_data=skill_data,
            command=command,
            query=query,
        )

    def _get_activated_skills(self, query: pipeline_query.Query) -> dict:
        """Get the activated skills dict from query.variables."""
        if query.variables is None:
            return {}
        return query.variables.get(ACTIVATED_SKILLS_KEY, {})

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
