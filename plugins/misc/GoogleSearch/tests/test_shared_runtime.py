"""Shared-runtime behaviour tests for the GoogleSearch tool.

One ``Google`` component object is driven through two distinct installation
bindings. Configuration and the installation binding are supplied per
invocation through the SDK's task-local invocation context (``bind_invocation``)
exactly as the stateless component model requires; the component must build each
outbound request from the *current* invocation's config and must not retain any
tenant data on itself.

The blocking test stubs the outbound HTTP call (both the synchronous ``httpx.get``
seam used before the fix and the asynchronous ``httpx.AsyncClient`` seam used
now) and asserts that another coroutine keeps running while the request is in
flight. Before the fix the synchronous ``httpx.get`` stalled the loop, so the
ticker made no progress.
"""

from __future__ import annotations

import asyncio
import json
import sys
import time
import unittest
from pathlib import Path
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from langbot_plugin.api.proxies.invocation import bind_invocation  # noqa: E402
from langbot_plugin.entities.io.context import InstallationBinding  # noqa: E402

import components.tools.google as google_module  # noqa: E402


def binding(owner: str) -> InstallationBinding:
    return InstallationBinding(
        instance_uuid=f"instance-{owner}",
        workspace_uuid=f"workspace-{owner}",
        placement_generation=1,
        installation_uuid=f"install-{owner}",
        runtime_revision=1,
        artifact_digest="a" * 64,
    )


class _FakePlugin:
    """Minimal shared plugin object carrying the runtime handler identity.

    ``get_config`` returns a process-wide fallback (as a dedicated-mode plugin
    would). A stateless component must ignore it while an invocation config is
    bound; the tests assert the invocation config wins.
    """

    def __init__(self) -> None:
        self.plugin_runtime_handler = object()

    def get_config(self) -> dict:
        return {"api_key": "key-plugin-default"}


class _FakeResponse:
    def __init__(self, payload: dict) -> None:
        self._payload = payload

    def raise_for_status(self) -> None:
        pass

    def json(self) -> dict:
        return self._payload


class _RecordingAsyncClient:
    """Async stand-in for httpx.AsyncClient used by the fixed code path."""

    calls: list[dict] = []
    delay = 0.0

    def __init__(self, *args, **kwargs) -> None:
        pass

    async def __aenter__(self) -> "_RecordingAsyncClient":
        return self

    async def __aexit__(self, *exc) -> bool:
        return False

    async def get(self, url, params=None, **kwargs) -> _FakeResponse:
        if self.delay:
            await asyncio.sleep(self.delay)
        type(self).calls.append({"url": url, "params": dict(params or {})})
        return _FakeResponse({"organic_results": [{"title": "t", "link": "l", "snippet": "s"}]})


def _sync_blocking_get(url, params=None, **kwargs):
    """The pre-fix seam: a synchronous, loop-blocking request."""

    _sync_get_calls.append({"url": url, "params": dict(params or {})})
    time.sleep(0.3)
    return _FakeResponse({"organic_results": []})


_sync_get_calls: list[dict] = []


class GoogleSharedRuntimeTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.tool = google_module.Google()
        self.plugin = _FakePlugin()
        self.tool.plugin = self.plugin
        self.handler = self.plugin.plugin_runtime_handler
        _RecordingAsyncClient.calls = []
        _RecordingAsyncClient.delay = 0.0
        _sync_get_calls.clear()

    def _drive(self, owner: str, api_key: str, query: str):
        """Run one invocation for ``owner`` with its own config and binding."""

        return bind_invocation(
            self.handler,
            config={"api_key": api_key},
            binding=binding(owner),
        )

    async def test_request_uses_current_invocation_config(self) -> None:
        with mock.patch.object(google_module.httpx, "AsyncClient", _RecordingAsyncClient), \
             mock.patch.object(google_module.httpx, "get", _sync_blocking_get):
            with self._drive("a", "key-owner-a", "query-a"):
                result_a = await self.tool.call({"query": "query-a"})
            with self._drive("b", "key-owner-b", "query-b"):
                result_b = await self.tool.call({"query": "query-b"})

        self.assertEqual([c["params"]["api_key"] for c in _RecordingAsyncClient.calls],
                         ["key-owner-a", "key-owner-b"])
        self.assertEqual([c["params"]["q"] for c in _RecordingAsyncClient.calls],
                         ["query-a", "query-b"])
        self.assertEqual(result_a["organic_results"][0]["title"], "t")
        self.assertEqual(result_b["organic_results"][0]["title"], "t")

        # No per-tenant state retained on the shared component object.
        self.assertLessEqual(set(vars(self.tool)), {"plugin"})
        self.assertNotIn("key-owner-a", repr(vars(self.tool)))
        self.assertNotIn("key-owner-b", repr(vars(self.tool)))

    async def test_handler_does_not_block_event_loop(self) -> None:
        _RecordingAsyncClient.delay = 0.3

        ticks = [0]
        stop = asyncio.Event()

        async def ticker() -> None:
            while not stop.is_set():
                ticks[0] += 1
                await asyncio.sleep(0.01)

        ticker_task = asyncio.create_task(ticker())
        with mock.patch.object(google_module.httpx, "AsyncClient", _RecordingAsyncClient), \
             mock.patch.object(google_module.httpx, "get", _sync_blocking_get):
            with self._drive("a", "key-owner-a", "query-a"):
                await self.tool.call({"query": "query-a"})

        progressed = ticks[0]
        stop.set()
        await ticker_task

        # Pre-fix assertion: the synchronous httpx.get stalled the loop, so
        # `progressed` was 0 and the request went through the sync seam.
        self.assertGreaterEqual(progressed, 3, "event loop stalled during the outbound request")
        self.assertEqual(_sync_get_calls, [], "request must not use the blocking seam")


if __name__ == "__main__":
    unittest.main()
