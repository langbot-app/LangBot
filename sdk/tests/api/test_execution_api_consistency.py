"""Consistency test verifying ExecutionAPI catalog and SDK proxy entry points."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock, Mock

import pytest

from langbot_plugin.api.proxies.langbot_api import LangBotAPIProxy
from langbot_plugin.entities.io.actions.enums import (
    PluginToRuntimeAction,
    RuntimeToLangBotAction,
)


def _load_catalog() -> list[dict]:
    catalog_path = Path(__file__).parent.parent / "data" / "execution_api_catalog.json"
    assert catalog_path.exists(), f"Catalog file not found at {catalog_path}"
    with open(catalog_path, encoding="utf-8") as f:
        return json.load(f)


def test_catalog_has_all_operations():
    catalog = _load_catalog()
    assert len(catalog) == 80
    assert "execution.request_interaction" in {item["id"] for item in catalog}
    for item in catalog:
        assert item["id"].startswith("execution.")
        assert "input_schema" in item
        assert "output_schema" in item
        assert "scope" in item


def test_docs_table_matches_catalog():
    """The operation table in docs/execution_api.md must list exactly the catalog."""
    import re

    docs_path = Path(__file__).resolve().parents[2] / "docs" / "execution_api.md"
    text = docs_path.read_text(encoding="utf-8")
    rows = {
        match.group(1): (match.group(2), match.group(3), match.group(4))
        for match in re.finditer(
            r"^\| `(execution\.[a-z_]+)` \| `([a-z_]+)` \| (是|否) \| (是|否) \|",
            text,
            re.MULTILINE,
        )
    }
    catalog = {
        item["id"]: (
            item["scope"],
            "是" if item["side_effect"] else "否",
            "是" if item["streaming"] else "否",
        )
        for item in _load_catalog()
    }
    assert rows == catalog


def test_catalog_operations_map_to_sdk_action_enums():
    catalog = _load_catalog()
    all_enums = {e.value for e in PluginToRuntimeAction} | {
        e.value for e in RuntimeToLangBotAction
    }

    catalog_actions = {item["id"].replace("execution.", "") for item in catalog}
    missing = catalog_actions - all_enums
    assert not missing, f"Catalog operations missing from SDK action enums: {missing}"


def test_runtime_forwards_all_catalog_operations_and_storage_proxies():
    """Verify all 65 catalog actions have Runtime handlers and storage operations have dedicated proxy methods."""
    from langbot_plugin.runtime.io.handlers.plugin import PluginConnectionHandler

    catalog = _load_catalog()
    catalog_actions = {item["id"].replace("execution.", "") for item in catalog}
    storage_actions = {
        "set_binary_storage",
        "get_binary_storage",
        "delete_binary_storage",
        "get_binary_storage_keys",
    }
    non_storage_actions = catalog_actions - storage_actions

    runtime_handler = PluginConnectionHandler(Mock(), None)
    missing_from_runtime = non_storage_actions - set(runtime_handler.actions.keys())
    assert not missing_from_runtime, (
        f"Runtime handler missing actions: {missing_from_runtime}"
    )

    # Verify dedicated storage proxy methods exist on LangBotAPIProxy
    for method_name in [
        "set_plugin_storage",
        "get_plugin_storage",
        "delete_plugin_storage",
        "get_plugin_storage_keys",
        "set_workspace_storage",
        "get_workspace_storage",
        "delete_workspace_storage",
        "get_workspace_storage_keys",
    ]:
        assert hasattr(LangBotAPIProxy, method_name), (
            f"Missing storage proxy method: {method_name}"
        )


@pytest.mark.asyncio
async def test_execution_proxy_invoke_unary():
    handler = Mock()
    handler.call_action = AsyncMock(return_value={"version": "v4.11.2"})
    api = LangBotAPIProxy(handler)

    res = await api.execution.invoke("execution.get_langbot_version")
    assert res == {"version": "v4.11.2"}
    handler.call_action.assert_awaited_once_with(
        PluginToRuntimeAction.GET_LANGBOT_VERSION,
        {},
        timeout=180.0,
    )


@pytest.mark.asyncio
async def test_execution_proxy_invoke_without_prefix():
    handler = Mock()
    handler.call_action = AsyncMock(return_value={"version": "v4.11.2"})
    api = LangBotAPIProxy(handler)

    res = await api.execution.invoke("get_langbot_version")
    assert res == {"version": "v4.11.2"}
    handler.call_action.assert_awaited_once_with(
        PluginToRuntimeAction.GET_LANGBOT_VERSION,
        {},
        timeout=180.0,
    )


@pytest.mark.asyncio
async def test_execution_proxy_stream():
    async def dummy_generator(*args, **kwargs):
        yield {"chunk": {"text": "hello"}}
        yield {"chunk": {"text": " world"}}

    handler = Mock()
    handler.call_action_generator = dummy_generator
    api = LangBotAPIProxy(handler)

    chunks = []
    async for chunk in api.execution.stream(
        "execution.invoke_llm_stream",
        llm_model_uuid="model-1",
        messages=[],
    ):
        chunks.append(chunk)

    assert len(chunks) == 2
    assert chunks[0] == {"chunk": {"text": "hello"}}


@pytest.mark.asyncio
async def test_langbot_api_proxy_box_methods():
    handler = Mock()
    handler.call_action = AsyncMock(
        side_effect=lambda action, data, timeout=15.0: {
            PluginToRuntimeAction.BIND_BOX: {"box_id": "box-1", "outbox": "/out"},
            PluginToRuntimeAction.IMPORT_BOX_ATTACHMENTS: {
                "items": [
                    {
                        "id": "f-1",
                        "name": "test.txt",
                        "type": "file",
                        "size": 100,
                        "path": "/in/test.txt",
                    }
                ]
            },
            PluginToRuntimeAction.EXPORT_BOX_FILES: {
                "items": [
                    {
                        "id": "f-2",
                        "name": "out.txt",
                        "type": "file",
                        "size": 200,
                        "path": "/out/out.txt",
                    }
                ],
                "warning": None,
            },
        }.get(action, {})
    )

    api = LangBotAPIProxy(handler)

    binding = await api.bind_box("box-1")
    assert binding.box_id == "box-1"
    assert binding.outbox == "/out"

    imported = await api.import_box_attachments(["att-1"])
    assert len(imported) == 1
    assert imported[0].id == "f-1"

    exported = await api.export_box_files(["/out/out.txt"])
    assert len(exported) == 1
    assert exported[0].id == "f-2"


@pytest.mark.asyncio
async def test_workspace_operations_consistency():
    """Verify list_application_operations and call_application_operation consistency."""
    from langbot_plugin.runtime.io.handlers.plugin import PluginConnectionHandler

    assert (
        PluginToRuntimeAction.LIST_APPLICATION_OPERATIONS.value
        == "list_application_operations"
    )
    assert (
        PluginToRuntimeAction.CALL_APPLICATION_OPERATION.value
        == "call_application_operation"
    )

    runtime_handler = PluginConnectionHandler(Mock(), None)
    assert "list_application_operations" in runtime_handler.actions
    assert "call_application_operation" in runtime_handler.actions

    handler = Mock()
    handler.call_action = AsyncMock(
        side_effect=lambda action, data, timeout=180.0: {
            PluginToRuntimeAction.LIST_APPLICATION_OPERATIONS: {
                "operations": [{"id": "bot.list", "risk": "read"}],
                "domains": [{"domain": "bot"}],
            },
            PluginToRuntimeAction.CALL_APPLICATION_OPERATION: {
                "ok": True,
                "result": {"bots": []},
                "operation": {"id": "bot.list"},
            },
        }.get(action, {})
    )

    api = LangBotAPIProxy(handler)
    assert hasattr(api, "workspace")

    list_res = await api.workspace.list()
    assert len(list_res["operations"]) == 1
    assert list_res["operations"][0]["id"] == "bot.list"

    call_res = await api.workspace.call("bot.list")
    assert call_res["ok"] is True
    assert call_res["result"] == {"bots": []}
