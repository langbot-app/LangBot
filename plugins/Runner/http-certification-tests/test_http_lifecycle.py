import asyncio
import importlib
from types import SimpleNamespace

import pytest
from test_isolation import GATEWAYS, context, gateway_invocation, load


@pytest.mark.parametrize("name", GATEWAYS)
def test_gateway_actual_http_revocation_limits_and_close(name):
    async def run(runner):
        import httpx

        runner.get_run_api = lambda ctx: SimpleNamespace()
        reg = await runner._create_asset_gateway_registration(
            context(),
            dict(
                asset_gateway_host="127.0.0.1",
                asset_gateway_port=0,
                asset_gateway_request_timeout=0.1,
                asset_gateway_token_ttl=60,
            ),
        )

        class Tools:
            async def call_mcp_tool(self, name, args):
                return {"content": [{"type": "text", "text": "scope-A"}]}

        reg.tools = Tools()
        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {"name": "fixture", "arguments": {"run_token": reg.token}},
        }
        async with httpx.AsyncClient(trust_env=False) as client:
            result = (await client.post(reg.http_mcp_endpoint, json=payload)).json()
            assert result["result"]["content"][0]["text"] == "scope-A"
            payload["params"]["arguments"]["run_token"] = "foreign"
            assert (await client.post(reg.http_mcp_endpoint, json=payload)).json()["result"]["isError"]
            assert (await client.post(reg.http_mcp_endpoint, content=b"x" * (1024 * 1024 + 1))).status_code == 413
            # Slow HTTP peer must expire rather than retaining a handler/task.
            port = reg.gateway.server.sockets[0].getsockname()[1]
            reader, writer = await asyncio.open_connection("127.0.0.1", port)
            writer.write(b"POST /mcp HTTP/1.1\r\nContent-Length: 100\r\n\r\n")
            await writer.drain()
            assert await asyncio.wait_for(reader.read(), 1) == b""
            writer.close()
            await writer.wait_closed()
            await reg.stop()
            assert reg.gateway._registration_for_token(reg.token) is None
            assert not reg.gateway.tasks
            with pytest.raises(httpx.ConnectError):
                await client.get(reg.endpoint)

    with load(name) as (_, runner):
        with gateway_invocation(runner):
            asyncio.run(run(runner))


@pytest.mark.parametrize("name", ["deerflow", "weknora", "dify", "langflow"])
def test_total_deadline_includes_trickle_stream(name, monkeypatch):
    import httpx

    async def run():
        with load(name):
            mod = importlib.import_module("pkg." + name + "_client")
            cls = getattr(
                mod,
                {
                    "deerflow": "AsyncDeerFlowClient",
                    "weknora": "AsyncWeKnoraClient",
                    "dify": "AsyncDifyClient",
                    "langflow": "AsyncLangflowClient",
                }[name],
            )

            class Trickle(httpx.AsyncByteStream):
                closed = False

                async def __aiter__(self):
                    while True:
                        await asyncio.sleep(0.015)
                        yield b": keepalive\n\n"

                async def aclose(self):
                    self.closed = True

            body = Trickle()
            original = httpx.AsyncClient
            client = original(
                base_url="https://fixture.invalid",
                transport=httpx.MockTransport(lambda request: httpx.Response(200, stream=body)),
            )
            monkeypatch.setattr(httpx, "AsyncClient", lambda *args, **kwargs: client)
            if name == "deerflow":
                c = cls(api_base="https://fixture.invalid")
                gen = c.stream_run("thread", {}, timeout=0.08)
            elif name == "weknora":
                c = cls(api_key="fixture", base_url="https://fixture.invalid")
                gen = c.knowledge_chat(session_id="session", query="hi", user="user", timeout=0.08)
            elif name == "dify":
                c = cls(api_key="fixture", base_url="https://fixture.invalid", timeout=0.08)
                gen = c.chat_messages(inputs={}, query="hi", user="user")
            else:
                c = cls(api_key="fixture", base_url="https://fixture.invalid", timeout=0.08)
                gen = c.run_flow(flow_id="flow", input_value="hi")
            started = asyncio.get_running_loop().time()
            with pytest.raises(TimeoutError):
                await asyncio.wait_for(anext(gen), 0.35)
            elapsed = asyncio.get_running_loop().time() - started
            await gen.aclose()
            assert elapsed < 0.25, "per-read timeout permits indefinite trickle"
            assert body.closed

    asyncio.run(run())


def test_dify_continuation_rejects_cross_conversation():
    with load("dify") as (m, runner):

        async def run():
            data = {}

            async def put(k, v):
                data[k] = v

            async def get(k):
                return data[k]

            runner.get_run_api = lambda ctx: SimpleNamespace(set_plugin_storage=put, get_plugin_storage=get)
            a = context()
            b = context()
            b.conversation.conversation_id = "other"
            await runner._store_interaction_continuation(a, {"interaction_id": "i", "version": 1})
            with pytest.raises(m.DifyAPIError):
                await runner._load_interaction_continuation(b, "i")

        asyncio.run(run())


def test_dify_failed_resume_is_not_replayed():
    with load("dify") as (m, runner):

        async def run():
            data = {}
            calls = []

            async def put(k, v):
                data[k] = v

            async def get(k):
                return data[k]

            runner.get_run_api = lambda ctx: SimpleNamespace(set_plugin_storage=put, get_plugin_storage=get)

            class Client:
                async def workflow_submit(self, **kwargs):
                    calls.append(kwargs)
                    raise ConnectionError("ambiguous remote failure")
                    yield

            ctx = context()
            await runner._store_interaction_continuation(
                ctx,
                {
                    "interaction_id": "i",
                    "version": 1,
                    "phase": "action",
                    "action_map": {"yes": "approve"},
                    "form_token": "fixture",
                    "workflow_run_id": "w",
                    "user": "u",
                },
            )
            submission = SimpleNamespace(interaction_id="i", values={}, action_id="yes")
            for _ in range(2):
                with pytest.raises((ConnectionError, m.DifyAPIError)):
                    async for _ in runner._resume_workflow(ctx, Client(), submission, False):
                        pass
            assert len(calls) == 1

        asyncio.run(run())


@pytest.mark.parametrize("name", GATEWAYS)
def test_same_installation_gateway_overlap_keeps_other_token_alive(name):
    async def run(runner):
        runner.get_run_api = lambda ctx: SimpleNamespace()
        cfg = dict(
            asset_gateway_host="127.0.0.1",
            asset_gateway_port=0,
            asset_gateway_request_timeout=1,
            asset_gateway_token_ttl=60,
        )
        a = await runner._create_asset_gateway_registration(context(), cfg)
        # A fixed port is the documented externally configured MCP address.
        cfg["asset_gateway_port"] = a.gateway.server.sockets[0].getsockname()[1]
        await a.stop()
        a = await runner._create_asset_gateway_registration(context(), cfg)
        b = None
        try:
            b = await runner._create_asset_gateway_registration(context(), cfg)
            await a.stop()
            assert b.gateway._registration_for_token(b.token) is b
        finally:
            await a.stop()
            if b:
                await b.stop()

    with load(name) as (_, runner):
        with gateway_invocation(runner):
            asyncio.run(run(runner))


@pytest.mark.parametrize("name", GATEWAYS)
def test_runner_cancellation_releases_gateway(name, monkeypatch):
    async def run(module, runner):
        entered = asyncio.Event()

        class Client:
            def __init__(self, **kwargs):
                pass

            async def close(self):
                pass

            async def hang(self, **kwargs):
                entered.set()
                await asyncio.Event().wait()
                yield {}

            chat_messages = iter_agent = iter_workflow = run_flow = call_webhook = hang

        monkeypatch.setattr(
            module,
            {
                "coze": "AsyncCozeClient",
                "dashscope": "DashScopeClient",
                "dify": "AsyncDifyClient",
                "langflow": "AsyncLangflowClient",
                "n8n": "AsyncN8nClient",
            }[name],
            Client,
        )
        runner.get_run_api = lambda ctx: SimpleNamespace()
        ctx = context()
        ctx.config.update(
            {
                "api-key": "fixture",
                "app-id": "app",
                "bot-id": "bot",
                "flow-id": "flow",
                "webhook-url": "https://fixture.invalid",
                "langbot-assets-enabled": True,
                "langbot-assets-gateway-host": "127.0.0.1",
                "langbot-assets-gateway-port": 0,
            }
        )

        async def consume():
            async for _ in runner.invoke(ctx):
                pass

        task = asyncio.create_task(consume())
        await asyncio.wait_for(entered.wait(), 1)
        task.cancel()
        await asyncio.sleep(0)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert not runner._asset_gateway_pool

    with load(name) as (module, runner):
        asyncio.run(run(module, runner))
