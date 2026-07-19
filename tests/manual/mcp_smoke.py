"""End-to-end test: boot the real MCPMount on a port and drive it with an MCP client.

Exercises the ASGI dispatcher (auth + /mcp routing), the FastMCP streamable-HTTP
transport, and a real tool call against the (mocked) service layer.

Run: uv run --no-sync python tests/manual/mcp_smoke.py
"""

from __future__ import annotations

import asyncio
import contextlib
from types import SimpleNamespace
from unittest.mock import AsyncMock

from hypercorn.asyncio import serve
from hypercorn.config import Config
from quart import Quart

from langbot.pkg.api.mcp.mount import MCPMount

PORT = 5399
GLOBAL_KEY = 'test-global-key-123'


def build_ap() -> SimpleNamespace:
    ap = SimpleNamespace()
    ap.instance_config = SimpleNamespace(
        data={'api': {'global_api_key': GLOBAL_KEY}, 'system': {'edition': 'community', 'instance_id': 'inst-1'}}
    )
    ap.ver_mgr = SimpleNamespace(get_current_version=lambda: '4.5.0-test')
    ap.logger = SimpleNamespace(info=print, error=print, warning=print)

    # API key verification: reuse real logic shape (global key match)
    async def verify_api_key(key: str) -> bool:
        return bool(key) and key == GLOBAL_KEY

    ap.apikey_service = SimpleNamespace(verify_api_key=verify_api_key)
    ap.bot_service = SimpleNamespace(
        get_bots=AsyncMock(return_value=[{'uuid': 'bot-1', 'name': 'Demo Bot', 'adapter': 'telegram'}]),
        list_event_route_statuses=AsyncMock(return_value={'routes': [], 'unmatched_events': [], 'stale_routes': []}),
        dispatch_test_event_route=AsyncMock(
            return_value={
                'dispatched': True,
                'event_type': 'message.received',
                'suppressed_outputs': [],
                'route_status': {
                    'routes': [],
                    'unmatched_events': [],
                    'stale_routes': [],
                },
            }
        ),
    )
    ap.pipeline_service = SimpleNamespace(get_pipelines=AsyncMock(return_value=[{'uuid': 'pl-1', 'name': 'default'}]))
    ap.llm_model_service = SimpleNamespace(get_llm_models=AsyncMock(return_value=[]))
    ap.embedding_models_service = SimpleNamespace(get_embedding_models=AsyncMock(return_value=[]))
    ap.provider_service = SimpleNamespace(get_providers=AsyncMock(return_value=[]))
    ap.knowledge_service = SimpleNamespace(get_knowledge_bases=AsyncMock(return_value=[]))
    ap.mcp_service = SimpleNamespace(get_mcp_servers=AsyncMock(return_value=[]))
    ap.skill_service = SimpleNamespace(list_skills=AsyncMock(return_value=[{'name': 'demo-skill'}]))
    return ap


async def run_server(mount: MCPMount, shutdown: asyncio.Event) -> None:
    quart_app = Quart(__name__)

    @quart_app.route('/healthz')
    async def healthz():
        return {'code': 0, 'msg': 'ok'}

    config = Config()
    config.bind = [f'127.0.0.1:{PORT}']
    config.accesslog = None
    asgi = mount.wrap(quart_app)
    await serve(asgi, config, shutdown_trigger=shutdown.wait)


async def main() -> int:
    from mcp.client.session import ClientSession
    from mcp.client.streamable_http import streamablehttp_client

    ap = build_ap()
    mount = MCPMount(ap)
    await mount.start_session_manager()

    shutdown = asyncio.Event()
    server_task = asyncio.create_task(run_server(mount, shutdown))
    await asyncio.sleep(1.0)  # let the server bind

    url = f'http://127.0.0.1:{PORT}/mcp'
    failures = []

    # 1. Unauthorized request is rejected.
    import httpx

    async with httpx.AsyncClient() as client:
        r = await client.post(url, json={'jsonrpc': '2.0', 'id': 1, 'method': 'ping'})
        if r.status_code != 401:
            failures.append(f'expected 401 without key, got {r.status_code}')
        else:
            print('PASS: unauthorized request rejected (401)')

    # 2. Authorized MCP session: list tools + call two.
    headers = {'X-API-Key': GLOBAL_KEY}
    async with streamablehttp_client(url, headers=headers) as (read, write, _):
        async with ClientSession(read, write) as session:
            await session.initialize()
            tools = await session.list_tools()
            names = [t.name for t in tools.tools]
            print(f'PASS: listed {len(names)} tools')
            for required in ('list_bots', 'get_system_info', 'list_skills', 'test_bot_event_route'):
                if required not in names:
                    failures.append(f'missing tool {required}')

            res = await session.call_tool('list_bots', {})
            text = res.content[0].text if res.content else ''
            if 'Demo Bot' not in text:
                failures.append(f'list_bots did not return expected data: {text!r}')
            else:
                print('PASS: list_bots returned bot data')

            res2 = await session.call_tool('get_system_info', {})
            text2 = res2.content[0].text if res2.content else ''
            if '4.5.0-test' not in text2:
                failures.append(f'get_system_info wrong: {text2!r}')
            else:
                print('PASS: get_system_info returned version')

            res3 = await session.call_tool(
                'test_bot_event_route',
                {
                    'bot_uuid': 'bot-1',
                    'event_type': 'message.received',
                    'payload': {'message_text': 'hello'},
                },
            )
            text3 = res3.content[0].text if res3.content else ''
            if '"dispatched": true' not in text3:
                failures.append(f'test_bot_event_route wrong: {text3!r}')
            else:
                print('PASS: test_bot_event_route returned dispatch result')

    shutdown.set()
    with contextlib.suppress(Exception):
        await asyncio.wait_for(server_task, timeout=5)
    await mount.stop_session_manager()

    if failures:
        print('\nFAILURES:')
        for f in failures:
            print(' -', f)
        return 1
    print('\nALL MCP SMOKE CHECKS PASSED')
    return 0


if __name__ == '__main__':
    raise SystemExit(asyncio.run(main()))
