"""Export errors are ordinary tool results; no completion recovery hook."""

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from langbot_plugin.api.entities.builtin.runner.box import BoxFile

from pkg.agent_core.langbot import LangBotToolExecutor
from pkg.agent_core.types import ToolCallRequest
from pkg.box import LocalAgentBox


@pytest.mark.asyncio
async def test_explicit_export_error_then_retry():
    ctx = SimpleNamespace(
        export_box_files=AsyncMock(
            side_effect=[RuntimeError("file missing: /out/a"), [BoxFile(id="file", name="a", type="File", size=1)]]
        ),
        delivery=SimpleNamespace(automatic_reply=True),
        reply_files=AsyncMock(),
    )
    box = LocalAgentBox(ctx, None)
    box.prepare = AsyncMock()
    executor = LangBotToolExecutor(None, set())
    assembly = SimpleNamespace(tools=[], tool_executor=executor)
    box.install_tool(assembly)
    request = ToolCallRequest.from_raw(
        {
            "id": "export",
            "type": "function",
            "function": {"name": "export_box_files", "arguments": '{"paths": ["/out/a"]}'},
        }
    )
    failed = await executor.execute(executor.prepare(request))
    assert "file missing" in failed.error
    assert not box.file_ids
    success = await executor.execute(executor.prepare(request))
    assert success.error is None
    assert box.file_ids == ["file"]
    assert not hasattr(box, "before_complete")
    assert not hasattr(box, "finish")


@pytest.mark.asyncio
@pytest.mark.parametrize("automatic", [False, True])
async def test_parallel_exports_keep_handles_and_delivery_unique(automatic):
    import asyncio

    file = BoxFile(id="file", name="a", type="File", size=1, warning="cleanup failed")
    ctx = SimpleNamespace(
        export_box_files=AsyncMock(return_value=[file]),
        delivery=SimpleNamespace(automatic_reply=automatic),
        reply_files=AsyncMock(),
    )
    box = LocalAgentBox(ctx, None)
    box.prepare = AsyncMock()
    results = await asyncio.gather(box.export_files(["/out/a"]), box.export_files(["/out/a"]))
    assert all(r["status"] == "accepted" and r["items"][0]["warning"] == "cleanup failed" for r in results)
    assert box.file_ids == (["file"] if automatic else [])
    assert ctx.reply_files.await_count == (0 if automatic else 1)
    assert not hasattr(box, "before_complete") and not hasattr(box, "finish")


@pytest.mark.asyncio
@pytest.mark.parametrize("failure", [RuntimeError("send failed"), PermissionError("no permission")])
async def test_platform_failure_is_fatal_and_cannot_reexport_or_redeliver(failure):
    from pkg.agent_core.types import NonRetryableToolError

    ctx = SimpleNamespace(
        export_box_files=AsyncMock(return_value=[BoxFile(id="file", name="a", type="File", size=1)]),
        delivery=SimpleNamespace(automatic_reply=False),
        reply_files=AsyncMock(side_effect=failure),
    )
    box = LocalAgentBox(ctx, None)
    box.prepare = AsyncMock()
    executor = LangBotToolExecutor(None, set())
    box.install_tool(SimpleNamespace(tools=[], tool_executor=executor))
    request = ToolCallRequest.from_raw(
        {"id": "call", "function": {"name": "export_box_files", "arguments": '{"paths":["/out/a"]}'}}
    )
    for _ in range(2):
        with pytest.raises(NonRetryableToolError, match="platform delivery failed"):
            await executor.execute(executor.prepare(request))
    ctx.export_box_files.assert_awaited_once_with(["/out/a"])
    ctx.reply_files.assert_awaited_once_with(["file"])


@pytest.mark.asyncio
async def test_invalid_host_response_is_not_a_generation_retry():
    from pkg.agent_core.types import NonRetryableToolError

    ctx = SimpleNamespace(
        export_box_files=AsyncMock(
            side_effect=RuntimeError(
                'ActionCallError: LANGBOT_EXPORT_V1:{"code":"box.export.invalid_response","message":"invalid attachment data","retryable":false}'
            )
        )
    )
    box = LocalAgentBox(ctx, None)
    box.prepare = AsyncMock()
    with pytest.raises(NonRetryableToolError, match="invalid attachment data"):
        await box.export_files(["/out/a"])


@pytest.mark.asyncio
async def test_legacy_sdk_fails_before_acquiring_a_box(monkeypatch):
    from langbot_plugin.api.entities.builtin.runner.context import RunnerContext

    async def old_export(self):
        raise AssertionError("must not be called")

    monkeypatch.setattr(RunnerContext, "export_box_files", old_export)
    api = SimpleNamespace(get_box_status=AsyncMock())
    with pytest.raises(RuntimeError, match="upgrade them together"):
        await LocalAgentBox(SimpleNamespace(), api).prepare()
    api.get_box_status.assert_not_called()
