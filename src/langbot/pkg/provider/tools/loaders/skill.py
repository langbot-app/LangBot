from __future__ import annotations

import json
import typing

if typing.TYPE_CHECKING:
    from langbot_plugin.api.entities.events import pipeline_query
    from ....core import app

# Key used to store skill tool registry in query.variables
SKILL_TOOLS_REGISTRY_KEY = '_skill_tools_registry'


class SkillToolLoader:
    """Stateless skill tool loader that reads from query.variables.

    Skill tools are registered per-query to ensure isolation between conversations.
    The actual tool definitions are stored in query.variables[SKILL_TOOLS_REGISTRY_KEY].
    """

    ap: app.Application

    def __init__(self, ap: app.Application):
        self.ap = ap

    async def initialize(self):
        pass

    def has_tool(self, name: str, query: pipeline_query.Query) -> bool:
        """Check if a skill tool is registered for this query."""
        registry = self._get_registry(query)
        return name in registry

    async def invoke_tool(self, name: str, parameters: dict, query: pipeline_query.Query) -> typing.Any:
        """Invoke a skill tool via BoxService."""
        registry = self._get_registry(query)
        entry = registry.get(name)
        if not entry:
            raise ValueError(f'Skill tool not found: {name}')

        return await self.ap.box_service.execute_skill_tool(
            skill_data=entry['skill_data'],
            tool_def=entry['tool_def'],
            parameters=parameters,
            query=query,
        )

    def _get_registry(self, query: pipeline_query.Query) -> dict:
        """Get the skill tool registry from query.variables."""
        if query.variables is None:
            return {}
        return query.variables.get(SKILL_TOOLS_REGISTRY_KEY, {})

    async def shutdown(self):
        pass


def register_skill_tools(
    query: pipeline_query.Query,
    skill_tools: list[dict],
    skill_data: dict,
) -> None:
    """Register skill tools on a query for the SkillToolLoader to find.

    Args:
        query: The current query object
        skill_tools: List of namespaced skill tool definitions from SkillManager.get_skill_tools()
        skill_data: The skill data dict (needed for package_root, uuid, etc.)
    """
    if query.variables is None:
        query.variables = {}

    registry = query.variables.setdefault(SKILL_TOOLS_REGISTRY_KEY, {})

    for tool_def in skill_tools:
        namespaced_name = tool_def['name']  # Already namespaced by SkillManager
        if namespaced_name in registry:
            continue
        registry[namespaced_name] = {
            'tool_def': tool_def,
            'skill_data': skill_data,
        }
