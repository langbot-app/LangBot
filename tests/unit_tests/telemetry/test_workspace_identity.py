from __future__ import annotations

import uuid
from types import SimpleNamespace


def test_standard_oss_instance_id_aligns_to_embedded_uuid():
    from langbot.pkg.workspace.identity import workspace_uuid_from_instance_id

    instance_uuid = "a711d9e4-0953-443f-a0e9-7dd50193a79f"

    assert workspace_uuid_from_instance_id(instance_uuid) == instance_uuid
    assert workspace_uuid_from_instance_id(f"instance_{instance_uuid}") == instance_uuid


def test_custom_legacy_instance_id_maps_to_stable_valid_uuid():
    from langbot.pkg.workspace.identity import workspace_uuid_from_instance_id

    first = workspace_uuid_from_instance_id("instance_migration_test")
    second = workspace_uuid_from_instance_id("instance_migration_test")

    assert first == second
    assert str(uuid.UUID(first)) == first


def test_query_telemetry_identity_uses_execution_workspace_only():
    from langbot.pkg.telemetry.identity import workspace_identity

    identity = workspace_identity(SimpleNamespace(workspace_uuid="workspace-a", instance_uuid="instance-a"))

    assert identity == {"workspace_uuid": "workspace-a"}
