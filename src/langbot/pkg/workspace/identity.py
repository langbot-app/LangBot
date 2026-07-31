from __future__ import annotations

import uuid


_INSTANCE_PREFIX = "instance_"
_WORKSPACE_IDENTITY_NAMESPACE = uuid.UUID("8ea04f29-8528-4cc3-bb28-30a838c89d76")


def workspace_uuid_from_instance_id(instance_id: str) -> str:
    """Return the stable OSS Workspace UUID for a persisted instance identity."""
    value = instance_id.strip()
    if not value:
        raise ValueError("LangBot instance identity is empty")

    candidate = value[len(_INSTANCE_PREFIX) :] if value.startswith(_INSTANCE_PREFIX) else value
    try:
        return str(uuid.UUID(candidate))
    except ValueError:
        return str(uuid.uuid5(_WORKSPACE_IDENTITY_NAMESPACE, value))
