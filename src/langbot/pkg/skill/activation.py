from __future__ import annotations

import typing

from ..provider.tools.loaders import skill as skill_loader

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

    skill_data = skill_mgr.get_skill_by_name(skill_name)
    if skill_data is None:
        return False

    skill_loader.register_activated_skill(query, skill_data)
    return True