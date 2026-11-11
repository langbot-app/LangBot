from __future__ import annotations

import re

from langbot_plugin.entities.io.context import ActionContext
from langbot_plugin.workspace import workspace_namespace


def box_namespace(action_context: ActionContext) -> str:
    """Return the persistent namespace for one Workspace.

    This namespace deliberately excludes ``placement_generation`` so durable
    Workspace data survives a placement hand-off.
    """

    context = ActionContext.model_validate(action_context)
    return workspace_namespace(context.instance_uuid, context.workspace_uuid)


def box_runtime_namespace(action_context: ActionContext) -> str:
    """Return the ephemeral runtime namespace for one Workspace placement."""

    context = ActionContext.model_validate(action_context)
    return f"{box_namespace(context)}-g{context.placement_generation}"


def namespace_session_id(action_context: ActionContext, session_id: str) -> str:
    """Map a logical session id into a placement-owned physical id."""

    logical_id = str(session_id or "").strip()
    if not logical_id:
        raise ValueError("Box session_id must not be empty")
    safe_id = re.sub(r"[^A-Za-z0-9_.-]+", "-", logical_id).strip("-")
    if not safe_id:
        raise ValueError("Box session_id must contain a valid character")
    return f"{box_runtime_namespace(action_context)}-{safe_id}"


def session_namespace_prefix(action_context: ActionContext) -> str:
    return f"{box_runtime_namespace(action_context)}-"


def workspace_session_namespace_prefix(action_context: ActionContext) -> str:
    """Return the prefix shared by every placement of one Workspace."""

    return f"{box_namespace(action_context)}-"


def session_belongs_to_placement(
    action_context: ActionContext,
    session_id: str,
) -> bool:
    """Return whether a physical session belongs to the exact placement."""

    physical_id = str(session_id or "").strip()
    prefix = session_namespace_prefix(action_context)
    return physical_id.startswith(prefix) and len(physical_id) > len(prefix)


def logical_session_id(action_context: ActionContext, session_id: str) -> str:
    """Return the caller-visible id for a Workspace-owned physical session.

    Values outside the exact placement namespace are preserved rather than
    exposed as another placement's logical id.
    """

    physical_id = str(session_id or "").strip()
    prefix = session_namespace_prefix(action_context)
    if physical_id.startswith(prefix):
        return physical_id[len(prefix) :]
    return physical_id
