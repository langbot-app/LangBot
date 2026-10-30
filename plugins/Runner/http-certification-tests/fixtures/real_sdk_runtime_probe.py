"""Isolated runtime probe. All provider replies below are TEST FIXTURES, not live data."""

from __future__ import annotations

import asyncio
import importlib.metadata
import json
import logging
import runpy
import socket
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

import langbot_plugin
import websockets
from aiohttp import web
from langbot_plugin.api.definition.components.runner.runner import Runner
from langbot_plugin.api.entities.builtin.runner import (
    AgentEventContext,
    AgentInput,
    AgentResources,
    AgentRunState,
    AgentRuntimeContext,
    AgentTrigger,
    DeliveryContext,
    RunnerContext,
    RunnerManifest,
    RunnerResult,
)
from langbot_plugin.cli.run.controller import PluginRuntimeController
from langbot_plugin.cli.run.handler import PluginRuntimeHandler
from langbot_plugin.cli.utils.page_components import discover_plugin_components
from langbot_plugin.entities.io.actions.enums import RuntimeToPluginAction
from langbot_plugin.entities.io.req import ActionRequest
from langbot_plugin.runtime.io.connections.ws import WebSocketConnection
from langbot_plugin.utils.discover.engine import ComponentDiscoveryEngine

ROOT = Path(__file__).resolve().parents[2]
PLUGIN = sys.argv[2] if len(sys.argv) > 2 else Path.cwd().name
CALLS = []
TRANSCRIPT = []


def block_external_network(event, args):
    if event == "socket.connect":
        sock, address = args
        if sock.family in (socket.AF_INET, socket.AF_INET6) and address[0] not in ("127.0.0.1", "::1", "localhost"):
            raise AssertionError(f"External connection forbidden in fixture probe: {address}")


sys.addaudithook(block_external_network)


def ctx(run_id, config):
    return RunnerContext(
        run_id=run_id,
        trigger=AgentTrigger(type="message.received"),
        event=AgentEventContext(event_id="fixture-event", event_type="message.received", source="local-test"),
        input=AgentInput(text="FIXTURE_OK"),
        delivery=DeliveryContext(surface="test", supports_streaming=True),
        resources=AgentResources(),
        state=AgentRunState(),
        runtime=AgentRuntimeContext(metadata={"component_kind": "Runner", "steering_enabled": False}),
        config=config,
    ).model_dump(mode="json")


def sse(events):
    return web.Response(
        text="".join(
            (f"event: {name}\n" if name else "") + "data: " + json.dumps(data) + "\n\n" for name, data in events
        ),
        content_type="text/event-stream",
    )


async def vendor_fixture(request):
    body = await request.json()
    CALLS.append({"boundary": "loopback HTTP vendor fixture", "path": request.path, "body": body})
    if PLUGIN == "n8n-agent":
        return web.json_response({"response": "FIXTURE_OK"})
    if PLUGIN == "langflow-agent":
        return sse([(None, {"messages": [{"message": "FIXTURE_OK"}], "session_id": "fixture-session"})])
    if PLUGIN == "coze-agent":
        return sse(
            [
                ("conversation.message.delta", {"content": "FIXTURE_OK"}),
                ("conversation.chat.completed", {"conversation_id": "fixture-conversation"}),
            ]
        )
    if PLUGIN == "dify-agent":
        return sse(
            [
                (None, {"event": "message", "answer": "FIXTURE_OK", "conversation_id": "fixture-conversation"}),
                (None, {"event": "message_end", "conversation_id": "fixture-conversation"}),
            ]
        )
    if PLUGIN == "weknora-agent":
        if request.path.endswith("/sessions"):
            return web.json_response({"data": {"id": "fixture-session"}})
        return sse([(None, {"response_type": "answer", "content": "FIXTURE_OK", "done": True})])
    if PLUGIN == "deerflow-agent":
        if request.path.endswith("/threads"):
            return web.json_response({"thread_id": "fixture-thread"})
        return sse([("values", {"messages": [{"type": "ai", "content": "FIXTURE_OK", "id": "fixture-message"}]})])
    raise AssertionError(f"Unexpected fixture HTTP request: {PLUGIN} {request.path}")


async def rpc(conn, action, data, seq, *, stream=False):
    request = ActionRequest.make_request(seq, action.value, data)
    TRANSCRIPT.append({"direction": "request", "frame": request.model_dump(mode="json")})
    await conn.send(request.model_dump_json())
    responses = []
    while True:
        response = json.loads(await asyncio.wait_for(conn.receive(), 15))
        TRANSCRIPT.append({"direction": "response", "frame": response})
        assert response["seq_id"] == seq, response
        assert response["code"] == 0, response
        if response.get("chunk_status") == "end":
            break
        responses.append(response["data"])
        if not stream:
            break
    return responses


async def probe(destination):
    discovery = ComponentDiscoveryEngine()
    manifest = discovery.load_component_manifest("manifest.yaml")
    assert manifest is not None
    assert set(manifest.spec["components"]) == {"Runner"}
    components = discover_plugin_components(manifest, discovery)
    assert len(components) == 1
    component = components[0]
    assert component.kind == "Runner"
    identity = f"{manifest.metadata.author}/{manifest.metadata.name}"
    descriptor = RunnerManifest(
        id=f"plugin:{identity}/{component.metadata.name}",
        name=component.metadata.name,
        label=component.manifest["metadata"]["label"],
        component_kind=component.kind,
        usages=component.spec["usages"],
        capabilities=component.spec.get("capabilities", {}),
        permissions=component.spec.get("permissions", {}),
        config_schema=component.spec.get("config", []),
    )
    controller = PluginRuntimeController(manifest, components, stdio=False, ws_debug_url="", prod_mode=False)

    async def runtime_peer(ws):
        handler = PluginRuntimeHandler(WebSocketConnection(ws), controller.initialize)
        controller.handler = handler
        handler.plugin_container = controller.plugin_container
        await handler.run()

    app = web.Application()
    app.router.add_post("/{path:.*}", vendor_fixture)
    http_runner = web.AppRunner(app)
    await http_runner.setup()
    site = web.TCPSite(http_runner, "127.0.0.1", 0)
    await site.start()
    base = f"http://127.0.0.1:{site._server.sockets[0].getsockname()[1]}"
    config = {
        "api-key": "local-fixture-not-a-credential",
        "api-base": base,
        "base-url": base,
        "webhook-url": base + "/webhook",
        "bot-id": "fixture-bot",
        "app-id": "fixture-app",
        "flow-id": "fixture-flow",
        "langbot-assets-enabled": False,
        "timeout": 5,
    }
    if PLUGIN == "weknora-agent":
        config["app-type"] = "chat"
    invalid = {"location": "invalid"} if PLUGIN in {"acp-agent-runner", "claude-code-agent", "codex-agent"} else {}
    try:
        async with websockets.serve(runtime_peer, "127.0.0.1", 0) as server:
            port = server.sockets[0].getsockname()[1]
            async with websockets.connect(f"ws://127.0.0.1:{port}") as ws:
                conn = WebSocketConnection(ws)
                plugin_config = {
                    item["name"]: item["default"] for item in manifest.spec.get("config", []) if "default" in item
                }
                plugin_config["daemon-enabled"] = False
                await rpc(
                    conn,
                    RuntimeToPluginAction.INITIALIZE_PLUGIN,
                    {"plugin_settings": {"enabled": True, "priority": 0, "plugin_config": plugin_config}},
                    1,
                )
                container = (await rpc(conn, RuntimeToPluginAction.GET_PLUGIN_CONTAINER, {}, 2))[0]
                instance = controller.plugin_container.components[0].component_instance
                assert isinstance(instance, Runner)
                assert instance.plugin_identity == identity
                invalid_results = await rpc(
                    conn,
                    RuntimeToPluginAction.RUN_RUNNER,
                    {"runner_name": "default", "context": ctx("invalid-run", invalid)},
                    3,
                    stream=True,
                )
                with tempfile.TemporaryDirectory(prefix="runner-cli-fixture-") as work:
                    patches = []
                    if PLUGIN in {"claude-code-agent", "codex-agent"}:
                        helpers = runpy.run_path(str(ROOT / "tests/test_plugin_layout.py"))
                        cli = Path(work) / "fixture_cli.py"
                        writer = (
                            "_write_fake_native_cli"
                            if PLUGIN == "claude-code-agent"
                            else "_write_fake_codex_app_server"
                        )
                        helpers[writer](cli)
                        config.update(
                            {"location": "local", "command": sys.executable, "args-json": [str(cli)], "workspace": work}
                        )
                        if PLUGIN == "codex-agent":
                            config["command"] = f"{sys.executable} {cli}"
                            config["args-json"] = []
                        CALLS.append({"boundary": "local subprocess vendor CLI fixture", "writer": writer})
                    elif PLUGIN == "acp-agent-runner":
                        cli = ROOT / "tests/fixtures/fake_acp_runtime.py"
                        config.update(
                            {
                                "provider": "custom",
                                "command": sys.executable,
                                "args": [str(cli)],
                                "workspace": work,
                                "append-run-scope-prompt": False,
                            }
                        )
                        CALLS.append({"boundary": "local subprocess ACP JSON-RPC fixture", "script": str(cli)})
                    elif PLUGIN in {"dashscope-agent", "tbox-agent"}:
                        client_module = importlib.import_module("pkg." + PLUGIN.removesuffix("-agent") + "_client")
                        transport = importlib.import_module("pkg.vendor_process")
                        worker = Path(client_module.__file__).with_name("vendor_worker.py")
                        wrapper = Path(work) / "vendor_fixture.py"
                        fixture = Path(__file__).with_name("worker_transport_fixture.py")
                        wrapper.write_text(
                            "import runpy\n"
                            + f'runpy.run_path({str(fixture)!r}, init_globals={{"WORKER":{str(worker)!r},"PLUGIN":{PLUGIN!r}}})\n'
                        )
                        original = transport.vendor_stream
                        patches.append(
                            patch.object(
                                client_module,
                                "vendor_stream",
                                lambda payload, timeout: original(payload, timeout=timeout, worker=wrapper),
                            )
                        )
                        config["streaming"] = False if PLUGIN == "tbox-agent" else True
                        CALLS.append(
                            {"boundary": "real vendor SDK in killable subprocess, simulated transport", "live": False}
                        )
                    for item in patches:
                        item.start()
                    try:
                        fixture_results = await rpc(
                            conn,
                            RuntimeToPluginAction.RUN_RUNNER,
                            {"runner_name": "default", "context": ctx("fixture-run", config)},
                            4,
                            stream=True,
                        )
                    finally:
                        for item in reversed(patches):
                            item.stop()
                for result in invalid_results + fixture_results:
                    RunnerResult.model_validate(result)
                evidence = {
                    "plugin": PLUGIN,
                    "identity": identity,
                    "status": container["status"],
                    "runner_class": type(instance).__name__,
                    "component_kind": component.kind,
                    "descriptor": descriptor.model_dump(mode="json"),
                    "sdk_path": str(Path(langbot_plugin.__file__).resolve()),
                    "sdk_version": importlib.metadata.version("langbot-plugin"),
                    "transport": "real SDK WebSocketConnection + PluginRuntimeHandler on loopback",
                    "invalid_results": invalid_results,
                    "fixture_results": fixture_results,
                    "fixture_calls": CALLS,
                    "external_live_connectivity_tested": False,
                    "rpc_transcript": TRANSCRIPT,
                }
                destination.write_text(json.dumps(evidence, indent=2))
                print(json.dumps({key: evidence[key] for key in ("plugin", "identity", "status", "runner_class")}))
    finally:
        await http_runner.cleanup()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(probe(Path(sys.argv[1]).resolve()))
