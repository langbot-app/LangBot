"""SysStat: the command must not stall the shared event loop per invocation."""

from __future__ import annotations

import asyncio
import sys
import time
import unittest
from pathlib import Path
from types import SimpleNamespace

from langbot_plugin.api.proxies.invocation import bind_invocation
from langbot_plugin.entities.io.context import InstallationBinding

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import components.commands.sysstat as sysstat  # noqa: E402


def _binding(installation: str, *, workspace: str = "workspace-sysstat"):
    return InstallationBinding(
        instance_uuid="instance-1",
        workspace_uuid=workspace,
        installation_uuid=installation,
        runtime_revision=1,
        artifact_digest="c" * 64,
    )


class SysStatSharedRuntimeTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self._original_collect = sysstat._collect_status

    def tearDown(self) -> None:
        sysstat._collect_status = self._original_collect

    @staticmethod
    def _slow_collect(delay: float, marker: str):
        def collect() -> str:
            time.sleep(delay)
            return f"====系统状态====\n{marker}\n============"

        return collect

    async def _run(self, binding, command):
        async def collect():
            return [
                item
                async for item in command.registered_subcommands[""].subcommand(
                    command, SimpleNamespace()
                )
            ]

        with bind_invocation(SimpleNamespace(), binding=binding):
            return await collect()

    async def test_handler_offloads_collection_and_stays_responsive(self) -> None:
        from components.commands.sysstat import SysStat

        sysstat._collect_status = self._slow_collect(0.3, "CPU使用率: 42.00%")
        command = SysStat()

        task = asyncio.ensure_future(self._run(_binding("installation-sysstat-a"), command))
        ticks = 0
        while not task.done():
            await asyncio.sleep(0.02)
            ticks += 1
        results = await task

        # Pre-fix psutil.cpu_percent(interval=1) slept on the loop, so a
        # concurrent 20 ms ticker could not advance until the call returned.
        self.assertGreaterEqual(ticks, 5)
        self.assertIn("CPU使用率: 42.00%", results[0].text)
        self.assertIsNone(results[0].error)

    async def test_two_installations_share_one_command_object(self) -> None:
        from components.commands.sysstat import SysStat

        sysstat._collect_status = self._slow_collect(0.1, "CPU使用率: 7.00%")
        command = SysStat()

        results = await asyncio.gather(
            self._run(_binding("installation-sysstat-b"), command),
            self._run(_binding("installation-sysstat-c"), command),
        )

        for result in results:
            self.assertIn("CPU使用率: 7.00%", result[0].text)
            self.assertIsNone(result[0].error)


if __name__ == "__main__":
    unittest.main()
