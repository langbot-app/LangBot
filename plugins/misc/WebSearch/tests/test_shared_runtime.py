"""Shared-runtime behaviour tests for the WebSearch ``visit_web`` tool.

The plugin declares an empty ``spec.config``, so the two-binding test proves the
shared component object derives every invocation purely from its arguments and
retains no per-tenant state across bindings. The remaining tests cover the
blocking ``mux.process`` call (site adapters use the synchronous ``requests``
library) and the previous shared-default list in ``SiteAdapterBase.make_ret``.
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

import components.tools.visit_web as visit_web_module  # noqa: E402
from components.tools.sites import model as site_model  # noqa: E402


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
    def __init__(self) -> None:
        self.plugin_runtime_handler = object()

    def get_config(self) -> dict:
        return {}


class WebSearchSharedRuntimeTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.tool = visit_web_module.VisitWeb()
        self.plugin = _FakePlugin()
        self.tool.plugin = self.plugin
        self.handler = self.plugin.plugin_runtime_handler

    async def test_two_bindings_derive_result_from_invocation_only(self) -> None:
        seen: list[str] = []

        def fake_process(url: str, brief_len: int, **kwargs) -> str:
            seen.append(url)
            return f"page:{url}:{brief_len}"

        with mock.patch.object(visit_web_module, "process", fake_process):
            with bind_invocation(self.handler, config={}, binding=binding("a")):
                result_a = await self.tool.call({"url": "https://a.example/"})
            with bind_invocation(self.handler, config={}, binding=binding("b")):
                result_b = await self.tool.call({"url": "https://b.example/", "brief_len": 32})

        self.assertEqual(seen, ["https://a.example/", "https://b.example/"])
        self.assertEqual(result_a, "page:https://a.example/:4096")
        self.assertEqual(result_b, "page:https://b.example/:32")

        # Empty config + no per-tenant state retained on the shared object.
        self.assertLessEqual(set(vars(self.tool)), {"plugin"})
        self.assertNotIn("a.example", repr(vars(self.tool)))
        self.assertNotIn("b.example", repr(vars(self.tool)))

    async def test_handler_does_not_block_event_loop(self) -> None:
        def blocking_process(url: str, brief_len: int, **kwargs) -> str:
            time.sleep(0.3)
            return f"page:{url}"

        ticks = [0]
        stop = asyncio.Event()

        async def ticker() -> None:
            while not stop.is_set():
                ticks[0] += 1
                await asyncio.sleep(0.01)

        ticker_task = asyncio.create_task(ticker())
        with mock.patch.object(visit_web_module, "process", blocking_process):
            with bind_invocation(self.handler, config={}, binding=binding("a")):
                await self.tool.call({"url": "https://slow.example/"})

        progressed = ticks[0]
        stop.set()
        await ticker_task

        # Pre-fix assertion: the synchronous mux.process ran on the loop, so
        # `progressed` was 0.
        self.assertGreaterEqual(progressed, 3, "event loop stalled during page processing")

    def test_site_adapter_registry_holds_artifact_level_data_only(self) -> None:
        registry = site_model.__site_adapters__
        self.assertIsInstance(registry, list)
        self.assertIs(registry, site_model.__site_adapters__)
        for entry in registry:
            self.assertLessEqual(set(entry), {"regexp", "cls"})

    def test_make_ret_does_not_share_a_mutable_default(self) -> None:
        first = site_model.SiteAdapterBase.make_ret()
        first["content"]["briefs"].append("leaked-into-default")
        second = site_model.SiteAdapterBase.make_ret()

        # Pre-fix assertion: the shared `briefs=[]` default made `second` carry
        # the mutated list.
        self.assertEqual(second["content"]["briefs"], [])


if __name__ == "__main__":
    unittest.main()
