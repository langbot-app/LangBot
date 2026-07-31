from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class WorkspaceExecutionBinding:
    """Core-neutral binding for one validated Workspace execution generation."""

    instance_uuid: str
    workspace_uuid: str
    placement_generation: int
    write_fenced: bool
    state: str
