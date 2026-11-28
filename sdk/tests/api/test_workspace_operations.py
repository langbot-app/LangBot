"""Tests for Workspace operations manifest validation, resources, and proxies."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, Mock

import pytest
from pydantic import ValidationError

from langbot_plugin.api.entities.builtin.runner.manifest import (
    RunnerPermissions,
)
from langbot_plugin.api.entities.permissions import PluginPermissions
from langbot_plugin.api.entities.builtin.runner.resources import (
    AgentResources,
    WorkspaceOperationResource,
)
from langbot_plugin.api.entities.builtin.runner.context import RunnerContext
from langbot_plugin.api.proxies.langbot_api import LangBotAPIProxy
from langbot_plugin.api.proxies.runner.api import RunnerAPIProxy
from langbot_plugin.entities.io.actions.enums import PluginToRuntimeAction
from langbot_plugin.entities.io.errors import ActionCallError


def test_plugin_permissions_workspace_operations_valid():
    perms = PluginPermissions(
        workspace_operations=["bot.list", "stats.basic", "pipeline.extensions.update"]
    )
    assert perms.workspace_operations == [
        "bot.list",
        "stats.basic",
        "pipeline.extensions.update",
    ]


def test_plugin_permissions_workspace_operations_default_empty():
    perms = PluginPermissions()
    assert perms.workspace_operations == []
    assert perms.capabilities == []


def test_plugin_permissions_workspace_operations_invalid_type():
    invalid_cases = ["bot.list", [1], [None]]
    for case in invalid_cases:
        with pytest.raises(ValidationError):
            PluginPermissions(workspace_operations=case)


def test_runner_permissions_cannot_declare_workspace_operations():
    with pytest.raises(ValidationError):
        RunnerPermissions(workspace_operations=["bot.list"])


def test_plugin_permissions_extra_forbid():
    with pytest.raises(ValidationError):
        PluginPermissions(unknown_field="not_allowed")


def test_runner_permissions_extra_forbid():
    with pytest.raises(ValidationError):
        RunnerPermissions(unknown_field="not_allowed")


def test_agent_resources_with_workspace_operations():
    res = AgentResources(
        workspace_operations=[
            WorkspaceOperationResource(
                id="bot.list",
                domain="bot",
                summary="List all bots",
                risk="read",
            )
        ]
    )
    assert len(res.workspace_operations) == 1
    assert res.workspace_operations[0].id == "bot.list"
    assert res.workspace_operations[0].risk == "read"


def test_agent_resources_without_workspace_operations_backward_compat():
    # When Core does not provide workspace_operations, it defaults to empty list
    res = AgentResources.model_validate({})
    assert res.workspace_operations == []


@pytest.mark.asyncio
async def test_workspace_proxy_list_success():
    handler = Mock()
    handler.call_action = AsyncMock(
        return_value={
            "operations": [
                {
                    "id": "bot.list",
                    "domain": "bot",
                    "risk": "read",
                    "side_effect": False,
                }
            ],
            "domains": [{"domain": "bot", "count": 1}],
        }
    )

    api = LangBotAPIProxy(handler)
    res = await api.workspace.list()

    assert "operations" in res
    assert len(res["operations"]) == 1
    assert res["operations"][0]["id"] == "bot.list"
    handler.call_action.assert_awaited_once_with(
        PluginToRuntimeAction.LIST_APPLICATION_OPERATIONS,
        {},
        timeout=180.0,
    )


@pytest.mark.asyncio
async def test_workspace_proxy_list_with_run_id():
    handler = Mock()
    handler.call_action = AsyncMock(return_value={"operations": [], "domains": []})

    ctx = Mock(spec=RunnerContext)
    ctx.run_id = "run-123"
    ctx.resources = AgentResources()
    ctx.runtime = Mock()
    ctx.runtime.deadline_at = None

    api = RunnerAPIProxy(ctx, handler)
    res = await api.workspace.list()

    assert res == {"operations": [], "domains": []}
    assert handler.call_action.await_count == 1
    call_args = handler.call_action.await_args
    assert call_args[0][0] == PluginToRuntimeAction.LIST_APPLICATION_OPERATIONS
    assert call_args[0][1] == {"run_id": "run-123"}


@pytest.mark.asyncio
async def test_workspace_proxy_list_error_does_not_raise():
    handler = Mock()
    handler.call_action = AsyncMock(
        side_effect=ActionCallError("Permission denied", {})
    )

    api = LangBotAPIProxy(handler)
    res = await api.workspace.list()

    assert res["operations"] == []
    assert res["domains"] == []
    assert "error" in res


@pytest.mark.asyncio
async def test_workspace_proxy_call_success():
    handler = Mock()
    handler.call_action = AsyncMock(
        return_value={
            "ok": True,
            "result": {"bots": [{"uuid": "b-1"}]},
            "operation": {"id": "bot.list", "risk": "read", "side_effect": False},
        }
    )

    api = LangBotAPIProxy(handler)
    res = await api.workspace.call("bot.list", limit=10)

    assert res["ok"] is True
    assert res["result"]["bots"][0]["uuid"] == "b-1"
    handler.call_action.assert_awaited_once_with(
        PluginToRuntimeAction.CALL_APPLICATION_OPERATION,
        {"operation_id": "bot.list", "arguments": {"limit": 10}},
        timeout=180.0,
    )


@pytest.mark.asyncio
async def test_workspace_proxy_call_with_run_id():
    handler = Mock()
    handler.call_action = AsyncMock(return_value={"ok": True, "result": {}})

    ctx = Mock(spec=RunnerContext)
    ctx.run_id = "run-456"
    ctx.resources = AgentResources()
    ctx.runtime = Mock()
    ctx.runtime.deadline_at = None

    api = RunnerAPIProxy(ctx, handler)
    res = await api.workspace.call("stats.basic")

    assert res["ok"] is True
    assert handler.call_action.await_count == 1
    call_args = handler.call_action.await_args
    assert call_args[0][0] == PluginToRuntimeAction.CALL_APPLICATION_OPERATION
    assert call_args[0][1] == {
        "operation_id": "stats.basic",
        "arguments": {},
        "run_id": "run-456",
    }


@pytest.mark.asyncio
async def test_workspace_proxy_call_error_does_not_raise():
    handler = Mock()
    handler.call_action = AsyncMock(
        side_effect=ActionCallError("Action failed", {"code": "not_found"})
    )

    api = LangBotAPIProxy(handler)
    res = await api.workspace.call("unknown.op")

    assert res["ok"] is False
    assert res["error"]["code"] == "not_found"


def test_example_runner_plugin_manifest_structure():
    import yaml

    example_dir = (
        Path(__file__).parent.parent.parent / "examples" / "workspace_runner_plugin"
    )
    manifest_file = example_dir / "manifest.yaml"
    runner_yaml = example_dir / "components" / "runner" / "default.yaml"

    assert manifest_file.exists()
    assert runner_yaml.exists()

    with open(manifest_file, encoding="utf-8") as manifest_stream:
        data = yaml.safe_load(manifest_stream)

    assert "spec" in data
    assert "permissions" in data["spec"]
    perms = data["spec"]["permissions"]
    assert "workspace_operations" in perms
    assert "bot.list" in perms["workspace_operations"]
    assert "stats.basic" in perms["workspace_operations"]

    validated_perms = PluginPermissions.model_validate(perms)
    assert "bot.list" in validated_perms.workspace_operations
    with open(runner_yaml, encoding="utf-8") as runner_stream:
        runner = yaml.safe_load(runner_stream)
    runner_permissions = runner["spec"]["permissions"]
    assert "workspace_operations" not in runner_permissions
    RunnerPermissions.model_validate(runner_permissions)
