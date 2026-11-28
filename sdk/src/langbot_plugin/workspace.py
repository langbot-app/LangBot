"""Workspace identity helpers shared by independent SDK domains."""

from __future__ import annotations

import hashlib


def workspace_namespace(instance_uuid: str, workspace_uuid: str) -> str:
    """Return a stable, filesystem-safe namespace for one Workspace."""

    instance = str(instance_uuid or "").strip()
    workspace = str(workspace_uuid or "").strip()
    if not instance or not workspace:
        raise ValueError("Workspace namespace requires instance and Workspace UUIDs")
    digest = hashlib.sha256(f"{instance}\0{workspace}".encode("utf-8")).hexdigest()
    return f"ws-{digest[:24]}"


__all__ = ["workspace_namespace"]
