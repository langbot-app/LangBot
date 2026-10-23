#!/usr/bin/env python3
"""A deterministic OpenAI Chat Completions server for local regression tests."""

import argparse
import base64
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import math
from pathlib import Path
import re
import struct
import threading
import time
import uuid


MAX_BODY_BYTES = 1024 * 1024
USAGE = {'prompt_tokens': 10, 'completion_tokens': 5, 'total_tokens': 15}
GROUP_TURN = re.compile(r'LB_GROUP=(\S+) LB_TURN=(\d+) LB_TOKEN=([a-f0-9]+) LB_PREVIOUS=(none|[a-f0-9]+)')


def group_ack(messages, start):
    """Require a real previous user turn and reply, with no other group's history."""
    turns = []
    for index, message in enumerate(messages):
        if message.get('role') == 'user':
            for match in GROUP_TURN.finditer(str(message.get('content', ''))):
                turns.append((index, *match.groups()))
    if not turns:
        return ''
    position, group, turn, token, previous = turns[-1]
    if position != start or any(item[1] != group for item in turns):
        raise ValueError('group history contains another group or lacks the current turn')
    if int(turn) == 1:
        if len(turns) != 1 or previous != 'none':
            raise ValueError('first group turn must have an empty history')
    else:
        if len(turns) < 2:
            raise ValueError('previous group turn is missing from model history')
        prior_position, _, prior_turn, prior_token, _ = turns[-2]
        replies = messages[prior_position + 1 : start]
        if (
            int(prior_turn) != int(turn) - 1
            or prior_token != previous
            or not any(
                message.get('role') == 'assistant' and f'GROUP_ACK={previous}' in str(message.get('content', ''))
                for message in replies
            )
        ):
            raise ValueError('previous group turn or assistant acknowledgement does not match')
    return f' GROUP_ACK={token}'


def mock_embeddings(body):
    """Return deterministic normalized token hashes, not semantic model inference."""
    inputs = body.get('input')
    inputs = [inputs] if isinstance(inputs, str) else inputs
    if (
        not isinstance(inputs, list)
        or not 1 <= len(inputs) <= 128
        or any(not isinstance(text, str) or not text for text in inputs)
    ):
        raise ValueError('embedding input must contain 1..128 non-empty strings')
    dimensions = body.get('dimensions', 384)
    if isinstance(dimensions, bool) or not isinstance(dimensions, int) or not 1 <= dimensions <= 4096:
        raise ValueError('embedding dimensions must be an integer in 1..4096')
    encoding = body.get('encoding_format', 'float')
    if encoding not in ('float', 'base64'):
        raise ValueError('embedding encoding_format must be float or base64')
    data = []
    for index, text in enumerate(inputs):
        vector = [0.0] * dimensions
        for token in re.findall(r'\w+', text.casefold()) or [text]:
            digest = hashlib.sha256(token.encode()).digest()
            vector[int.from_bytes(digest[:4], 'little') % dimensions] += 1 if digest[4] % 2 else -1
        norm = math.sqrt(sum(value * value for value in vector))
        if not norm:
            vector[0], norm = 1.0, 1.0
        vector = [value / norm for value in vector]
        embedding = (
            base64.b64encode(struct.pack(f'<{dimensions}f', *vector)).decode() if encoding == 'base64' else vector
        )
        data.append({'object': 'embedding', 'index': index, 'embedding': embedding})
    return {'object': 'list', 'model': body['model'], 'data': data, 'usage': {'prompt_tokens': 10, 'total_tokens': 10}}


def select_message(body, scenario):
    messages = body.get('messages')
    if not isinstance(messages, list) or not messages or any(not isinstance(m, dict) for m in messages):
        raise ValueError('messages must be a non-empty array of objects')
    if not isinstance(body.get('stream', False), bool):
        raise ValueError('stream must be a boolean')
    if body.get('stream_options') is not None and not isinstance(body['stream_options'], dict):
        raise ValueError('stream_options must be an object')
    # Select from the current turn's history, never a shared request counter.
    start = next(
        (i for i in range(len(messages) - 1, -1, -1) if messages[i].get('role') == 'user'),
        None,
    )
    if start is None:
        raise ValueError('a user message is required')
    acknowledgement = group_ack(messages, start)
    turn = messages[start:]
    calls = [i for i, m in enumerate(turn) if m.get('role') == 'assistant' and m.get('tool_calls')]
    for index, position in enumerate(calls):
        end = calls[index + 1] if index + 1 < len(calls) else len(turn)
        requested = {call['id'] for call in turn[position]['tool_calls']}
        returned = [m.get('tool_call_id') for m in turn[position + 1 : end] if m.get('role') == 'tool']
        if len(returned) != len(requested) or set(returned) != requested:
            raise ValueError('each tool call must have exactly one matching tool result')
    steps = scenario['steps']
    if len(calls) >= len(steps):
        raise ValueError('tool history exceeds the configured scenario')
    step = steps[len(calls)]
    if expected_prompt := step.get('expect_prompt'):
        if expected_prompt not in json.dumps(messages, ensure_ascii=False):
            raise ValueError(f'model input must contain {expected_prompt!r}')
    expected = step.get('expect_tool_output')
    if expected is not None:
        results = turn[calls[-1] + 1 :] if calls else []
        result_text = '\n'.join(str(m.get('content', '')) for m in results if m.get('role') == 'tool')
        if expected not in result_text:
            raise ValueError(f'tool result must contain {expected!r}')
    content = step.get('content')
    message = {'role': 'assistant', 'content': content + acknowledgement if content is not None else None}
    if tool_calls := step.get('tool_calls'):
        tools = body.get('tools', [])
        if not isinstance(tools, list) or any(
            not isinstance(t, dict) or not isinstance(t.get('function'), dict) for t in tools
        ):
            raise ValueError('tools must be an array of objects')
        available = {t.get('function', {}).get('name') for t in tools if t.get('type') == 'function'}
        if body.get('tool_choice') == 'none' or any(call['name'] not in available for call in tool_calls):
            raise ValueError('scenario tools must be advertised and enabled by the caller')
        message['tool_calls'] = [
            {
                'id': f'call_mock_{len(calls)}_{i}',
                'type': 'function',
                'function': {
                    'name': call['name'],
                    'arguments': json.dumps(call['arguments']),
                },
            }
            for i, call in enumerate(tool_calls)
        ]
    return message


class MockServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, address, scenarios, record_path=None):
        super().__init__(address, Handler)
        self.scenarios = scenarios
        self.record_path = record_path
        self.record_lock = threading.Lock()

    def record(self, entry):
        if self.record_path:
            with (
                self.record_lock,
                self.record_path.open('a', encoding='utf-8') as stream,
            ):
                stream.write(json.dumps(entry, ensure_ascii=False) + '\n')


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *_args):
        pass

    def json_response(self, status, payload):
        data = json.dumps(payload, ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        if self.path == '/healthz':
            self.json_response(200, {'status': 'ok'})
        elif self.path == '/v1/models':
            self.json_response(
                200,
                {
                    'object': 'list',
                    'data': [
                        {
                            'id': name,
                            'object': 'model',
                            'created': 0,
                            'owned_by': 'mock',
                        }
                        for name in [*self.server.scenarios, 'mock-embedding']
                    ],
                },
            )
        else:
            self.json_response(
                404,
                {
                    'error': {
                        'message': 'unknown endpoint',
                        'type': 'invalid_request_error',
                    }
                },
            )

    def do_POST(self):
        entry = {'request_id': uuid.uuid4().hex, 'time': time.time(), 'path': self.path, 'status': 400}
        try:
            if self.path not in ('/v1/chat/completions', '/v1/embeddings'):
                entry['status'] = 404
                self.json_response(
                    404,
                    {
                        'error': {
                            'message': 'unknown endpoint',
                            'type': 'invalid_request_error',
                        }
                    },
                )
                return
            self.connection.settimeout(10)
            length = int(self.headers.get('Content-Length', 0))
            if self.headers.get('Transfer-Encoding') or not 0 < length <= MAX_BODY_BYTES:
                raise ValueError('a Content-Length between 1 and 1048576 is required')
            body = json.loads(self.rfile.read(length))
            if not isinstance(body, dict) or not isinstance(body.get('model'), str):
                raise ValueError('request must be an object with a model name')
            entry['request'] = body
            if self.path == '/v1/embeddings':
                if body['model'] != 'mock-embedding':
                    raise ValueError('embedding model must be mock-embedding')
                payload = mock_embeddings(body)
                entry.update(status=200, response=payload)
                self.json_response(200, payload)
                return
            scenario = self.server.scenarios.get(body['model'])
            if scenario is None:
                raise ValueError('unknown model; use GET /v1/models')
            message = select_message(body, scenario)
            time.sleep(scenario.get('delay_seconds', 0))
            status = scenario.get('status', 200)
            entry['status'] = status
            if status != 200:
                self.json_response(
                    status,
                    {
                        'error': {
                            'message': 'injected mock failure',
                            'type': 'api_error',
                            'code': str(status),
                        }
                    },
                )
                return
            entry['response'] = message
            base = {
                'id': 'chatcmpl-' + entry['request_id'],
                'created': int(time.time()),
                'model': body['model'],
            }
            finish = 'tool_calls' if message.get('tool_calls') else 'stop'
            if body.get('stream'):
                self.stream_response(body, scenario, message, base, finish)
            else:
                self.json_response(
                    200,
                    {
                        **base,
                        'object': 'chat.completion',
                        'choices': [{'index': 0, 'message': message, 'finish_reason': finish}],
                        'usage': USAGE,
                    },
                )
        except (ValueError, KeyError, TypeError, TimeoutError) as exc:
            entry.update(status=400, error=str(exc))
            self.json_response(400, {'error': {'message': str(exc), 'type': 'invalid_request_error'}})
        except (BrokenPipeError, ConnectionResetError):
            entry['disconnected'] = True
        finally:
            self.server.record(entry)

    def stream_response(self, body, scenario, message, base, finish):
        self.send_response(200)
        self.send_header('Content-Type', 'text/event-stream')
        self.send_header('Cache-Control', 'no-cache')
        self.end_headers()

        def send(delta, reason=None):
            payload = {
                **base,
                'object': 'chat.completion.chunk',
                'choices': [{'index': 0, 'delta': delta, 'finish_reason': reason}],
            }
            self.wfile.write(('data: ' + json.dumps(payload, ensure_ascii=False) + '\n\n').encode())
            self.wfile.flush()
            time.sleep(scenario.get('chunk_delay_seconds', 0))

        send({'role': 'assistant'})
        content = message.get('content') or ''
        for offset in range(0, len(content), 8):
            send({'content': content[offset : offset + 8]})
        for index, call in enumerate(message.get('tool_calls', [])):
            send(
                {
                    'tool_calls': [
                        {
                            'index': index,
                            'id': call['id'],
                            'type': 'function',
                            'function': {
                                'name': call['function']['name'],
                                'arguments': '',
                            },
                        }
                    ]
                }
            )
            arguments = call['function']['arguments']
            for offset in range(0, len(arguments), 16):
                send(
                    {
                        'tool_calls': [
                            {
                                'index': index,
                                'function': {'arguments': arguments[offset : offset + 16]},
                            }
                        ]
                    }
                )
        send({}, finish)
        if (body.get('stream_options') or {}).get('include_usage'):
            payload = {
                **base,
                'object': 'chat.completion.chunk',
                'choices': [],
                'usage': USAGE,
            }
            self.wfile.write(('data: ' + json.dumps(payload) + '\n\n').encode())
        self.wfile.write(b'data: [DONE]\n\n')
        self.wfile.flush()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--port', type=int, default=18080)
    parser.add_argument(
        '--scenarios',
        type=Path,
        default=Path(__file__).with_name('mock_llm_scenarios.json'),
    )
    parser.add_argument(
        '--record',
        type=Path,
        help='Append request/response JSONL without HTTP headers; use test data only',
    )
    args = parser.parse_args()
    scenarios = json.loads(args.scenarios.read_text(encoding='utf-8'))
    if not isinstance(scenarios, dict) or not scenarios:
        parser.error('scenarios must be a non-empty object keyed by model name')
    for name, scenario in scenarios.items():
        if not isinstance(scenario, dict) or not isinstance(scenario.get('steps'), list) or not scenario['steps']:
            parser.error(f'{name}: steps must be a non-empty array')
        if any(not isinstance(step, dict) for step in scenario['steps']):
            parser.error(f'{name}: each step must be an object')
        for step in scenario['steps']:
            if not isinstance(step.get('content'), str) and not step.get('tool_calls'):
                parser.error(f'{name}: each step needs content or tool_calls')
            if 'expect_tool_output' in step and not isinstance(step['expect_tool_output'], str):
                parser.error(f'{name}: expect_tool_output must be a string')
            if 'expect_prompt' in step and not isinstance(step['expect_prompt'], str):
                parser.error(f'{name}: expect_prompt must be a string')
            if 'tool_calls' in step:
                calls = step['tool_calls']
                if not isinstance(calls, list) or any(
                    not isinstance(call, dict)
                    or not isinstance(call.get('name'), str)
                    or not isinstance(call.get('arguments'), dict)
                    for call in calls
                ):
                    parser.error(f'{name}: tool_calls need a name and arguments object')
        if scenario.get('status', 200) not in (200, 401, 429, 500, 503):
            parser.error(f'{name}: unsupported injected HTTP status')
        for key in ('delay_seconds', 'chunk_delay_seconds'):
            value = scenario.get(key, 0)
            if not isinstance(value, (int, float)) or not 0 <= value <= 60:
                parser.error(f'{name}: {key} must be between 0 and 60')
    with MockServer((args.host, args.port), scenarios, args.record) as server:
        print(f'Mock LLM: http://{args.host}:{server.server_port}/v1', flush=True)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass


if __name__ == '__main__':
    main()
