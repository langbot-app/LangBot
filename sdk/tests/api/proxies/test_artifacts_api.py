"""Artifact helpers preserve Workspace grants, binary contracts and cancellation."""

import asyncio
import base64
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from langbot_plugin.api.proxies.artifacts import ArtifactsProxy, ArtifactOperationError
from langbot_plugin.api.proxies.invocation import bind_invocation
from langbot_plugin.api.proxies.langbot_api import LangBotAPIProxy
from langbot_plugin.entities.io.actions.enums import PluginToRuntimeAction as Action

META = dict(
    id="art_" + "a" * 32,
    name="file.bin",
    mime_type="application/octet-stream",
    size=2,
    digest="a" * 64,
    source="upload",
    lifecycle="temporary",
)


@pytest.mark.asyncio
async def test_binary_roundtrip_uses_existing_workspace_envelope():
    handler = SimpleNamespace(
        call_action=AsyncMock(
            side_effect=[
                {"ok": True, "result": META},
                {
                    "ok": True,
                    "result": {
                        "metadata": META,
                        "content_base64": base64.b64encode(b"\x00\xff").decode(),
                    },
                },
            ]
        )
    )
    proxy = LangBotAPIProxy(handler).artifacts
    saved = await proxy.create("file.bin", b"\x00\xff")
    assert (await proxy.read(saved.id)).content == b"\x00\xff"
    args = handler.call_action.await_args_list[0]
    assert args.args[0] == Action.CALL_APPLICATION_OPERATION
    assert args.args[1]["arguments"]["content_base64"] == "AP8="
    assert "content" not in args.args[1]["arguments"]
    assert args.kwargs["cancel_peer_on_cancel"] is True


@pytest.mark.asyncio
async def test_shared_plugin_proxy_cannot_escape_active_run_or_invocation():
    handler = SimpleNamespace(
        call_action=AsyncMock(return_value={"ok": True, "result": META})
    )
    shared = LangBotAPIProxy(handler)
    with bind_invocation(handler, SimpleNamespace(run_id="run-a")):
        proxy = shared.artifacts
        await proxy.get(META["id"])
        assert handler.call_action.await_args.args[1]["run_id"] == "run-a"
    with pytest.raises(RuntimeError, match="ended"):
        await proxy.get(META["id"])
    with bind_invocation(handler, SimpleNamespace(run_id="run-b")):
        with pytest.raises(RuntimeError, match="another run"):
            await ArtifactsProxy(handler, "run-a").get(META["id"])


@pytest.mark.asyncio
async def test_old_host_and_authorization_fail_without_storage_fallback():
    handler = SimpleNamespace(
        call_action=AsyncMock(
            return_value={
                "ok": False,
                "error": {"code": "not_found", "message": "Operation not found"},
            }
        )
    )
    with pytest.raises(ArtifactOperationError) as failure:
        await ArtifactsProxy(handler).get(META["id"])
    assert failure.value.code == "not_found"
    handler.call_action.assert_awaited_once()


@pytest.mark.asyncio
async def test_artifact_limits_and_cancel_are_not_swallowed():
    handler = SimpleNamespace(call_action=AsyncMock(side_effect=asyncio.CancelledError))
    proxy = ArtifactsProxy(handler)
    with pytest.raises(ValueError):
        await proxy.create("big", b"x" * (256 * 1024 + 1))
    with pytest.raises(ValueError):
        await proxy.read(META["id"], max_bytes=True)
    handler.call_action.assert_not_awaited()
    with pytest.raises(asyncio.CancelledError):
        await proxy.read(META["id"])
