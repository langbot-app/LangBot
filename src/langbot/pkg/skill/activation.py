from __future__ import annotations

from dataclasses import dataclass
import typing

import langbot_plugin.api.entities.builtin.resource.tool as resource_tool

from ..provider.tools.loaders import skill as skill_loader

if typing.TYPE_CHECKING:
    import langbot_plugin.api.entities.builtin.pipeline.query as pipeline_query
    from ..core import app


@dataclass
class PreparedSkillActivation:
    activated_skill_names: list[str]
    cleaned_content: str
    prompt: str


def _ensure_skill_exec_tool(query: pipeline_query.Query) -> None:
    if query.use_funcs is None:
        query.use_funcs = []

    if any(getattr(tool, 'name', None) == skill_loader.SKILL_EXEC_TOOL_NAME for tool in query.use_funcs):
        return

    query.use_funcs.append(
        resource_tool.LLMTool(
            name=skill_loader.SKILL_EXEC_TOOL_NAME,
            human_desc="Execute a command in the activated skill's sandbox",
            description=(
                "Execute a command in the activated skill's sandbox environment. "
                'The skill directory is mounted at /workspace with write access.'
            ),
            parameters={
                'type': 'object',
                'properties': {
                    'skill_name': {
                        'type': 'string',
                        'description': 'Name of the activated skill',
                    },
                    'command': {
                        'type': 'string',
                        'description': 'Shell command to run in the sandbox',
                    },
                },
                'required': ['skill_name', 'command'],
            },
            func=lambda: None,
        )
    )


def prepare_skill_activation(
    ap: app.Application,
    query: pipeline_query.Query,
    response_content: str | None,
) -> PreparedSkillActivation | None:
    """Prepare multi-skill activation state on the query.

    This resolves top-level activation markers, registers the activated skills
    for skill_exec, and returns the combined activation prompt plus cleaned
    response content.
    """
    if not response_content or not getattr(ap, 'skill_mgr', None):
        return None

    activated_skill_names = ap.skill_mgr.detect_skill_activations(response_content)
    if not activated_skill_names:
        return None

    prompt = ap.skill_mgr.build_activation_prompt_for_skills(activated_skill_names)
    if not prompt:
        return None

    for skill_name in activated_skill_names:
        skill_data = ap.skill_mgr.get_skill_by_name(skill_name)
        if skill_data:
            skill_loader.register_activated_skill(query, skill_data)

    _ensure_skill_exec_tool(query)

    return PreparedSkillActivation(
        activated_skill_names=activated_skill_names,
        cleaned_content=ap.skill_mgr.remove_activation_marker(response_content),
        prompt=prompt,
    )
