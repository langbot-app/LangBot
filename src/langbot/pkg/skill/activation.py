from __future__ import annotations

import typing

from ..provider.tools.loaders import skill as skill_loader
from ..api.http.context import ExecutionContext

if typing.TYPE_CHECKING:
    from ..core import app
    import langbot_plugin.api.entities.builtin.pipeline.query as pipeline_query


# Skill activation is now handled through Tool Call mechanism (activate tool).
# This file is kept for potential future extensions but the text marker
# detection mechanism has been removed.


def register_activated_skill(
    ap: app.Application,
    query: pipeline_query.Query,
    skill_name: str,
) -> bool:
    """Register an activated skill for sandbox mount path resolution.

    This is called by the activate tool when a skill is activated via Tool Call.
    """
    skill_mgr = getattr(ap, 'skill_mgr', None)
    if skill_mgr is None:
        return False

    execution_context = ExecutionContext(
        instance_uuid=str(getattr(query, 'instance_uuid', '') or ''),
        workspace_uuid=str(getattr(query, 'workspace_uuid', '') or ''),
        placement_generation=getattr(query, 'placement_generation', 0) or 0,
        bot_uuid=getattr(query, 'bot_uuid', None),
        pipeline_uuid=getattr(query, 'pipeline_uuid', None),
        query_uuid=getattr(query, 'query_uuid', None),
    )
    skill_data = skill_mgr.get_skill_by_name(execution_context, skill_name)
    if skill_data is None:
        return False

    skill_loader.register_activated_skill(query, skill_data)
    return True
