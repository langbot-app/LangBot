"""Compare a direct stream, Core requester and isolated OpenCode 2.x server.

All three clients use a local measurement relay. The relay sends the same
synthetic request bytes and headers upstream, deliberately removing agent prompt
differences. This measures the request layer, not a production bot pipeline/UI.
Credentials are read from an environment variable or an untracked local file.
"""

import argparse
import asyncio
import contextlib
import hashlib
import itertools
import json
import os
from pathlib import Path
import socket
import statistics
import secrets
import subprocess
import tempfile
import time
from types import SimpleNamespace

import httpx
from aiohttp import web


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


class SSEMeter:
    """Incrementally parse SSE without assuming network chunk boundaries."""

    def __init__(self):
        self.buffer = b''
        self.first_event = None
        self.first_content = None
        self.usage = None
        self.content_chars = 0
        self.done = False

    def feed(self, data, now):
        self.buffer += data
        while b'\n' in self.buffer:
            line, self.buffer = self.buffer.split(b'\n', 1)
            if not line.startswith(b'data:'):
                continue
            raw = line[5:].strip()
            if raw == b'[DONE]':
                self.done = True
                continue
            item = json.loads(raw)
            if self.first_event is None:
                self.first_event = now
            if item.get('usage'):
                self.usage = item['usage']
            for choice in item.get('choices', []):
                content = (choice.get('delta') or {}).get('content')
                if content:
                    if self.first_content is None:
                        self.first_content = now
                    self.content_chars += len(content)


def cache_tokens(usage):
    if not isinstance(usage, dict):
        return None
    detail = usage.get('prompt_tokens_details') or usage.get('input_tokens_details') or {}
    return detail.get('cached_tokens', usage.get('cache_read_input_tokens'))


def summary(records):
    result = {}
    for name in sorted({row['client'] for row in records}):
        rows = [r for r in records if r['client'] == name and not r.get('warmup')]
        stats = {'samples': len(rows)}
        for key in ('dispatch_to_wire_ms', 'upstream_ttft_ms', 'ttft_ms', 'total_ms', 'preparation_ms'):
            values = [r[key] for r in rows if r.get(key) is not None]
            if values:
                stats[key] = {'median': round(statistics.median(values), 3), 'max': round(max(values), 3)}
        stats['cache_read_tokens'] = [cache_tokens(r.get('usage')) for r in rows]
        result[name] = stats
    return result


def free_port():
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0))
        return sock.getsockname()[1]


async def run(options):
    # Import/initialization cost is reported separately from resident calls.
    started = time.perf_counter()
    from langbot.pkg.provider.modelmgr.requesters.litellmchat import LiteLLMRequester
    from langbot.pkg.provider.modelmgr.request_policy import CallState, RequestPolicy, current_call
    from langbot_plugin.api.entities.builtin.provider.message import Message
    import importlib.metadata

    import_ms = (time.perf_counter() - started) * 1000
    credentials = json.loads(Path(options.credentials_file).read_text()) if options.credentials_file else {}
    base_url = options.base_url or credentials.get('base_url')
    key = os.environ.get(options.api_key_env) or credentials.get('api_key')
    if not options.mock and not (base_url and key):
        raise ValueError('A base URL and API key are required for live mode')
    prefix = 'You are a concise technical assistant. Follow only the final question.\n'
    if options.long_prefix:
        prefix += ''.join(
            f'Reference entry {i}: HTTP connection pooling reuses established transports. '
            'Keep authentication and timeouts request scoped. Measure first content separately from reasoning.\n'
            for i in range(180)
        )
    canonical = {
        'model': options.model,
        'stream': True,
        'stream_options': {'include_usage': True},
        'temperature': 0,
        'max_tokens': 256,
        'messages': [
            {
                'role': 'system',
                'content': [
                    {
                        'type': 'text',
                        'text': prefix,
                        **({'cache_control': {'type': 'ephemeral'}} if options.cache_control else {}),
                    }
                ],
            },
            {'role': 'user', 'content': 'Explain HTTP connection pooling in exactly five short numbered sentences.'},
        ],
    }
    payload = json.dumps(canonical, separators=(',', ':')).encode()
    records = []
    active = None
    upstream = httpx.AsyncClient(timeout=90)
    relay_sockets = {}

    async def relay(request):
        nonlocal active
        if active is None or active.get('wire_started') is not None:
            return web.json_response({'error': 'Unexpected extra request'}, status=409)
        row = active
        finished = row['relay_finished']
        row['wire_started'] = time.perf_counter()
        incoming = await request.json()
        row['received_body_hash'] = digest(incoming)
        row['received_fields'] = sorted(incoming)
        row['received_message_chars'] = len(json.dumps(incoming.get('messages', [])))
        row['upstream_body_hash'] = digest(canonical)
        row['dispatch_to_wire_ms'] = (row['wire_started'] - row['start']) * 1000
        connection = id(request.transport)
        row['client_socket_reused'] = connection in relay_sockets
        relay_sockets[connection] = request.transport
        meter = SSEMeter()
        response = web.StreamResponse(headers={'Content-Type': 'text/event-stream'})
        try:
            if options.mock:
                await response.prepare(request)
                await asyncio.sleep(0.05)
                for i in range(20):
                    event = {
                        'id': 'synthetic',
                        'object': 'chat.completion.chunk',
                        'created': 1,
                        'model': options.model,
                        'choices': [{'index': 0, 'delta': {'content': 'word '}, 'finish_reason': None}],
                    }
                    data = ('data: ' + json.dumps(event) + '\n\n').encode()
                    meter.feed(data, time.perf_counter())
                    await response.write(data)
                    await asyncio.sleep(0.03)
                event['choices'] = [{'index': 0, 'delta': {}, 'finish_reason': 'stop'}]
                event['usage'] = {'prompt_tokens': 50, 'completion_tokens': 20, 'total_tokens': 70}
                data = ('data: ' + json.dumps(event) + '\n\ndata: [DONE]\n\n').encode()
                meter.feed(data, time.perf_counter())
                await response.write(data)
            else:
                async with upstream.stream(
                    'POST',
                    base_url.rstrip('/') + '/chat/completions',
                    content=payload,
                    headers={'Authorization': 'Bearer ' + key, 'Content-Type': 'application/json'},
                ) as remote:
                    row['status'] = remote.status_code
                    if remote.status_code != 200:
                        await remote.aread()
                        # Do not log upstream response bodies, headers or credentials.
                        return web.json_response(
                            {'error': f'Upstream HTTP {remote.status_code}'}, status=remote.status_code
                        )
                    row['upstream_headers_ms'] = (time.perf_counter() - row['wire_started']) * 1000
                    await response.prepare(request)
                    async for chunk in remote.aiter_bytes():
                        meter.feed(chunk, time.perf_counter())
                        try:
                            await response.write(chunk)
                        except ConnectionResetError:
                            row['client_closed_before_http_eof'] = True
            row['upstream_ttft_ms'] = (
                (meter.first_content - row['wire_started']) * 1000 if meter.first_content is not None else None
            )
            row['ttft_ms'] = (meter.first_content - row['start']) * 1000 if meter.first_content is not None else None
            row['usage'] = meter.usage
            row['content_chars'] = meter.content_chars
            row['upstream_complete_ms'] = (time.perf_counter() - row['wire_started']) * 1000
            with contextlib.suppress(ConnectionResetError):
                await response.write_eof()
            return response
        finally:
            finished.set()

    app = web.Application()
    app.router.add_post('/v1/chat/completions', relay)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '127.0.0.1', 0)
    await site.start()
    local = f'http://127.0.0.1:{site._server.sockets[0].getsockname()[1]}/v1'
    adapter = LiteLLMRequester(
        SimpleNamespace(),
        {'custom_llm_provider': 'openai', 'base_url': local, 'requester_name': 'new-api-chat-completions'},
    )
    await adapter.initialize()
    if options.baseline_no_drain:
        adapter._http_pool.drain_sse = False
    model = SimpleNamespace(
        model_entity=SimpleNamespace(name=options.model, extra_args={}, reasoning_config=None, abilities=[]),
        reasoning_config_override=None,
        provider=SimpleNamespace(
            token_mgr=SimpleNamespace(get_token=lambda: 'local-benchmark'),
            provider_entity=SimpleNamespace(requester='new-api-chat-completions'),
        ),
    )
    messages = [Message(role=x['role'], content=x['content']) for x in canonical['messages']]
    process = None
    with tempfile.TemporaryDirectory(prefix='langbot-llm-benchmark-') as directory:
        root = Path(directory)
        config = {
            'model': f'bench/{options.model}',
            'small_model': f'bench/{options.model}',
            'autoupdate': False,
            'provider': {
                'bench': {
                    'npm': '@ai-sdk/openai-compatible',
                    'name': 'Benchmark',
                    'options': {'baseURL': local, 'apiKey': 'local-benchmark'},
                    'models': {options.model: {'name': 'Benchmark', 'limit': {'context': 200000, 'output': 256}}},
                }
            },
            'agent': {'bench': {'mode': 'primary', 'prompt': prefix, 'tools': {'*': False}, 'steps': 2}},
            'permission': {'*': 'deny'},
        }
        config_path = root / 'opencode.json'
        config_path.write_text(json.dumps(config))
        env = os.environ.copy()
        server_password = secrets.token_urlsafe(24)
        env.update(
            {
                'OPENCODE_CONFIG': str(config_path),
                'XDG_CONFIG_HOME': str(root / 'config'),
                'XDG_DATA_HOME': str(root / 'data'),
                'XDG_CACHE_HOME': str(root / 'cache'),
                'NO_PROXY': os.environ.get('NO_PROXY', ''),
                'OPENCODE_SERVER_PASSWORD': server_password,
            }
        )
        port = free_port()
        server = f'http://127.0.0.1:{port}'
        log = (root / 'server.log').open('w')
        try:
            start_server = time.perf_counter()
            process = await asyncio.create_subprocess_exec(
                options.opencode,
                'serve',
                '--hostname',
                '127.0.0.1',
                '--port',
                str(port),
                cwd=root,
                env=env,
                stdout=log,
                stderr=log,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0,
            )
            async with httpx.AsyncClient(trust_env=False, timeout=100, auth=('opencode', server_password)) as client:
                for _ in range(120):
                    try:
                        response = await client.get(server + '/api/info')
                        if response.is_success:
                            break
                    except httpx.ConnectError:
                        pass
                    await asyncio.sleep(0.25)
                else:
                    raise RuntimeError('Isolated OpenCode server did not start')
                startup_ms = (time.perf_counter() - start_server) * 1000
                orders = list(itertools.permutations(('direct', 'langbot', 'opencode')))
                for round_index in range(-1, options.rounds):
                    for name in orders[max(0, round_index) % len(orders)]:
                        session_id = None
                        if name == 'opencode':
                            response = await client.post(
                                server + '/api/session',
                                json={
                                    'title': 'LLM benchmark',
                                    'agent': 'bench',
                                    'model': {'id': options.model, 'providerID': 'bench'},
                                    'location': {'directory': str(root)},
                                },
                            )
                            response.raise_for_status()
                            session_id = response.json()['data']['id']
                        row = {
                            'client': name,
                            'round': round_index,
                            'warmup': round_index < 0,
                            'start': time.perf_counter(),
                            'relay_finished': asyncio.Event(),
                        }
                        active = row
                        if name == 'direct':
                            meter = SSEMeter()
                            async with client.stream('POST', local + '/chat/completions', json=canonical) as response:
                                response.raise_for_status()
                                async for chunk in response.aiter_bytes():
                                    meter.feed(chunk, time.perf_counter())
                            row['consumer_first_content_ms'] = (meter.first_content - row['start']) * 1000
                        elif name == 'langbot':
                            state = CallState(RequestPolicy(retries=0, total_timeout=90))
                            token = current_call.set(state)
                            try:
                                async with contextlib.aclosing(
                                    adapter.invoke_llm_stream(
                                        None, model, messages, extra_args={'temperature': 0, 'max_tokens': 256}
                                    )
                                ) as stream:
                                    async for chunk in stream:
                                        if chunk.content and 'consumer_first_content_ms' not in row:
                                            row['consumer_first_content_ms'] = (
                                                time.perf_counter() - row['start']
                                            ) * 1000
                                row['preparation_ms'] = state.metrics.get('preparation_ms')
                                row['transport_setup_ms'] = state.metrics.get('transport_setup_ms')
                                row['client_usage'] = state.usage
                            finally:
                                current_call.reset(token)
                        else:
                            response = await client.post(
                                server + f'/api/session/{session_id}/prompt',
                                json={'text': canonical['messages'][-1]['content']},
                            )
                            response.raise_for_status()
                            await asyncio.wait_for(row['relay_finished'].wait(), 100)
                        if name != 'opencode':
                            row['consumer_total_ms'] = (time.perf_counter() - row['start']) * 1000
                        await asyncio.wait_for(row['relay_finished'].wait(), 100)
                        if 'upstream_complete_ms' not in row:
                            raise RuntimeError(f'Incomplete benchmark response (HTTP {row.get("status", "unknown")})')
                        # Use one completion boundary for all clients. This
                        # relay cannot measure OpenCode's UI rendering latency.
                        row['total_ms'] = row['dispatch_to_wire_ms'] + row['upstream_complete_ms']
                        row.pop('relay_finished')
                        row.pop('start')
                        row.pop('wire_started', None)
                        records.append(row)
                        active = None
                        print(json.dumps(row), flush=True)
                        await asyncio.sleep(0.1)
                report = {
                    'model': options.model,
                    'base_url': base_url,
                    'mock': options.mock,
                    'long_prefix': options.long_prefix,
                    'cache_control': options.cache_control,
                    'baseline_no_drain': options.baseline_no_drain,
                    'canonical_sha256': digest(canonical),
                    'canonical_bytes': len(payload),
                    'python_import_ms': import_ms,
                    'opencode_startup_ms': startup_ms,
                    'litellm': importlib.metadata.version('litellm'),
                    'opencode': options.opencode_version,
                    'records': records,
                    'summary': summary(records),
                }
                Path(options.output).write_text(json.dumps(report, indent=2), encoding='utf-8')
                print('SUMMARY', json.dumps(report['summary']), flush=True)
        finally:
            if process and process.returncode is None:
                process.terminate()
                await process.wait()
            log.close()
            await adapter.aclose()
            await upstream.aclose()
            await runner.cleanup()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--opencode', required=True)
    parser.add_argument('--opencode-version', default='unknown')
    parser.add_argument('--model', default='claude-haiku-4.5')
    parser.add_argument('--base-url')
    parser.add_argument('--credentials-file')
    parser.add_argument('--api-key-env', default='LLM_BENCHMARK_API_KEY')
    parser.add_argument('--rounds', type=int, default=6)
    parser.add_argument('--mock', action='store_true')
    parser.add_argument('--long-prefix', action='store_true')
    parser.add_argument('--cache-control', action='store_true')
    parser.add_argument('--baseline-no-drain', action='store_true', help='Reproduce the pre-fix stream transport')
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    if not 1 <= args.rounds <= 12:
        parser.error('--rounds must be between 1 and 12 (plus one warmup round)')
    os.environ['NO_PROXY'] = ','.join(filter(None, [os.environ.get('NO_PROXY'), '127.0.0.1', 'localhost']))
    asyncio.run(run(args))
