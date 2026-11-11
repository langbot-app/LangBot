"""Focused coverage for the catalog-derived workspace domains."""

from __future__ import annotations

import importlib.util
import inspect
from pathlib import Path
import sys
from types import ModuleType
from typing import Literal, Union, get_args, get_origin

from typing_extensions import get_type_hints
from unittest.mock import AsyncMock, Mock

import pytest

from langbot_plugin.api.proxies import workspace_domains as domains
from langbot_plugin.api.proxies.workspace import WorkspaceOperationsProxy
from langbot_plugin.entities.io.actions.enums import PluginToRuntimeAction
from langbot_plugin.entities.io.errors import ActionCallError


@pytest.fixture
def generator():
    # sdk/ lives inside the LangBot monorepo; the generator is Core's script.
    path = (
        Path(__file__).resolve().parents[3] / "scripts/generate_plugin_workspace_api.py"
    )
    if not path.exists():
        pytest.skip("Generation tests require the LangBot repository checkout")
    spec = importlib.util.spec_from_file_location("workspace_generator", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def operation(operation_id, input_schema=None, output_schema=None, **overrides):
    return {
        "id": operation_id,
        "exposure": "all",
        "streaming": False,
        "principals": None,
        "input_schema": input_schema or {"type": "object", "properties": {}},
        "output_schema": output_schema or {"type": "null"},
        **overrides,
    }


def generated_module(generator, catalog, monkeypatch):
    module = ModuleType("generated_workspace_domains")
    monkeypatch.setitem(sys.modules, module.__name__, module)
    exec(generator.render(catalog), module.__dict__)
    return module


@pytest.mark.asyncio
@pytest.mark.parametrize("run_id", [None, "current-run"])
async def test_bot_list_uses_existing_call_and_optional_run_id(run_id):
    response = {"ok": True, "result": [{"uuid": "bot-id"}]}
    handler = Mock(call_action=AsyncMock(return_value=response))
    workspace = WorkspaceOperationsProxy(handler, run_id)
    assert await workspace.bot.list(include_secret=True) is response
    payload = {
        "operation_id": "bot.list",
        "arguments": {"include_secret": True},
    }
    if run_id is not None:
        payload["run_id"] = run_id
    handler.call_action.assert_awaited_once_with(
        PluginToRuntimeAction.CALL_APPLICATION_OPERATION, payload, timeout=180.0
    )


@pytest.mark.asyncio
async def test_llm_methods_and_parameter_forwarding():
    workspace = WorkspaceOperationsProxy(None)
    workspace.call = AsyncMock(return_value={"ok": True, "result": "new-model"})
    assert await workspace.model.llm.create(model_data={"name": "test"}) == {
        "ok": True,
        "result": "new-model",
    }
    workspace.call.assert_awaited_once_with(
        "model.llm.create",
        model_data={"name": "test"},
        auto_set_to_default_pipeline=True,
    )
    await workspace.model.llm.get(model_uuid="model-id")
    workspace.call.assert_awaited_with(
        "model.llm.get", model_uuid="model-id", include_secret=False
    )
    for method in ("list", "get", "create", "update", "delete", "test"):
        assert inspect.iscoroutinefunction(getattr(workspace.model.llm, method))
    assert inspect.iscoroutinefunction(workspace.model.llm.default.get)
    assert inspect.iscoroutinefunction(workspace.model.llm.starred.set)


@pytest.mark.asyncio
async def test_failure_envelope_is_preserved():
    failure = {"ok": False, "error": {"code": "forbidden", "message": "Denied"}}
    handler = Mock(call_action=AsyncMock(return_value=failure))
    workspace = WorkspaceOperationsProxy(handler)
    assert await workspace.bot.list() is failure
    handler.call_action.side_effect = ActionCallError(
        "Denied", data={"code": "permission_denied"}
    )
    result = await workspace.model.llm.get(model_uuid="id")
    assert result["ok"] is False
    assert result["error"]["code"] == "permission_denied"


@pytest.mark.asyncio
async def test_legacy_signatures_and_calls_are_unchanged():
    assert list(inspect.signature(WorkspaceOperationsProxy.list).parameters) == ["self"]
    signature = inspect.signature(WorkspaceOperationsProxy.call)
    assert list(signature.parameters) == [
        "self",
        "operation_id",
        "_timeout",
        "arguments",
    ]
    assert signature.parameters["_timeout"].default is None
    handler = Mock(call_action=AsyncMock(return_value={"ok": True, "result": None}))
    workspace = WorkspaceOperationsProxy(handler)
    await workspace.call("custom.future", _timeout=12, value=1)
    handler.call_action.assert_awaited_with(
        PluginToRuntimeAction.CALL_APPLICATION_OPERATION,
        {"operation_id": "custom.future", "arguments": {"value": 1}},
        timeout=12,
    )
    await workspace.list()
    handler.call_action.assert_awaited_with(
        PluginToRuntimeAction.LIST_APPLICATION_OPERATIONS, {}, timeout=180.0
    )


def test_real_signatures_and_return_types():
    workspace = WorkspaceOperationsProxy(None)
    bot_list = inspect.signature(workspace.bot.list)
    assert list(bot_list.parameters) == ["include_secret"]
    assert bot_list.parameters["include_secret"].default is False
    llm_get = inspect.signature(workspace.model.llm.get)
    assert llm_get.parameters["model_uuid"].default is inspect.Parameter.empty
    assert llm_get.parameters["model_uuid"].kind is inspect.Parameter.KEYWORD_ONLY
    assert get_type_hints(workspace.model.llm.get)["model_uuid"] is str
    json_value = get_type_hints(domains.OperationError)["details"]
    assert (
        get_type_hints(workspace.model.llm.create)["model_data"]
        == dict[str, json_value]
    )
    success, failure = get_args(get_type_hints(workspace.bot.list)["return"])
    assert get_origin(success) is domains.OperationSuccess
    assert get_args(success) == (list[dict[str, json_value]],)
    assert failure is domains.OperationFailure
    assert get_type_hints(domains.OperationFailure)["ok"] == Literal[False]
    assert get_type_hints(domains.OperationSuccess)["ok"] == Literal[True]
    assert domains.OperationSuccess.__required_keys__ == {"ok", "result"}
    assert domains.OperationFailure.__required_keys__ == {"ok", "error"}
    assert domains.OperationError.__required_keys__ == {"code", "message"}
    success, _ = get_args(get_type_hints(workspace.model.llm.get)["return"])
    assert get_args(success) == (Union[dict[str, json_value], None],)
    success, _ = get_args(get_type_hints(workspace.model.llm.create)["return"])
    assert get_args(success) == (str,)


def test_catalog_generation_is_current_and_stable(generator):
    pytest.importorskip("langbot.pkg.api.application.api")
    catalog = generator.plugin_catalog()
    text = generator.render(catalog)
    assert text == Path(domains.__file__).read_text(encoding="utf-8")
    assert text == generator.render(list(reversed(catalog)))
    workspace = WorkspaceOperationsProxy(None)
    for item in catalog:
        method = workspace
        for part in item["id"].split("."):
            method = getattr(method, generator.identifier(part))
        assert inspect.iscoroutinefunction(method), item["id"]
        signature = inspect.signature(method)
        schema = item["input_schema"]
        assert set(signature.parameters) == {
            generator.identifier(field) for field in schema.get("properties", {})
        }
        for field, value in schema.get("properties", {}).items():
            parameter = signature.parameters[generator.identifier(field)]
            if field in schema.get("required", []):
                assert parameter.default is inspect.Parameter.empty
            elif "default" in value:
                assert parameter.default == value["default"]
        assert "Any" not in str(get_type_hints(method))


def test_catalog_filters(generator):
    catalog = [
        operation("sample.public"),
        operation("sample.plugin", principals=["plugin"]),
        operation("sample.account", principals=["account"]),
        operation("sample.none", exposure="none"),
        operation("sample.assistant", exposure="assistant"),
        operation("sample.stream", streaming=True),
    ]
    assert [item["id"] for item in generator.eligible_operations(catalog)] == [
        "sample.plugin",
        "sample.public",
    ]


@pytest.mark.asyncio
async def test_keyword_aliases_nested_schemas_and_optional_fields(
    generator, monkeypatch
):
    input_schema = {
        "type": "object",
        "$defs": {
            "Entry": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "count": {"type": "integer"},
                },
                "required": ["name"],
            }
        },
        "properties": {
            "from": {"type": "string"},
            "class": {"type": "integer", "default": 7},
            "extra-value": {"type": "string"},
            "entries": {"type": "array", "items": {"$ref": "#/$defs/Entry"}},
        },
        "required": ["from", "entries"],
    }
    output_schema = {
        "type": "object",
        "properties": {
            "items": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "status": {"enum": ["ok", "failed"]},
                        "value": {"anyOf": [{"type": "integer"}, {"type": "null"}]},
                    },
                    "required": ["status"],
                },
            },
        },
        "required": ["items"],
    }
    module = generated_module(
        generator,
        [operation("sample.import", input_schema, output_schema)],
        monkeypatch,
    )
    workspace = Mock(call=AsyncMock(return_value={"ok": True, "result": {"items": []}}))
    method = module.WorkspaceDomains(workspace).sample.import_
    await method(from_="source", entries=[{"name": "first"}])
    workspace.call.assert_awaited_with(
        "sample.import",
        **{"from": "source", "entries": [{"name": "first"}], "class": 7},
    )
    await method(from_="source", entries=[], extra_value="explicit", class_=9)
    assert workspace.call.await_args.kwargs["extra-value"] == "explicit"
    assert "from_ -> from" in method.__doc__
    hints = get_type_hints(method)
    entry = get_args(hints["entries"])[0]
    assert entry.__required_keys__ == {"name"}
    assert entry.__optional_keys__ == {"count"}
    assert get_type_hints(entry, include_extras=True) == {
        "name": str,
        "count": module.NotRequired[int],
    }
    success, _ = get_args(hints["return"])
    output = get_args(success)[0]
    assert output.__required_keys__ == {"items"}
    item = get_args(get_type_hints(output)["items"])[0]
    assert item.__required_keys__ == {"status"}
    assert item.__optional_keys__ == {"value"}
    assert get_type_hints(item)["status"] == Literal["ok", "failed"]
    assert (
        get_type_hints(item, include_extras=True)["value"]
        == module.NotRequired[Union[int, None]]
    )


@pytest.mark.asyncio
async def test_workspace_language_get_calls_the_catalog_operation():
    response = {
        "ok": True,
        "result": {"language": "zh_Hans", "supported_languages": []},
    }
    handler = Mock(call_action=AsyncMock(return_value=response))
    workspace = WorkspaceOperationsProxy(handler)
    assert await workspace.workspace.language.get() is response
    handler.call_action.assert_awaited_once_with(
        PluginToRuntimeAction.CALL_APPLICATION_OPERATION,
        {"operation_id": "workspace.language.get", "arguments": {}},
        timeout=180.0,
    )
