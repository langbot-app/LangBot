"""Run with: python -m unittest discover -s tests -v (SDK installed)."""

import asyncio
import json
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

from components.runner.community import CommunityProcessor
from components.runner.observer import ObserverProcessor
from langbot_plugin.api.definition.components.runner import RunnerContext
from langbot_plugin.api.proxies.langbot_api import LangBotAPIProxy

ROOT = Path(__file__).resolve().parents[1]


def run_context(*, run_id, config, event):
    return RunnerContext.model_validate(
        {
            "run_id": run_id,
            "trigger": {"type": event.data["type"]},
            "event": {
                "event_id": run_id,
                "event_type": event.data["type"],
                "source": "test",
                "data": event.data,
            },
            "input": {},
            "delivery": {"surface": "test"},
            "resources": {},
            "runtime": {},
            "config": config,
        }
    )


class ProcessorTests(unittest.IsolatedAsyncioTestCase):
    async def execute(self, filename, *, component=None, config=None, fail_lookup=False):
        component = component or CommunityProcessor()
        if not component.registered_handlers:
            await component.initialize()
        payload = json.loads((ROOT / "examples" / filename).read_text())

        async def call_tool(tool, parameters):
            if fail_lookup and tool != "event_reply":
                raise RuntimeError("Adapter does not support lookup")
            return {"ok": True, "mock": True, "delivery": "simulated"}

        api = SimpleNamespace(
            call_tool=AsyncMock(side_effect=call_tool),
            list_tools=AsyncMock(return_value=[{"name": "event_get_actor"}, {"name": "event_get_group"}]),
        )
        component.get_run_api = Mock(return_value=api)
        component.plugin = LangBotAPIProxy(component._plugin_runtime_handler)
        ctx = run_context(
            run_id=filename,
            config={"delay_ms": 0, **(config or {})},
            event=SimpleNamespace(data={"type": payload["event_type"], **payload["data"]}),
        )
        results = [item async for item in component.invoke(ctx)]
        return results, api

    async def test_all_success_examples_complete_once(self):
        scenarios = json.loads((ROOT / "examples/scenarios.json").read_text())
        for scenario in scenarios:
            if scenario["expect_error"]:
                continue
            with self.subTest(scenario=scenario["file"]):
                component = ObserverProcessor() if scenario["component"] == "observer" else CommunityProcessor()
                results, _ = await self.execute(scenario["file"], component=component)
                self.assertEqual(sum(r.type == "run.completed" for r in results), 1)

    async def test_welcome_has_three_traced_actions(self):
        results, api = await self.execute("01-member-joined.json")
        self.assertEqual(
            [c.args[0] for c in api.call_tool.await_args_list],
            ["event_get_actor", "event_get_group", "event_reply"],
        )
        starts = [r.data["tool_call_id"] for r in results if r.type == "tool.call.started"]
        ends = [r.data["tool_call_id"] for r in results if r.type == "tool.call.completed"]
        self.assertEqual(starts, ends)
        self.assertEqual(len(set(starts)), 3)

    async def test_lookup_failure_is_logged_but_welcome_still_sends(self):
        results, api = await self.execute("01-member-joined.json", fail_lookup=True)
        self.assertEqual(api.call_tool.await_args_list[-1].args[0], "event_reply")
        self.assertTrue(any(r.data.get("level") == "warning" for r in results))
        self.assertEqual(sum(bool(r.data.get("error")) for r in results), 2)

    async def test_departure_configuration_changes_actions(self):
        _, silent = await self.execute("02-member-left.json")
        _, announce = await self.execute("02-member-left.json", config={"announce_departures": True})
        silent.call_tool.assert_not_called()
        announce.call_tool.assert_awaited_once()

    async def test_image_does_not_corrupt_command_text(self):
        _, api = await self.execute("11-echo-with-image.json")
        api.call_tool.assert_awaited_once_with("event_reply", {"text": "你好 Runner!"})

    async def test_failure_requires_opt_in_and_preserves_error_log(self):
        results, api = await self.execute("06-failure.json")
        self.assertEqual(results[-1].type, "run.completed")
        api.call_tool.assert_not_called()
        component = CommunityProcessor()
        await component.initialize()
        component.get_run_api = Mock(return_value=SimpleNamespace(call_tool=AsyncMock()))
        payload = json.loads((ROOT / "examples/06-failure.json").read_text())
        ctx = run_context(
            run_id="fail",
            config={"allow_demo_failure": True},
            event=SimpleNamespace(data={"type": payload["event_type"], **payload["data"]}),
        )
        emitted = []
        with self.assertRaisesRegex(RuntimeError, "intentional failure"):
            async for result in component.invoke(ctx):
                emitted.append(result)
        self.assertTrue(any(r.data.get("level") == "error" for r in emitted))
        self.assertFalse(any(r.type == "run.completed" for r in emitted))

    async def test_observer_preserves_custom_fields_without_tools(self):
        results, api = await self.execute(
            "10-observer-custom.json",
            component=ObserverProcessor(),
            config={"include_payload": True},
        )
        self.assertIn("release", "\n".join(r.data.get("text", "") for r in results))
        api.call_tool.assert_not_called()

    async def test_config_is_scoped_to_each_run(self):
        component = CommunityProcessor()
        await component.initialize()
        api = SimpleNamespace(
            call_tool=AsyncMock(return_value={"mock": True}),
            list_tools=AsyncMock(return_value=[{"name": "event_get_actor"}, {"name": "event_get_group"}]),
        )
        component.get_run_api = Mock(return_value=api)
        component.plugin = LangBotAPIProxy(component._plugin_runtime_handler)
        payload = json.loads((ROOT / "examples/01-member-joined.json").read_text())

        async def collect(greeting):
            ctx = run_context(
                run_id=greeting,
                config={"welcome_text": greeting},
                event=SimpleNamespace(data={"type": payload["event_type"], **payload["data"]}),
            )
            return [r async for r in component.invoke(ctx)]

        await asyncio.gather(collect("Welcome A"), collect("Welcome B"))
        replies = [c.args[1]["text"] for c in api.call_tool.await_args_list if c.args[0] == "event_reply"]
        self.assertCountEqual(replies, ["Alice，Welcome A", "Alice，Welcome B"])


if __name__ == "__main__":
    unittest.main()
