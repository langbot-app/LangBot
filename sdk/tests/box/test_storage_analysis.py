from __future__ import annotations

import logging
from types import SimpleNamespace

from langbot_plugin.box.runtime import BoxRuntime
from langbot_plugin.box.tenancy import box_namespace
from langbot_plugin.entities.io.context import ActionContext


async def test_box_storage_analysis_reports_workspace_mcp_without_skills(tmp_path):
    workspace_root = tmp_path / "workspaces"
    skills_root = tmp_path / "skills"
    runtime = BoxRuntime(logging.getLogger("test-box-storage"), backends=[])
    runtime.init(
        {
            "local": {
                "host_root": str(tmp_path),
                "default_workspace": str(workspace_root),
                "allowed_mount_roots": [str(tmp_path)],
            }
        }
    )
    context = ActionContext(
        instance_uuid="instance-a",
        workspace_uuid="workspace-a",
        placement_generation=3,
    )
    namespace = box_namespace(context)
    workspace = workspace_root / "tenants" / namespace
    mcp = workspace / ".mcp" / "server-a"
    inbox = workspace / "inbox"
    skills = skills_root / "tenants" / namespace
    mcp.mkdir(parents=True)
    inbox.mkdir()
    skills.mkdir(parents=True)
    (mcp / "cache.bin").write_bytes(b"mcp")
    (inbox / "message.txt").write_bytes(b"inbox")
    (skills / "SKILL.md").write_bytes(b"skill")

    result = await runtime.get_storage_analysis(context)

    directories = {item["key"]: item for item in result["directories"]}
    assert directories["workspace"]["size_bytes"] == 8
    assert directories["mcp"]["size_bytes"] == 3
    assert directories["mcp"]["parent_key"] == "workspace"
    assert directories["outbox"]["exists"] is False
    assert "skills" not in directories
    assert result["size_bytes"] == 8
    assert result["active_sessions"] == 0
    assert result["managed_processes"] == 0


def test_box_storage_analysis_aggregates_ephemeral_managed_process_sessions():
    session = SimpleNamespace(
        info=SimpleNamespace(host_path=None),
        managed_processes={"mcp-server": object()},
    )
    report = {
        "session_workspaces": {
            "exists": True,
            "size_bytes": 12_000,
            "file_count": 4,
        },
        "session_caches": {
            "exists": True,
            "size_bytes": 30_000,
            "file_count": 10,
        },
        "session_temp": {
            "exists": True,
            "size_bytes": 2_000,
            "file_count": 2,
        },
    }

    directories = BoxRuntime._aggregate_sandbox_storage([session], [report])

    by_key = {item["key"]: item for item in directories}
    assert by_key["session_workspaces"]["size_bytes"] == 12_000
    assert by_key["session_caches"]["scope"] == "sandbox_sessions"
    assert by_key["managed_process_workspaces"]["size_bytes"] == 12_000
    assert by_key["managed_process_workspaces"]["kind"] == "detail"
