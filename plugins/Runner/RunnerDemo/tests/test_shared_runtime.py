"""Real SDK 0.7.4 shared worker: two installation bindings, one object graph.

Only Host/backend responses are deterministic protocol fixtures. Component
discovery, the loopback WebSocket RPC transport, ``PluginRuntimeController``,
``BasePlugin`` and the RunnerDemo components are the released SDK and the
plugin's own code.

The certified worker runs in this process, so the same test asserts object
identity on the live worker graph: two distinct ``InstallationBinding``
envelopes (workspace-A/installation-A, workspace-B/installation-B) resolve to
ONE ``PluginContainer``, one ``RunnerDemo`` instance and one instance per
component, while each binding keeps its own configuration, events and results.
"""

from __future__ import annotations

import asyncio
import copy
import json
import os
import tempfile
import unittest
from pathlib import Path

import websockets
from langbot_plugin.api.entities.builtin.runner.result import RunnerResult
from langbot_plugin.cli.run.controller import PluginRuntimeController
from langbot_plugin.cli.run.handler import PluginRuntimeHandler
from langbot_plugin.cli.utils.page_components import discover_plugin_components
from langbot_plugin.entities.io.actions.enums import PluginToRuntimeAction as P
from langbot_plugin.entities.io.actions.enums import RuntimeToPluginAction as R
from langbot_plugin.entities.io.context import InstallationBinding
from langbot_plugin.entities.io.errors import ActionCallError
from langbot_plugin.entities.io.resp import ActionResponse
from langbot_plugin.runtime.io.connections.ws import WebSocketConnection
from langbot_plugin.runtime.io.handler import Handler
from langbot_plugin.runtime.plugin.container import RuntimeContainerStatus
from langbot_plugin.utils.discover.engine import ComponentDiscoveryEngine

ROOT = Path(__file__).resolve().parents[1]
OWNERS = ("a", "b")
TOOL_NAMES = ("event_get_actor", "event_get_group", "event_reply")

# Per-installation settings as the Host would persist them, and the same values
# the Host renders into each run context. Every value carries an owner marker so
# cross-installation leakage is observable in configs, payloads and results.
CONFIGS = {
    "a": {
        "language": "en_US",
        "welcome_text": "welcome-private-a",
        "command_prefix": "/demo-a",
        "announce_departures": False,
        "delay_ms": 0,
        "allow_demo_failure": False,
    },
    "b": {
        "language": "zh_Hans",
        "welcome_text": "welcome-private-b",
        "command_prefix": "/demo-b",
        "announce_departures": False,
        "delay_ms": 0,
        "allow_demo_failure": False,
    },
}


def other(owner):
    return "b" if owner == "a" else "a"


def binding(owner):
    return InstallationBinding(
        instance_uuid="fixture",
        workspace_uuid=f"workspace-{owner}",
        installation_uuid=f"installation-{owner}",
        runtime_revision=1,
        artifact_digest="1" * 64,
    )


def run_context(owner, *, run_id, example, config, tools=(), marker=None, command=None):
    """One Host-rendered Run context built from a checked-in RunnerDemo example."""
    payload = json.loads((ROOT / "examples" / example).read_text(encoding="utf-8"))
    data = {"type": payload["event_type"], **payload["data"]}
    if marker is not None:
        data["data"]["marker"] = marker
    if command is not None:
        data["message_chain"][0]["text"] = command
    return {
        "run_id": run_id,
        "trigger": {"type": payload["event_type"], "source": "host_adapter"},
        "event": {
            "event_id": f"event-{run_id}",
            "event_type": payload["event_type"],
            "source": "test",
            "data": data,
        },
        "input": {},
        "delivery": {"surface": "test"},
        "runtime": {},
        "config": dict(config),
        "resources": {
            "tools": [{"tool_name": name, "operations": ["call"], "parameters": {"type": "object"}} for name in tools]
        },
    }


class DemoHostFixture:
    """Deterministic Host responses plus trusted-envelope accounting."""

    def __init__(self, host):
        self.host = host
        self.calls = []
        self.run_owners = {}
        self.violations = []
        self.barrier = False
        self.release = asyncio.Event()
        self.barrier_seen = set()
        self.concurrent_calls = 0
        self.peak_concurrent_calls = 0

        @host.action(P.GET_LANGBOT_VERSION)
        async def version(data):
            return ActionResponse.success({"version": "runner-demo-fixture", "api_features": []})

        @host.action(P.CALL_TOOL)
        async def call_tool(data):
            owner = self.record("call_tool", data)
            self.concurrent_calls += 1
            self.peak_concurrent_calls = max(self.peak_concurrent_calls, self.concurrent_calls)
            try:
                await self.reach_barrier(owner)
                return ActionResponse.success(
                    {"result": {"mock": True, "delivery": "simulated", "echo": f"result-private-{owner}"}}
                )
            finally:
                self.concurrent_calls -= 1

    def record(self, action, data):
        """Record one plugin-to-runtime call under its trusted installation envelope."""
        envelope = self.host.current_action_context
        if not isinstance(envelope, InstallationBinding):
            self.violations.append(f"{action}: envelope {envelope!r}")
            raise AssertionError("Host callback lost the trusted installation envelope")
        owner = {f"installation-{name}": name for name in OWNERS}[envelope.installation_uuid]
        if envelope.workspace_uuid != f"workspace-{owner}" or envelope.runtime_revision != 1:
            self.violations.append(f"{action}: envelope {envelope!r}")
            raise AssertionError(f"{action} arrived under a mismatched installation envelope")
        run_id = data.get("run_id")
        if isinstance(run_id, str) and run_id in self.run_owners and self.run_owners[run_id] != owner:
            self.violations.append(f"{action}: run {run_id} reached {owner}")
            raise AssertionError(f"run {run_id} left its installation binding")
        payload = json.dumps(data, ensure_ascii=False)
        if f"private-{other(owner)}" in payload:
            self.violations.append(f"{action}: {payload}")
            raise AssertionError(f"foreign installation marker reached binding {owner}")
        self.calls.append((action, copy.deepcopy(data), owner))
        if len(self.calls) > 200:
            self.violations.append("unbounded fixture RPC loop")
            raise AssertionError("Unbounded fixture RPC loop")
        return owner

    async def reach_barrier(self, owner):
        """Hold both bindings inside the shared component at the same time."""
        if not self.barrier:
            return
        self.barrier_seen.add(owner)
        if len(self.barrier_seen) < len(OWNERS):
            await asyncio.wait_for(self.release.wait(), 5)
        else:
            self.release.set()

    def calls_from(self, owner):
        return [action for action, _, recorded in self.calls if recorded == owner]

    async def attach(self, owner, settings=None):
        return await self.host.call_action(
            R.ATTACH_PLUGIN_SLOT,
            {"plugin_settings": settings or {"enabled": True, "priority": 0, "plugin_config": CONFIGS[owner]}},
            timeout=5,
            action_context=binding(owner),
        )

    async def detach(self, owner):
        return await self.host.call_action(R.DETACH_PLUGIN_SLOT, {}, timeout=5, action_context=binding(owner))

    async def run(
        self,
        owner,
        *,
        run_id,
        example,
        config=None,
        tools=(),
        runner="community",
        marker=None,
        command=None,
    ):
        self.run_owners[run_id] = owner
        return [
            RunnerResult.model_validate(item)
            async for item in self.host.call_action_generator(
                R.RUN_RUNNER,
                {
                    "runner_name": runner,
                    "context": run_context(
                        owner,
                        run_id=run_id,
                        example=example,
                        config=config or CONFIGS[owner],
                        tools=tools,
                        marker=marker,
                        command=command,
                    ),
                },
                timeout=10,
                action_context=binding(owner),
            )
        ]


class SharedRuntimeDualBindingTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        original_cwd = os.getcwd()
        os.chdir(ROOT)
        self.addCleanup(os.chdir, original_cwd)

        storage = tempfile.TemporaryDirectory()
        self.addCleanup(storage.cleanup)
        previous_storage = os.environ.get("LANGBOT_PLUGIN_FILE_STORAGE_DIR")
        os.environ["LANGBOT_PLUGIN_FILE_STORAGE_DIR"] = str(Path(storage.name) / "rpc")
        self.addCleanup(self._restore_storage_dir, previous_storage)

        discovery = ComponentDiscoveryEngine()
        manifest = discovery.load_component_manifest("manifest.yaml")
        self.assertEqual(
            (manifest.execution.shared_runtime, manifest.execution.component_model),
            ("shared-runtime-v1", "stateless-v1"),
        )
        components = discover_plugin_components(manifest, discovery)
        # Component discovery order follows the filesystem, so compare the set of
        # declared components rather than the order they were found in.
        self.assertEqual(
            sorted((component.kind, component.metadata.name) for component in components),
            [("Runner", "community"), ("Runner", "observer")],
        )

        self.controller = PluginRuntimeController(manifest, components, stdio=False, ws_debug_url="")
        # Registered first so it runs last, after the worker connection is closed.
        self.addAsyncCleanup(self.controller.cleanup_instances)
        host_ready = asyncio.get_running_loop().create_future()

        async def host_connection(socket):
            host = Handler(WebSocketConnection(socket), file_storage_dir=str(Path(storage.name) / "host-rpc"))
            backend = DemoHostFixture(host)
            host_ready.set_result(backend)
            try:
                await host.run()
            finally:
                await host.close()

        server = await websockets.serve(host_connection, "127.0.0.1", 0)
        self.addAsyncCleanup(self._close_server, server)
        port = server.sockets[0].getsockname()[1]

        socket = await websockets.connect(f"ws://127.0.0.1:{port}")
        handler = PluginRuntimeHandler(WebSocketConnection(socket), self.controller.initialize)
        handler.plugin_container = self.controller.plugin_container
        handler._slot_initialize_callback = self.controller.initialize_slot
        handler._slot_detach_callback = self.controller.detach_slot
        handler._slot_cancel_callback = self.controller.invalidate_slot
        self.controller.handler = handler
        self.worker_task = asyncio.create_task(handler.run())
        self.addAsyncCleanup(self._stop_worker, handler)

        self.host = await asyncio.wait_for(host_ready, 5)
        for owner in OWNERS:
            await self.host.attach(owner)

    @staticmethod
    def _restore_storage_dir(previous):
        if previous is None:
            os.environ.pop("LANGBOT_PLUGIN_FILE_STORAGE_DIR", None)
        else:
            os.environ["LANGBOT_PLUGIN_FILE_STORAGE_DIR"] = previous

    async def _stop_worker(self, handler):
        await handler.close()
        self.worker_task.cancel()
        await asyncio.gather(self.worker_task, return_exceptions=True)

    @staticmethod
    async def _close_server(server):
        server.close()
        await server.wait_closed()

    # ---- worker-side object graph assertions -------------------------------

    def routed_container(self, owner):
        """Container the worker's own RPC scope resolves for one installation binding.

        ``PluginRuntimeHandler.action_invocation_scope`` looks the binding up in
        this registry, and ``RUN_RUNNER`` resolves the component from
        ``handler.plugin_container``, so both paths must land on the one graph.
        """
        slot = self.controller.handler._slot_containers[f"installation-{owner}"]
        return slot.plugin_container

    def shared_container(self):
        """Resolve both bindings through the worker and assert one object graph."""
        container = self.controller.plugin_container
        slot_a = self.controller.plugin_container_for_slot("installation-a")
        slot_b = self.controller.plugin_container_for_slot("installation-b")
        self.assertIsNotNone(slot_a)
        self.assertIsNotNone(slot_b)
        self.assertIsNot(slot_a, slot_b)
        self.assertEqual((slot_a.binding, slot_b.binding), (binding("a"), binding("b")))
        # Both installation slots resolve to the one process-wide graph.
        self.assertIs(slot_a.plugin_container, container)
        self.assertIs(slot_b.plugin_container, container)
        self.assertIs(self.controller.handler.plugin_container, container)
        self.assertIs(slot_a.plugin_container.components, slot_b.plugin_container.components)
        for owner in OWNERS:
            self.assertIs(self.routed_container(owner), container)
        # Per-installation state lives on the slot, not on the shared graph.
        self.assertEqual(dict(slot_a.plugin_config), CONFIGS["a"])
        self.assertEqual(dict(slot_b.plugin_config), CONFIGS["b"])
        self.assertIsNot(slot_a.plugin_config, slot_b.plugin_config)
        # One plugin instance and one instance per component, bound to the live worker.
        self.assertEqual(type(container.plugin_instance).__name__, "RunnerDemo")
        self.assertEqual(
            sorted(component.manifest.metadata.name for component in container.components),
            ["community", "observer"],
        )
        self.assertEqual(container.status, RuntimeContainerStatus.INITIALIZED)
        for component in container.components:
            self.assertIs(component.component_instance._plugin_runtime_handler, self.controller.handler)
            self.assertIs(component.component_instance.plugin, container.plugin_instance)
        return container

    def graph_identity(self):
        container = self.controller.plugin_container
        return (
            id(container),
            id(container.plugin_instance),
            tuple(id(component.component_instance) for component in container.components),
        )

    # ---- run result helpers ------------------------------------------------

    def assert_completed(self, results):
        self.assertEqual(results[-1].type, "run.completed")
        self.assertEqual(len([r for r in results if r.type in {"run.completed", "run.failed"}]), 1)
        self.assertEqual([r.sequence for r in results], list(range(1, len(results) + 1)))

    def result_text(self, results):
        return json.dumps([result.model_dump(mode="json") for result in results], ensure_ascii=False)

    def reply_texts(self, results):
        return [
            result.data["parameters"]["text"]
            for result in results
            if result.type == "tool.call.started" and result.data.get("tool_name") == "event_reply"
        ]

    def log_text(self, results):
        return "\n".join(result.data.get("text", "") for result in results if result.type == "processor.log")

    # ---- tests -------------------------------------------------------------

    async def test_concurrent_bindings_share_one_component_instance(self):
        """Both bindings run at once inside the one `community` component instance."""
        container = self.shared_container()
        identity = self.graph_identity()
        self.host.barrier = True

        results_a, results_b = await asyncio.gather(
            self.host.run("a", run_id="run-a-join", example="01-member-joined.json", tools=TOOL_NAMES),
            self.host.run("b", run_id="run-b-join", example="01-member-joined.json", tools=TOOL_NAMES),
        )

        self.assertGreaterEqual(
            self.host.peak_concurrent_calls, 2, "both bindings must be inside the shared component simultaneously"
        )
        self.assertEqual(self.host.barrier_seen, set(OWNERS))
        for results in (results_a, results_b):
            self.assert_completed(results)
        self.assertEqual(self.reply_texts(results_a), ["Alice，welcome-private-a"])
        self.assertEqual(self.reply_texts(results_b), ["Alice，welcome-private-b"])
        self.assertIn("Member joined", self.log_text(results_a))
        self.assertIn("成员加入", self.log_text(results_b))
        for owner, results in (("a", results_a), ("b", results_b)):
            text = self.result_text(results)
            self.assertIn(f"result-private-{owner}", text)
            self.assertNotIn(f"private-{other(owner)}", text)
            self.assertEqual(
                {result.data["result"]["echo"] for result in results if result.type == "tool.call.completed"},
                {f"result-private-{owner}"},
            )
        self.assertEqual(self.host.calls_from("a"), ["call_tool"] * 3)
        self.assertEqual(self.host.calls_from("b"), ["call_tool"] * 3)
        self.assertEqual(self.host.violations, [])
        # No second graph appeared while serving the sibling installation.
        self.assertEqual(self.graph_identity(), identity)
        self.assertIs(self.controller.plugin_container_for_slot("installation-a").plugin_container, container)
        self.assertIs(self.controller.plugin_container_for_slot("installation-b").plugin_container, container)

    async def test_one_graph_serves_both_components_and_later_events(self):
        """A then B (other component) then a later event on A, on one graph."""
        self.shared_container()
        identity = self.graph_identity()

        first = await self.host.run("a", run_id="run-a-first", example="01-member-joined.json", tools=TOOL_NAMES)
        self.assert_completed(first)
        self.assertEqual(self.reply_texts(first), ["Alice，welcome-private-a"])

        observed = await self.host.run(
            "b",
            run_id="run-b-observe",
            example="10-observer-custom.json",
            runner="observer",
            config={"language": "zh_Hans", "include_payload": True},
            marker="payload-private-b",
        )
        self.assert_completed(observed)
        self.assertEqual(self.reply_texts(observed), [])
        self.assertEqual([r for r in observed if r.type.startswith("tool.call")], [])
        self.assertIn("payload-private-b", self.result_text(observed))
        self.assertNotIn("private-a", self.result_text(observed))
        self.assertEqual(self.graph_identity(), identity)

        # The later event on A uses A's own command prefix; B's prefix would not
        # match and would produce no reply, so the reply proves A's own config.
        later = await self.host.run(
            "a",
            run_id="run-a-later",
            example="11-echo-with-image.json",
            tools=TOOL_NAMES,
            command=f"{CONFIGS['a']['command_prefix']} echo echo-private-a",
        )
        self.assert_completed(later)
        self.assertEqual(self.reply_texts(later), ["echo-private-a"])
        self.assertIn("echo-private-a", self.result_text(later))
        self.assertNotIn("private-b", self.result_text(later))
        self.assertEqual(self.host.violations, [])
        self.assertEqual(self.graph_identity(), identity)

    async def test_detaching_one_binding_keeps_sibling_graph_intact(self):
        """Isolation is per installation: dropping B leaves A's shared graph intact."""
        container = self.shared_container()
        identity = self.graph_identity()

        await self.host.detach("b")
        self.assertIsNone(self.controller.plugin_container_for_slot("installation-b"))
        self.assertIs(self.controller.plugin_container_for_slot("installation-a").plugin_container, container)

        with self.assertRaises(ActionCallError) as caught:
            await self.host.run("b", run_id="run-b-detached", example="01-member-joined.json", tools=TOOL_NAMES)
        self.assertIn("Shared plugin slot is not attached", str(caught.exception))

        kept = await self.host.run("a", run_id="run-a-after-detach", example="01-member-joined.json", tools=TOOL_NAMES)
        self.assert_completed(kept)
        self.assertEqual(self.reply_texts(kept), ["Alice，welcome-private-a"])
        self.assertIs(self.controller.plugin_container, container)
        self.assertEqual(self.graph_identity(), identity)
        self.assertEqual(self.host.violations, [])


if __name__ == "__main__":
    unittest.main()
