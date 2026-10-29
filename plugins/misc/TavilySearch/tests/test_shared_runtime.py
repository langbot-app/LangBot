"""Shared-runtime behaviour tests for the TavilySearch tool.

One ``TavilySearchTool`` object is driven through two distinct installation
bindings. The API key is read from the *current* invocation's installation
config (via the SDK task-local invocation context) and the vendor client is
built per call; the vendor's synchronous ``search`` must run off the shared
event loop.
"""

from __future__ import annotations

import asyncio
import sys
import time
import unittest
from pathlib import Path
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from langbot_plugin.api.proxies.invocation import bind_invocation  # noqa: E402
from langbot_plugin.entities.io.context import InstallationBinding  # noqa: E402

import components.tools.tavily_search as tavily_module  # noqa: E402


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
        return {"tavily_api_key": "key-plugin-default"}


class _FakeTavilyClient:
    """Synchronous vendor-client stand-in (same shape as TavilyClient.search)."""

    api_keys: list[str] = []
    searches: list[dict] = []
    delay = 0.0

    def __init__(self, api_key: str) -> None:
        type(self).api_keys.append(api_key)
        self.api_key = api_key

    def search(self, **kwargs) -> dict:
        type(self).searches.append(dict(kwargs))
        if self.delay:
            time.sleep(self.delay)
        return {
            "results": [{"title": f"result-{self.api_key}", "url": "u", "content": "c"}],
        }


class TavilySharedRuntimeTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.tool = tavily_module.TavilySearchTool()
        self.plugin = _FakePlugin()
        self.tool.plugin = self.plugin
        self.handler = self.plugin.plugin_runtime_handler
        _FakeTavilyClient.api_keys = []
        _FakeTavilyClient.searches = []
        _FakeTavilyClient.delay = 0.0

    def _drive(self, owner: str, api_key: str):
        return bind_invocation(
            self.handler,
            config={"tavily_api_key": api_key},
            binding=binding(owner),
        )

    async def test_request_uses_current_invocation_credentials(self) -> None:
        with mock.patch.object(tavily_module, "TavilyClient", _FakeTavilyClient):
            with self._drive("a", "key-owner-a"):
                result_a = await self.tool.call({"query": "query-a"}, None, 1)
            with self._drive("b", "key-owner-b"):
                result_b = await self.tool.call({"query": "query-b"}, None, 2)

        self.assertEqual(_FakeTavilyClient.api_keys, ["key-owner-a", "key-owner-b"])
        self.assertEqual([s["query"] for s in _FakeTavilyClient.searches],
                         ["query-a", "query-b"])
        self.assertIn("result-key-owner-a", result_a)
        self.assertIn("result-key-owner-b", result_b)

        # No per-tenant state retained on the shared component object.
        self.assertLessEqual(set(vars(self.tool)), {"plugin"})
        self.assertNotIn("key-owner-a", repr(vars(self.tool)))
        self.assertNotIn("key-owner-b", repr(vars(self.tool)))

    async def test_handler_does_not_block_event_loop(self) -> None:
        _FakeTavilyClient.delay = 0.3

        ticks = [0]
        stop = asyncio.Event()

        async def ticker() -> None:
            while not stop.is_set():
                ticks[0] += 1
                await asyncio.sleep(0.01)

        ticker_task = asyncio.create_task(ticker())
        with mock.patch.object(tavily_module, "TavilyClient", _FakeTavilyClient):
            with self._drive("a", "key-owner-a"):
                await self.tool.call({"query": "query-a"}, None, 1)

        progressed = ticks[0]
        stop.set()
        await ticker_task

        # Pre-fix assertion: the synchronous client.search ran on the loop, so
        # `progressed` was 0.
        self.assertGreaterEqual(progressed, 3, "event loop stalled during Tavily search")


if __name__ == "__main__":
    unittest.main()
