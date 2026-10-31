"""Admin writes must be serialized with runtime writes of the same installation.

Review F1: ``update_settings`` / ``set_session_limit`` / ``reset_session`` /
``reset_all`` / ``delete_session`` mutated the cached state and then awaited
``persist`` without taking the installation lock that ``check_and_count`` holds.
``persist`` overwrites the whole row, so when a Host completes two in-flight
writes out of call order, the older snapshot lands last and silently rolls the
newer one back.

The synthetic Host below keeps ``SET_PLUGIN_STORAGE`` pending until the test
releases it, and releases newest-first, which is the order that makes an
unserialized pair lose the newer write. Pre-fix, an admin settings write and a
counter write of one installation both sit in the Host queue at once, and the
durable row ends up missing the session the counter write had recorded.
"""

from __future__ import annotations

import asyncio
import base64
import importlib.util
import json
import sys
from pathlib import Path

import pytest
from langbot_plugin.api.proxies.invocation import bind_invocation
from langbot_plugin.entities.io.actions.enums import PluginToRuntimeAction as Action
from langbot_plugin.entities.io.context import InstallationBinding

PLUGIN_ROOT = Path(__file__).resolve().parents[1]


def _load_plugin_module(module_name: str):
    """Load this plugin's ``main.py`` under a unique name."""

    spec = importlib.util.spec_from_file_location(module_name, PLUGIN_ROOT / "main.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


plugin_main = _load_plugin_module("daily_limit_plugin_serialization_under_test")
DailyLimitPlugin = plugin_main.DailyLimitPlugin

INSTANCE = "instance-1"
WORKSPACE = "workspace-1"

CONFIG = {
    "daily_limit": 50,
    "limit_message": "configured message",
    "silent_mode": False,
    "reset_timezone_offset": 8,
    "reset_hour": 0,
}


class ReorderingHost:
    """Host KV whose writes complete only when the test releases them."""

    def __init__(self) -> None:
        self.rows: dict[tuple[str, str, str], bytes] = {}
        self.pending: list[tuple[str, bytes, asyncio.Future]] = []
        self.commits: list[str] = []

    async def call_action(self, action, data):
        key = data.get("key", "")
        row = (INSTANCE, WORKSPACE, key)
        if action == Action.GET_PLUGIN_STORAGE:
            return {"value_base64": base64.b64encode(self.rows.get(row, b"")).decode()}
        if action == Action.SET_PLUGIN_STORAGE:
            value = base64.b64decode(data["value_base64"])
            future = asyncio.get_running_loop().create_future()
            self.pending.append((key, value, future))
            await future
            return {}
        if action == Action.DELETE_PLUGIN_STORAGE:
            self.rows.pop(row, None)
            return {}
        raise AssertionError(action)

    def release_newest(self) -> bool:
        """Commit the most recently issued pending write, as a busy Host can."""

        if not self.pending:
            return False
        key, value, future = self.pending.pop()
        self.rows[(INSTANCE, WORKSPACE, key)] = value
        self.commits.append(key)
        future.set_result(None)
        return True


class FlakyHost(ReorderingHost):
    """Host that fails exactly one write, the ``fail_on``-th, and accepts the rest."""

    def __init__(self, fail_on: int) -> None:
        super().__init__()
        self.fail_on = fail_on
        self.writes_seen = 0

    async def call_action(self, action, data):
        if action == Action.SET_PLUGIN_STORAGE:
            self.writes_seen += 1
            if self.writes_seen == self.fail_on:
                raise RuntimeError("host storage unavailable")
        return await super().call_action(action, data)


def _binding(installation: str) -> InstallationBinding:
    return InstallationBinding(
        instance_uuid=INSTANCE,
        workspace_uuid=WORKSPACE,
        installation_uuid=installation,
        runtime_revision=1,
        artifact_digest="a" * 64,
    )


def _plugin(host: ReorderingHost) -> DailyLimitPlugin:
    plugin = DailyLimitPlugin()
    plugin.plugin_runtime_handler = host
    return plugin


async def _settle(turns: int = 20) -> None:
    for _ in range(turns):
        await asyncio.sleep(0)


async def _drain(host: ReorderingHost, *tasks: asyncio.Task) -> None:
    """Run the tasks to completion while the Host commits writes newest-first."""

    for _ in range(200):
        if host.release_newest():
            await _settle()
            continue
        if all(task.done() for task in tasks):
            break
        await asyncio.sleep(0)
    assert all(task.done() for task in tasks), "the Host writes never completed"
    for task in tasks:
        task.result()


def _row(host: ReorderingHost, binding: InstallationBinding) -> dict:
    scope = plugin_main.installation_scope(binding)
    return json.loads(host.rows[(INSTANCE, WORKSPACE, plugin_main.storage_key(scope))].decode("utf-8"))


def test_runtime_write_is_not_overwritten_by_an_overlapping_admin_write():
    """A counter write and an admin settings write of one installation must not interleave."""

    async def scenario():
        host = ReorderingHost()
        plugin = _plugin(host)
        binding = _binding("installation-a")

        with bind_invocation(host, config=CONFIG, binding=binding):
            settings_write = asyncio.create_task(plugin.update_settings({"limit_message": "admin"}))
            await _settle()
            # PRE-FIX: the admin write reaches the Host without the installation
            # lock, so the runtime write below starts while it is still in flight.
            assert len(host.pending) == 1, "the settings write never reached the Host"

            counter_write = asyncio.create_task(plugin.check_and_count("group:1", "group:1"))
            await _settle(50)

            await _drain(host, settings_write, counter_write)

        row = _row(host, binding)
        # PRE-FIX: the older settings snapshot was committed last, so the durable
        # row had no "group:1" session at all.
        assert list(row["sessions"]) == ["group:1"]
        assert row["sessions"]["group:1"]["count"] == 1
        assert row["settings"]["limit_message"] == "admin"

        # The durable row is the truth: a reload must show the same state.
        reloaded = _plugin(host)
        with bind_invocation(host, config=CONFIG, binding=binding):
            snapshot = await reloaded.snapshot()
        assert [row_["id"] for row_ in snapshot["sessions"]] == ["group:1"]
        assert snapshot["sessions"][0]["count"] == 1
        assert snapshot["settings"]["limit_message"] == "admin"

    asyncio.run(scenario())


def test_admin_writes_of_one_installation_are_serialized_too():
    """Two overlapping admin writes must not let the older snapshot win."""

    async def scenario():
        host = ReorderingHost()
        plugin = _plugin(host)
        binding = _binding("installation-a")

        with bind_invocation(host, config=CONFIG, binding=binding):
            counter_write = asyncio.create_task(plugin.check_and_count("group:1", "group:1"))
            await _drain(host, counter_write)
            assert list(_row(host, binding)["sessions"]) == ["group:1"]

            settings_write = asyncio.create_task(plugin.update_settings({"reset_hour": 5}))
            await _settle()
            assert len(host.pending) == 1, "the settings write never reached the Host"

            delete_write = asyncio.create_task(plugin.delete_session("group:1"))
            await _settle(50)

            await _drain(host, settings_write, delete_write)

        row = _row(host, binding)
        # PRE-FIX: the settings snapshot (which still held "group:1") was committed
        # after the deletion, so the session came back.
        assert row["sessions"] == {}
        assert row["settings"]["reset_hour"] == 5

    asyncio.run(scenario())


def test_failed_write_does_not_leave_the_change_in_memory():
    """A write that never landed must not stay in memory and leak into the next one."""

    async def scenario():
        host = FlakyHost(fail_on=2)
        plugin = _plugin(host)
        binding = _binding("installation-a")

        with bind_invocation(host, config=CONFIG, binding=binding):
            counter_write = asyncio.create_task(plugin.check_and_count("group:1", "group:1"))
            await _drain(host, counter_write)

            # PRE-FIX: the rejected value stayed in the cached settings dict and was
            # written out by the next successful write.
            with pytest.raises(RuntimeError):
                await plugin.update_settings({"limit_message": "never persisted"})
            assert (await plugin.snapshot())["settings"]["limit_message"] == "configured message"

            await _drain(host, asyncio.create_task(plugin.reset_all()))

        row = _row(host, binding)
        assert row["settings"]["limit_message"] == "configured message"
        assert list(row["sessions"]) == ["group:1"]

    asyncio.run(scenario())
