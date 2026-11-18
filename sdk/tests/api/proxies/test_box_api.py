from unittest.mock import AsyncMock, MagicMock
import pytest

from langbot_plugin.api.entities.builtin.runner.box import BoxFile
from langbot_plugin.api.entities.builtin.runner.errors import AgentAPIException
from langbot_plugin.api.proxies.runner import RunnerAPIProxy
from langbot_plugin.api.proxies.runner.common import PermissionDeniedError
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
@pytest.mark.parametrize("use_shared_api", [False, True])
async def test_context_explicit_export_preserves_paths_warning_and_cancellation(
    use_shared_api,
):
    ctx = create_mock_context()
    handler = MagicMock()
    handler.call_action = AsyncMock(
        return_value={
            "items": [{"id": "file", "name": "answer.txt", "type": "File", "size": 4}],
            "warning": "Files accepted, but cleanup failed; do not repeat delivery.",
        }
    )
    ctx._api = RunnerAPIProxy(ctx=ctx, plugin_runtime_handler=handler)
    with bind_invocation(handler, ctx.api):
        api = LangBotAPIProxy(handler) if use_shared_api else ctx
        files = await api.export_box_files(["/workspace/artifacts/answer.txt"])
    assert len(files) == 1 and files[0].id == "file"
    assert files[0].warning == handler.call_action.return_value["warning"]
    assert handler.call_action.await_args.args[:2] == (
        Action.EXPORT_BOX_FILES,
        {"run_id": ctx.run_id, "paths": ["/workspace/artifacts/answer.txt"]},
    )
    assert handler.call_action.await_args.kwargs["cancel_peer_on_cancel"] is True


@pytest.mark.asyncio
async def test_run_file_content_and_commit_keep_handles_and_invocation_scope():
    ctx = create_mock_context()
    ctx.context.available_apis.box = True
    contents = [
        {"type": "text", "text": "metadata"},
        {"type": "image_base64", "image_base64": "data:image/png;base64,aGk="},
    ]
    file_id = "00000000-0000-4000-8000-000000000001"
    metadata = {
        "id": file_id,
        "name": "answer.png",
        "type": "Image",
        "size": 2,
        "artifact_id": "durable-artifact-id",
        "mime_type": "image/png",
        "digest": "sha256:digest",
        "lifecycle": "durable",
        "expires_at": None,
    }
    handler = MagicMock()
    handler.call_action = AsyncMock(
        side_effect=[{"contents": contents}, {"items": [metadata]}]
    )
    ctx._api = RunnerAPIProxy(ctx=ctx, plugin_runtime_handler=handler)
    shared = LangBotAPIProxy(handler)
    with bind_invocation(handler, ctx.api):
        assert (
            await shared.read_run_file(
                file_id,
                mode="native",
                offset=3,
                max_chars=100,
                page_start=2,
                page_end=3,
            )
            == contents
        )
    assert handler.call_action.await_args.args[1] == {
        "run_id": ctx.run_id,
        "file_id": file_id,
        "mode": "native",
        "offset": 3,
        "max_chars": 100,
        "page_start": 2,
        "page_end": 3,
    }
    files = await ctx.commit_run_files([file_id])
    assert files == [BoxFile.model_validate(metadata)]
    assert files[0].id == file_id
    assert handler.call_action.await_args.args[:2] == (
        Action.COMMIT_RUN_FILES,
        {"run_id": ctx.run_id, "file_ids": [file_id]},
    )
    for call in handler.call_action.await_args_list:
        assert call.args[2] > 0
        assert call.kwargs["cancel_peer_on_cancel"] is True


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "method,args", [("read_run_file", ("file-1",)), ("commit_run_files", (["file-1"],))]
)
async def test_run_file_operations_require_box_grant_and_valid_response(method, args):
    ctx = create_mock_context()
    handler = MagicMock()
    handler.call_action = AsyncMock(return_value={})
    proxy = RunnerAPIProxy(ctx=ctx, plugin_runtime_handler=handler)
    with pytest.raises(PermissionDeniedError):
        await getattr(proxy, method)(*args)
    handler.call_action.assert_not_called()
    ctx.context.available_apis.box = True
    with pytest.raises(AgentAPIException) as error:
        await getattr(proxy, method)(*args)
    assert error.value.error.code == "host.malformed_response"


def test_legacy_box_file_shape_defaults_new_metadata():
    file = BoxFile(id="file-1", name="answer.txt", type="File", size=2)
    assert file.id == "file-1"
    assert file.artifact_id is None
    assert file.mime_type is None
    assert file.digest is None
    assert file.lifecycle is None
    assert file.expires_at is None
