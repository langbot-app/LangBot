from unittest.mock import AsyncMock, MagicMock
import pytest

from langbot_plugin.api.proxies.runner import RunnerAPIProxy
from langbot_plugin.api.proxies.langbot_api import LangBotAPIProxy
from langbot_plugin.api.proxies.invocation import bind_invocation
from langbot_plugin.entities.io.actions.enums import PluginToRuntimeAction as Action
from tests.api.proxies.test_agent_run_api_proxy import create_mock_context


@pytest.mark.asyncio
async def test_common_box_api_keeps_invocation_authorization():
    ctx = create_mock_context()
    handler = MagicMock()
    handler.call_action = AsyncMock(
        return_value={"enabled": True, "available": True, "remaining": 0}
    )
    proxy = RunnerAPIProxy(ctx=ctx, plugin_runtime_handler=handler)
    shared = LangBotAPIProxy(handler)
    with bind_invocation(handler, proxy):
        result = await shared.get_box_status()
    assert result.remaining == 0
    assert handler.call_action.await_args.args[:2] == (
        Action.GET_BOX_STATUS,
        {"run_id": ctx.run_id},
    )


@pytest.mark.asyncio
async def test_context_box_operations_carry_run_and_explicit_file_refs():
    ctx = create_mock_context()
    handler = MagicMock()
    handler.call_action = AsyncMock(
        side_effect=[
            {"id": "box", "status": "ready"},
            {"box_id": "box", "inbox": "/in/run", "outbox": "/out/run"},
            {"items": []},
            {"items": []},
            {"result": {"ok": True}},
        ]
    )
    proxy = RunnerAPIProxy(ctx=ctx, plugin_runtime_handler=handler)
    await proxy.acquire_box("global")
    await proxy.bind_box("box")
    await proxy.import_box_attachments(["attachment-0"])
    await proxy.export_box_files(["/out/run/result.txt"])
    assert handler.call_action.await_args.args[1]["paths"] == ["/out/run/result.txt"]
    assert await proxy.reply_files(["file-1"]) == {"ok": True}
    for call in handler.call_action.await_args_list:
        assert call.args[1]["run_id"] == ctx.run_id
    assert handler.call_action.await_args_list[-1].args[1]["file_ids"] == ["file-1"]


@pytest.mark.asyncio
async def test_resource_api_without_invocation_does_not_invent_a_run():
    handler = MagicMock()
    handler.call_action = AsyncMock(return_value={"items": []})
    assert await LangBotAPIProxy(handler).list_boxes() == []
    assert handler.call_action.await_args.args[:2] == (Action.LIST_BOXES, {})


@pytest.mark.asyncio
async def test_context_explicit_export_preserves_paths_and_cleanup_warning():
    ctx = create_mock_context()
    handler = MagicMock()
    handler.call_action = AsyncMock(
        return_value={
            "items": [{"id": "file", "name": "answer.txt", "type": "File", "size": 4}],
            "warning": "Files accepted, but cleanup failed; do not repeat delivery.",
        }
    )
    ctx._api = RunnerAPIProxy(ctx=ctx, plugin_runtime_handler=handler)
    files = await ctx.export_box_files(["/workspace/artifacts/answer.txt"])
    assert len(files) == 1 and files[0].id == "file"
    assert files[0].warning == handler.call_action.return_value["warning"]
    assert handler.call_action.await_args.args[:2] == (
        Action.EXPORT_BOX_FILES,
        {"run_id": ctx.run_id, "paths": ["/workspace/artifacts/answer.txt"]},
    )
