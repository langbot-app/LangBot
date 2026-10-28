"""Operational two-binding probe against real SDK 0.7.4 Worker, local upstream fixtures.

Not a certificate: runs source directories, injects an observer/controlled vendor
transport via sitecustomize, has no Cloud placement or live upstream acceptance.
The artifact_digest in both synthetic bindings is a protocol fixture, not a
hash of a built archive. Keep native coding runners dedicated-only.
"""

import asyncio
import importlib.metadata
import json
import os
import pathlib
import sys
import textwrap

from aiohttp import web
from langbot_plugin.api.entities.builtin.runner import (
    AgentEventContext,
    AgentInput,
    AgentResources,
    AgentRunState,
    AgentRuntimeContext,
    AgentTrigger,
    DeliveryContext,
    RunnerContext,
)
from langbot_plugin.entities.io.actions.enums import PluginToRuntimeAction, RuntimeToPluginAction
from langbot_plugin.entities.io.context import InstallationBinding

ROOT = pathlib.Path(__file__).resolve().parents[1]
NAMES = ["coze", "dify", "n8n", "langflow", "dashscope", "tbox", "deerflow", "weknora"]


def ctx(name, config):
    return RunnerContext(
        run_id=f"run-{name}",
        trigger=AgentTrigger(type="message.received"),
        event=AgentEventContext(event_id="fixture-event", event_type="message.received", source="fixture"),
        input=AgentInput(text="FIXTURE_OK"),
        delivery=DeliveryContext(surface="test", supports_streaming=True),
        resources=AgentResources(),
        state=AgentRunState(),
        runtime=AgentRuntimeContext(metadata={"component_kind": "Runner", "steering_enabled": False}),
        config=config,
    ).model_dump(mode="json")


def binding(letter):
    return InstallationBinding(
        instance_uuid="probe-instance",
        workspace_uuid=f"workspace-{letter}",
        installation_uuid=f"installation-{letter}",
        placement_generation=1,
        runtime_revision=1,
        artifact_digest="a" * 64,
    )


async def rpc(proc, seq, action, data, b=None):
    frame = dict(seq_id=seq, action=action, data=data)
    if b:
        frame["context"] = b.model_dump()
    proc.stdin.write((json.dumps(frame) + "\n").encode())
    await proc.stdin.drain()
    results = []
    callbacks = []
    while True:
        line = await asyncio.wait_for(proc.stdout.readline(), 20)
        if not line:
            raise RuntimeError("worker EOF: " + (await proc.stderr.read()).decode()[-4000:])
        try:
            response = json.loads(line)
        except json.JSONDecodeError:
            continue
        if "action" in response:
            callbacks.append(response)
            proc.stdin.write(
                (
                    json.dumps(dict(seq_id=response["seq_id"], code=0, message="ok", data={"bots": ["fixture-bot"]}))
                    + "\n"
                ).encode()
            )
            await proc.stdin.drain()
            continue
        if response.get("seq_id") != seq:
            raise AssertionError(response)
        if response.get("code") != 0:
            raise AssertionError(response)
        if response.get("chunk_status") == "end":
            return results, callbacks
        results.append(response.get("data"))
        if action != RuntimeToPluginAction.RUN_RUNNER.value:
            return results, callbacks


async def vendor(request):
    body = await request.json()
    authorization = str(request.headers.get("Authorization", ""))
    api_key_header = str(request.headers.get("X-API-Key", ""))
    credential_blob = json.dumps(body) + request.path + authorization + api_key_header
    letter = "A" if "tenant-A" in credential_blob else "B" if "tenant-B" in credential_blob else "?"
    request.app["calls"].append(
        dict(
            path=request.path,
            letter=letter,
            body=body,
            authorization_marker=letter if "tenant-" + letter in authorization else None,
            api_key_marker=letter if "tenant-" + letter in api_key_header else None,
        )
    )
    name = request.app["name"]
    text = "FIXTURE_OK_" + letter
    if name == "n8n":
        return web.json_response({"response": text})

    def sse(events):
        return web.Response(
            text="".join(
                (f"event: {event}\n" if event else "") + "data: " + json.dumps(data) + "\n\n" for event, data in events
            ),
            content_type="text/event-stream",
        )

    if name == "langflow":
        return sse([(None, {"messages": [{"message": text}], "session_id": "fixture-session-" + letter})])
    if name == "coze":
        return sse(
            [
                ("conversation.message.delta", {"content": text}),
                ("conversation.chat.completed", {"conversation_id": "fixture-conversation-" + letter}),
            ]
        )
    if name == "dify":
        return sse(
            [
                (None, {"event": "message", "answer": text, "conversation_id": "fixture-conversation-" + letter}),
                (None, {"event": "message_end", "conversation_id": "fixture-conversation-" + letter}),
            ]
        )
    if name == "weknora":
        # WeKnora: POST /sessions returns {"data": {"id": ...}}; chats stream
        # `data:` lines whose payload carries response_type/content/done.
        if request.path.endswith("/sessions"):
            return web.json_response({"data": {"id": "fixture-session-" + letter}})
        return sse([(None, {"response_type": "answer", "content": text, "done": True})])
    if name == "deerflow":
        # DeerFlow LangGraph: POST .../threads returns {"thread_id": ...}; the
        # runs/stream SSE carries a `values` event holding the message list.
        if request.path.endswith("/threads"):
            return web.json_response({"thread_id": "fixture-thread-" + letter})
        return sse([("values", {"messages": [{"type": "ai", "content": text, "id": "fixture-message-" + letter}]})])
    raise AssertionError(name)


async def probe(name, out):
    folder = ROOT / (name + "-agent")
    marker = out / (name + "-identities.jsonl")
    # The worker appends to this file, so a stale file from an earlier run in the
    # same outdir would add identity lines and fail the one-process assertions
    # below with a misleading `AssertionError()`.
    marker.write_text("", encoding="utf-8")
    site = out / (name + "-site")
    site.mkdir(exist_ok=True)
    if name in ("dashscope", "tbox"):
        worker = folder / "pkg/vendor_worker.py"
        fixture = ROOT / "http-certification-tests/fixtures/worker_transport_fixture.py"
        (site / "vendor_fixture.py").write_text(
            "import runpy\nrunpy.run_path("
            + repr(str(fixture))
            + ',init_globals={"WORKER":'
            + repr(str(worker))
            + ',"PLUGIN":'
            + repr(name + "-agent")
            + "})\n"
        )
    (site / "sitecustomize.py").write_text(
        textwrap.dedent("""\
 import os,json
 from langbot_plugin.cli.run.controller import PluginRuntimeController
 original=PluginRuntimeController.initialize_slot
 async def marked(self,binding,settings):
     slot=await original(self,binding,settings)
     with open(os.environ['PROBE_MARKER'],'a') as stream:
         stream.write(json.dumps({'pid':os.getpid(),'workspace':binding.workspace_uuid,'plugin_id':id(self.plugin_container.plugin_instance),'component_id':id(self.plugin_container.components[0].component_instance),'config':settings['plugin_config']})+'\\n')
     return slot
 PluginRuntimeController.initialize_slot=marked
 original_init=PluginRuntimeController._initialize_container
 async def init(self,*args,**kwargs):
     await original_init(self,*args,**kwargs)
     if os.environ.get('PROBE_VENDOR_WORKER'):
         import importlib
         module=importlib.import_module('pkg.'+os.environ['PROBE_VENDOR_MODULE'])
         original=module.vendor_stream
         async def fixture_stream(payload, *, timeout):
             import sys
             with open(os.environ['PROBE_MARKER'],'a') as stream:
                 stream.write(json.dumps({'vendor_request':True,'api_key':payload.get('api_key') or payload.get('kwargs',{}).get('api_key')})+'\\n')
             prior=list(sys.path)
             try:
                 sys.path.insert(0,os.environ['PROBE_VENDOR_SITE'])
                 async for item in original(payload,timeout=timeout,worker=os.environ['PROBE_VENDOR_WORKER']):
                     yield item
             finally:
                 sys.path[:]=prior
         module.vendor_stream=fixture_stream
 PluginRuntimeController._initialize_container=init
 """)
    )
    app = web.Application()
    app["name"] = name
    app["calls"] = []
    app.router.add_post("/{path:.*}", vendor)
    hr = web.AppRunner(app)
    await hr.setup()
    s = web.TCPSite(hr, "127.0.0.1", 0)
    await s.start()
    base = "http://127.0.0.1:" + str(s._server.sockets[0].getsockname()[1])
    env = {
        k: v
        for k, v in os.environ.items()
        if not any(x in k.upper() for x in ("TOKEN", "SECRET", "KEY", "PROXY", "ANTHROPIC", "CODEX", "DASHSCOPE"))
    }
    env.update(
        PYTHONPATH=str(site),
        PYTHONDONTWRITEBYTECODE="1",
        PYTHONUNBUFFERED="1",
        LANGBOT_PLUGIN_RUNTIME_PROFILE="shared",
        LANGBOT_PLUGIN_REGISTRATION_CAPABILITY="x" * 40,
        LANGBOT_PLUGIN_FILE_STORAGE_DIR=str(out / (name + "-files")),
        PROBE_MARKER=str(marker),
    )
    if name in ("dashscope", "tbox"):
        env["PROBE_VENDOR_WORKER"] = str(site / "vendor_fixture.py")
        env["PROBE_VENDOR_MODULE"] = name + "_client"
        env["PROBE_VENDOR_SITE"] = str(
            pathlib.Path(__import__(name if name == "dashscope" else "tboxsdk").__file__).parents[1]
        )
    proc = await asyncio.create_subprocess_exec(
        sys.executable,
        "-m",
        "langbot_plugin.cli.__init__",
        "run",
        "-s",
        "--prod",
        cwd=folder,
        env=env,
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    result = dict(
        plugin=name,
        pid=proc.pid,
        sdk=importlib.metadata.version("langbot-plugin"),
        upstream="loopback HTTP fixture" if name not in ("dashscope", "tbox") else "not configured",
        bindings=[],
    )
    try:
        while True:
            line = await asyncio.wait_for(proc.stdout.readline(), 20)
            if not line:
                raise RuntimeError("registration EOF")
            try:
                registered = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(registered, dict) and "action" in registered:
                break
        assert registered["action"] == PluginToRuntimeAction.REGISTER_PLUGIN.value, registered
        proc.stdin.write((json.dumps(dict(seq_id=registered["seq_id"], code=0, message="ok", data={})) + "\n").encode())
        await proc.stdin.drain()
        for i, letter in enumerate("AB"):
            b = binding(letter)
            config = {
                "api-key": "tenant-" + letter,
                "api-base": base,
                "base-url": base,
                "webhook-url": base + "/webhook",
                "bot-id": "tenant-" + letter,
                "app-id": "tenant-" + letter,
                "flow-id": "tenant-" + letter,
                "langbot-assets-enabled": False,
                "timeout": 5,
            }
            if name == "tbox":
                config["streaming"] = False
            att, cb = await rpc(
                proc,
                100 + i,
                RuntimeToPluginAction.ATTACH_PLUGIN_SLOT.value,
                {"plugin_settings": {"enabled": True, "priority": i, "plugin_config": {"tenant": "tenant-" + letter}}},
                b,
            )
            slot, _ = await rpc(proc, 110 + i, RuntimeToPluginAction.GET_PLUGIN_SLOT_CONTAINER.value, {}, b)
            assert slot[0]["plugin_config"] == {"tenant": "tenant-" + letter}, slot
            events, calls = await rpc(
                proc,
                120 + i,
                RuntimeToPluginAction.RUN_RUNNER.value,
                {"runner_name": "default", "context": ctx(letter, config)},
                b,
            )
            result["bindings"].append(
                dict(
                    binding=b.model_dump(),
                    attach=att,
                    slot_config=slot[0]["plugin_config"],
                    events=events,
                    host_callbacks=[c.get("context") for c in calls],
                )
            )
        markers = [json.loads(x) for x in marker.read_text().splitlines()]
        result["identities"] = [x for x in markers if "workspace" in x]
        result["vendor_requests"] = [x for x in markers if x.get("vendor_request")]
        if name in ("dashscope", "tbox"):
            assert [x["api_key"] for x in result["vendor_requests"]] == ["tenant-A", "tenant-B"], result[
                "vendor_requests"
            ]
        result["upstream_calls"] = [
            {"path": x["path"], "letter": x["letter"], "authorization_marker": x["authorization_marker"]}
            for x in app["calls"]
        ]
        assert (
            all(c["letter"] == letter for letter, c in zip("AB", app["calls"], strict=True))
            if name in ("coze", "dify", "langflow")
            else True
        )
        assert len(app["calls"]) == 2 if name not in ("dashscope", "tbox", "deerflow", "weknora") else True
        if name in ("deerflow", "weknora"):
            # These vendors touch their API twice per binding: create the
            # thread/session, then stream the run. Both calls must carry that
            # binding's own credential (Bearer / X-API-Key).
            assert len(app["calls"]) == 4, result["upstream_calls"]
            assert [c["letter"] for c in app["calls"]] == ["A", "A", "B", "B"], result["upstream_calls"]
            markers = [c["authorization_marker"] or c["api_key_marker"] for c in app["calls"]]
            assert markers == ["A", "A", "B", "B"], result["upstream_calls"]
        assert len(result["identities"]) == 2 and {x["pid"] for x in result["identities"]} == {proc.pid}
        assert (
            len({x["plugin_id"] for x in result["identities"]})
            == len({x["component_id"] for x in result["identities"]})
            == 1
        )
        assert {x["workspace"] for x in result["identities"]} == {"workspace-A", "workspace-B"}
        for row in result["bindings"]:
            assert row["events"][-1]["type"] == "run.completed", row["events"]
            assert not any(e["type"] == "run.failed" for e in row["events"])
            assert "FIXTURE_OK" in json.dumps(row["events"])
        assert len(app["calls"]) >= 2 or name in ("dashscope", "tbox")
        result["passed"] = True
    except Exception as e:
        result["passed"] = False
        result["error"] = repr(e)
    finally:
        proc.terminate()
        try:
            await asyncio.wait_for(proc.wait(), 5)
        except TimeoutError:
            proc.kill()
            await proc.wait()
        result["stderr"] = (await proc.stderr.read()).decode()[-3000:]
        await hr.cleanup()
        (out / (name + ".json")).write_text(json.dumps(result, indent=2, default=str))
    print(name, "PASS" if result.get("passed") else "BLOCKED", result.get("error", ""), "pid", proc.pid, flush=True)


async def main():
    assert importlib.metadata.version("langbot-plugin") == "0.7.4"
    out = pathlib.Path(sys.argv[1])
    out.mkdir(parents=True, exist_ok=True)
    failures = []
    for name in NAMES:
        await probe(name, out)
        if not json.loads((out / (name + ".json")).read_text())["passed"]:
            failures.append(name)
    if failures:
        raise SystemExit("Shared probe failed: " + ", ".join(failures))


asyncio.run(main())
