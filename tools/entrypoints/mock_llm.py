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
import socket
import struct
import threading
import time
import uuid


MAX_BODY_BYTES = 1024 * 1024
USAGE = {'prompt_tokens': 10, 'completion_tokens': 5, 'total_tokens': 15}
GROUP_TURN = re.compile(r'LB_GROUP=(\S+) LB_TURN=(\d+) LB_TOKEN=([a-f0-9]+) LB_PREVIOUS=(none|[a-f0-9]+)')
SCOPE_MARKER = re.compile(r'\bLB_MOCK_SCOPE=([^\s]+)')
SCOPE_ID = re.compile(r'[A-Za-z0-9_.:-]{1,128}')
MAX_FAULT_SCOPES = 2048
FAULT_SCOPE_TTL_SECONDS = 3600


class StreamDisconnected(Exception):
    """The mock deliberately closed an unfinished HTTP chunked response."""


def fault_scope(body, embedding):
    if 'mock_scope' in body:
        scope = body['mock_scope']
    else:
        if not embedding:
            text = next(
                (message.get('content', '') for message in reversed(body['messages']) if message.get('role') == 'user'),
                '',
            )
        else:
            text = body.get('input', '')
        if isinstance(text, list):
            text = '\n'.join(str(item.get('text', '') if isinstance(item, dict) else item) for item in text)
        scopes = set(SCOPE_MARKER.findall(str(text)))
        if len(scopes) > 1:
            raise ValueError('request contains conflicting LB_MOCK_SCOPE markers')
        scope = next(iter(scopes), None)
    if scope is not None and (not isinstance(scope, str) or not SCOPE_ID.fullmatch(scope)):
        raise ValueError('mock_scope must contain 1..128 letters, digits, or _.:-')
    return scope


def _text_parts(content):
    if isinstance(content, str):
        return [content]
    if not isinstance(content, list):
        return []
    return [part['text'] for part in content if isinstance(part, dict) and isinstance(part.get('text'), str)]


def group_markers(message):
    """Deduplicate equivalent representations within one provider user message, never across turns."""
    if message.get('role') != 'user':
        return []
    return list(
        dict.fromkeys(
            match.groups() for text in _text_parts(message.get('content')) for match in GROUP_TURN.finditer(text)
        )
    )


def group_ack(messages, start):
    """Require a real previous user turn and reply, with no other group's history."""
    turns = [(index, *marker) for index, message in enumerate(messages) for marker in group_markers(message)]
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


def _typed_payloads(message, kind):
    for text in _text_parts(message.get('content')):
        for line in text.splitlines():
            if not line.lstrip().startswith('{'):
                continue
            try:
                context = json.loads(line)
            except ValueError:
                continue
            if isinstance(context, dict) and context.get('type') == kind:
                yield context


def retrieved_context_contains(message, expected):
    """Match only JSON retrieval chunks merged into this model user turn."""
    for context in _typed_payloads(message, 'langbot_retrieved_context'):
        data = context.get('data')
        chunks = data.get('chunks') if isinstance(data, dict) else None
        if isinstance(chunks, list) and any(
            isinstance(chunk, dict) and isinstance(chunk.get('content'), str) and expected in chunk['content']
            for chunk in chunks
        ):
            return True
    return False


def current_image_ref(message):
    """Resolve the opaque reference from this user turn, not a guessed path or earlier turn."""
    attachments = [
        attachment
        for context in _typed_payloads(message, 'langbot_input_attachments')
        for attachment in (context['attachments'] if isinstance(context.get('attachments'), list) else [])
        if isinstance(attachment, dict)
        and attachment.get('type') == 'image'
        and attachment.get('mime_type') == 'image/png'
        and attachment.get('source') == 'message'
    ]
    if len(attachments) != 1 or not isinstance(attachments[0].get('ref'), str):
        raise ValueError('current model user message lacks exactly one expected image reference')
    ref = attachments[0]['ref']
    if not re.fullmatch(r'[A-Za-z0-9_.:-]{1,160}', ref):
        raise ValueError('current model image reference has unexpected shape')
    return ref


def _has_exact_image(messages, expected):
    images = [
        part.get('image_url')
        for message in messages
        if message.get('role') == 'user' and isinstance(message.get('content'), list)
        for part in message['content']
        if isinstance(part, dict) and part.get('type') == 'image_url'
    ]
    return len(images) == 1 and isinstance(images[0], dict) and images[0].get('url') == expected


def select_message(body, scenario):
    messages = body.get('messages')
    if not isinstance(messages, list) or not messages or any(not isinstance(m, dict) for m in messages):
        raise ValueError('messages must be a non-empty array of objects')
    if not isinstance(body.get('stream', False), bool):
        raise ValueError('stream must be a boolean')
    if body.get('stream_options') is not None and not isinstance(body['stream_options'], dict):
        raise ValueError('stream_options must be an object')
    scope = fault_scope(body, False) if scenario.get('substitute_mock_scope') else None
    if scenario.get('substitute_mock_scope') and scope is None:
        raise ValueError('this scenario requires mock_scope or LB_MOCK_SCOPE for tool file isolation')
    # Select from the current turn's history, never a shared request counter.
    start = next(
        (i for i in range(len(messages) - 1, -1, -1) if messages[i].get('role') == 'user'),
        None,
    )
    if start is None:
        raise ValueError('a user message is required')
    if scenario.get('read_current_image'):
        # LocalAgent appends a dedicated provider user-image message after a
        # multimodal tool result. Anchor to the real signed turn, not that
        # synthetic follow-up that has no user marker.
        start = next((i for i in range(start, -1, -1) if group_markers(messages[i])), start)
        attachment_ref = current_image_ref(messages[start])
    else:
        attachment_ref = None
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
    memory_marker = None
    if scenario.get('session_memory'):
        marker = group_markers(messages[start])
        if len(marker) != 1:
            raise ValueError('memory transaction needs one signed group marker')
        group, turn_number, _, _ = marker[0]
        memory_marker = 'QA session memory ' + group
        if int(turn_number) == 1:
            steps = scenario['first_turn_steps']
    if len(calls) >= len(steps):
        raise ValueError('tool history exceeds the configured scenario')
    step = steps[len(calls)]
    if expected_prompt := step.get('expect_prompt'):
        if expected_prompt not in json.dumps(messages, ensure_ascii=False):
            raise ValueError(f'model input must contain {expected_prompt!r}')
    if expected_retrieved := step.get('expect_current_retrieved'):
        if not retrieved_context_contains(messages[start], expected_retrieved):
            raise ValueError('current model user message lacks the expected retrieved chunk')
    if expected_image := step.get('expect_tool_image'):
        results = turn[calls[-1] + 1 :] if calls else []
        position = next((index for index, item in enumerate(results) if item.get('role') == 'tool'), None)
        if position is None or not _has_exact_image(results[position + 1 :], expected_image):
            raise ValueError('current attachment tool result must carry the exact expected image')
    if any(value in json.dumps(messages, ensure_ascii=False) for value in step.get('forbid_prompt', [])):
        raise ValueError('model input contains forbidden knowledge content')
    expected = step.get('expect_tool_output')
    if expected is not None:
        results = turn[calls[-1] + 1 :] if calls else []
        result_text = '\n'.join(str(m.get('content', '')) for m in results if m.get('role') == 'tool')
        if expected not in result_text:
            raise ValueError(f'tool result must contain {expected!r}')
    if memory_marker and (step.get('expect_memory_write') or step.get('expect_memory_episode')):
        results = turn[calls[-1] + 1 :] if calls else []
        text = '\n'.join(
            part for msg in results if msg.get('role') == 'tool' for part in _text_parts(msg.get('content'))
        )
        if step.get('expect_memory_write') and text != 'Remembered: ' + memory_marker:
            raise ValueError('remember did not return the exact current group receipt')
        if step.get('expect_memory_episode'):
            try:
                episodes = json.loads(text)['episodes']
            except (ValueError, KeyError, TypeError) as error:
                raise ValueError('recall did not return structured episodes') from error
            if (
                not isinstance(episodes, list)
                or len(episodes) != 1
                or not isinstance(episodes[0], dict)
                or episodes[0].get('content') != memory_marker
            ):
                raise ValueError('recall did not return exactly the current session memory')
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

        def arguments(call):
            value = dict(call['arguments'])
            if call['name'] == 'langbot_read_input_attachment' and value.get('ref') == '{current_image_ref}':
                if attachment_ref is None:
                    raise ValueError('tool expected a current image reference')
                value['ref'] = attachment_ref
            if memory_marker:
                value = {k: memory_marker if v == '{memory_marker}' else v for k, v in value.items()}
            encoded = json.dumps(value)
            return encoded.replace('{mock_scope}', scope) if scope is not None else encoded

        message['tool_calls'] = [
            {
                'id': f'call_mock_{len(calls)}_{i}',
                'type': 'function',
                'function': {
                    'name': call['name'],
                    'arguments': arguments(call),
                },
            }
            for i, call in enumerate(tool_calls)
        ]
    return message


class MockServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, address, scenarios, record_path=None):
        validate_scenarios(scenarios)
        super().__init__(address, Handler)
        self.scenarios = {'mock-embedding': {'kind': 'embedding'}, **scenarios}
        self.record_path = record_path
        self.record_lock = threading.Lock()
        self.fault_lock = threading.Lock()
        self.fault_scopes = {}

    def fault_controls(self, body, scenario, entry):
        scope = fault_scope(body, entry['path'] == '/v1/embeddings')
        entry['scope'] = scope
        if 'recover_after' not in scenario:
            return scenario
        if scope is None:
            raise ValueError('recovery scenarios require mock_scope or LB_MOCK_SCOPE')
        key = (entry['path'], body['model'], scope)
        now = time.monotonic()
        with self.fault_lock:
            for expired in [
                key for key, (_, touched) in self.fault_scopes.items() if now - touched >= FAULT_SCOPE_TTL_SECONDS
            ]:
                del self.fault_scopes[expired]
            if key not in self.fault_scopes and len(self.fault_scopes) >= MAX_FAULT_SCOPES:
                raise ValueError('mock fault scope limit reached; release completed scopes first')
            attempt = self.fault_scopes.get(key, (0, now))[0] + 1
            self.fault_scopes[key] = (attempt, now)
        entry.update(attempt=attempt, fault_active=attempt <= scenario['recover_after'])
        return scenario if entry['fault_active'] else {}

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
                        for name in self.server.scenarios
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

    def do_DELETE(self):
        prefix = '/_mock/scopes/'
        scope = self.path.removeprefix(prefix)
        if not self.path.startswith(prefix) or not SCOPE_ID.fullmatch(scope):
            self.json_response(400, {'error': {'message': 'use DELETE /_mock/scopes/<scope>'}})
            return
        with self.server.fault_lock:
            keys = [key for key in self.server.fault_scopes if key[2] == scope]
            for key in keys:
                del self.server.fault_scopes[key]
        self.json_response(200, {'scope': scope, 'released': len(keys)})

    def delay(self, seconds, kind, entry):
        if seconds:
            start = time.monotonic()
            time.sleep(seconds)
            entry['faults'].append({'kind': kind, 'seconds': seconds, 'elapsed_seconds': time.monotonic() - start})

    def do_POST(self):
        started = time.monotonic()
        entry = {
            'request_id': uuid.uuid4().hex,
            'time': time.time(),
            'path': self.path,
            'status': 400,
            'faults': [],
            'response_complete': False,
        }
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
                entry['response_complete'] = True
                return
            self.connection.settimeout(10)
            length = int(self.headers.get('Content-Length', 0))
            if self.headers.get('Transfer-Encoding') or not 0 < length <= MAX_BODY_BYTES:
                raise ValueError('a Content-Length between 1 and 1048576 is required')
            body = json.loads(self.rfile.read(length))
            if not isinstance(body, dict) or not isinstance(body.get('model'), str):
                raise ValueError('request must be an object with a model name')
            entry['request'] = body
            scenario = self.server.scenarios.get(body['model'])
            if scenario is None:
                raise ValueError('unknown model; use GET /v1/models')
            embedding = self.path == '/v1/embeddings'
            if embedding != (scenario.get('kind') == 'embedding'):
                raise ValueError('model does not support this endpoint')
            if embedding:
                payload = mock_embeddings(body)
            else:
                message = select_message(body, scenario)
                if not body.get('stream') and (
                    'disconnect_after_chunks' in scenario or 'stall_after_chunks' in scenario
                ):
                    raise ValueError('this fault scenario requires stream=true')
            controls = self.server.fault_controls(body, scenario, entry)
            self.delay(controls.get('delay_seconds', 0), 'delay', entry)
            status = controls.get('status', 200)
            entry['status'] = status
            if status != 200:
                entry['faults'].append({'kind': 'http_error', 'status': status})
                entry['response'] = {
                    'error': {'message': 'injected mock failure', 'type': 'api_error', 'code': str(status)}
                }
                self.json_response(status, entry['response'])
                entry['response_complete'] = True
                return
            if embedding:
                if fault := controls.get('embedding_fault'):
                    if fault == 'count':
                        payload['data'].pop()
                    else:
                        dimensions = body.get('dimensions', 384)
                        payload = mock_embeddings({**body, 'dimensions': dimensions - 1 if dimensions > 1 else 2})
                    entry['faults'].append({'kind': 'embedding_' + fault})
                entry['response'] = payload
                self.json_response(200, payload)
                entry['response_complete'] = True
                return
            entry['response'] = message
            base = {
                'id': 'chatcmpl-' + entry['request_id'],
                'created': int(time.time()),
                'model': body['model'],
            }
            finish = 'tool_calls' if message.get('tool_calls') else 'stop'
            if body.get('stream'):
                self.stream_response(body, controls, message, base, finish, entry)
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
            entry['response_complete'] = True
        except StreamDisconnected:
            entry['injected_disconnect'] = True
        except (ValueError, KeyError, TypeError, TimeoutError) as exc:
            entry.update(status=400, error=str(exc))
            self.json_response(400, {'error': {'message': str(exc), 'type': 'invalid_request_error'}})
            entry['response_complete'] = True
        except (BrokenPipeError, ConnectionResetError):
            entry['disconnected'] = True
        finally:
            entry['duration_seconds'] = time.monotonic() - started
            self.server.record(entry)

    def stream_response(self, body, scenario, message, base, finish, entry):
        chunked = 'disconnect_after_chunks' in scenario
        if chunked:
            self.protocol_version = 'HTTP/1.1'
        self.send_response(200)
        self.send_header('Content-Type', 'text/event-stream')
        self.send_header('Cache-Control', 'no-cache')
        if chunked:
            self.send_header('Transfer-Encoding', 'chunked')
        self.end_headers()

        def write(data):
            if chunked:
                data = f'{len(data):x}\r\n'.encode() + data + b'\r\n'
            self.wfile.write(data)
            self.wfile.flush()

        def send(delta, reason=None):
            payload = {
                **base,
                'object': 'chat.completion.chunk',
                'choices': [{'index': 0, 'delta': delta, 'finish_reason': reason}],
            }
            write(('data: ' + json.dumps(payload, ensure_ascii=False) + '\n\n').encode())
            entry['stream_chunks'] = entry.get('stream_chunks', 0) + 1
            if entry['stream_chunks'] == scenario.get('disconnect_after_chunks'):
                entry['faults'].append({'kind': 'stream_disconnect', 'after_chunks': entry['stream_chunks']})
                self.close_connection = True
                self.connection.shutdown(socket.SHUT_RDWR)
                raise StreamDisconnected
            if entry['stream_chunks'] == scenario.get('stall_after_chunks'):
                self.delay(scenario['stall_seconds'], 'stream_stall', entry)
            self.delay(scenario.get('chunk_delay_seconds', 0), 'chunk_delay', entry)

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
            write(('data: ' + json.dumps(payload) + '\n\n').encode())
        write(b'data: [DONE]\n\n')
        if chunked:
            self.wfile.write(b'0\r\n\r\n')
            self.wfile.flush()


def validate_scenarios(scenarios):
    if not isinstance(scenarios, dict) or not scenarios:
        raise ValueError('scenarios must be a non-empty object keyed by model name')
    for name, scenario in scenarios.items():
        if not isinstance(scenario, dict):
            raise ValueError(f'{name}: scenario must be an object')
        if scenario.get('kind', 'chat') not in ('chat', 'embedding'):
            raise ValueError(f'{name}: kind must be chat or embedding')
        if 'read_current_image' in scenario and type(scenario['read_current_image']) is not bool:
            raise ValueError(f'{name}: read_current_image must be boolean')
        if 'substitute_mock_scope' in scenario and not isinstance(scenario['substitute_mock_scope'], bool):
            raise ValueError(f'{name}: substitute_mock_scope must be a boolean')
        steps = scenario.get('steps', [])
        if not isinstance(steps, list) or (not steps and scenario.get('kind') != 'embedding'):
            raise ValueError(f'{name}: steps must be a non-empty array')
        if any(not isinstance(step, dict) for step in steps):
            raise ValueError(f'{name}: each step must be an object')
        if 'session_memory' in scenario:
            first = scenario.get('first_turn_steps')
            if scenario['session_memory'] is not True or not isinstance(first, list) or len(first) != 3:
                raise ValueError(f'{name}: session_memory requires three first_turn_steps')
            if not all(isinstance(step, dict) for step in first):
                raise ValueError(f'{name}: first_turn_steps must be objects')
            steps = [*steps, *first]
        for step in steps:
            if not isinstance(step.get('content'), str) and not step.get('tool_calls'):
                raise ValueError(f'{name}: each step needs content or tool_calls')
            if 'expect_tool_output' in step and not isinstance(step['expect_tool_output'], str):
                raise ValueError(f'{name}: expect_tool_output must be a string')
            if 'expect_prompt' in step and not isinstance(step['expect_prompt'], str):
                raise ValueError(f'{name}: expect_prompt must be a string')
            if 'expect_current_retrieved' in step and (
                not isinstance(step['expect_current_retrieved'], str)
                or not 1 <= len(step['expect_current_retrieved']) <= 256
            ):
                raise ValueError(f'{name}: expect_current_retrieved must be a non-empty fixture marker')
            if 'expect_tool_image' in step:
                image = step['expect_tool_image']
                prefix = 'data:image/png;base64,'
                if not isinstance(image, str) or not image.startswith(prefix) or not len(prefix) < len(image) <= 4096:
                    raise ValueError(f'{name}: expect_tool_image must be a small PNG data URL')
                try:
                    image_bytes = base64.b64decode(image.removeprefix(prefix), validate=True)
                except ValueError as error:
                    raise ValueError(f'{name}: expect_tool_image has malformed base64') from error
                if not image_bytes.startswith(b'\x89PNG\r\n\x1a\n'):
                    raise ValueError(f'{name}: expect_tool_image must start with a PNG header')
            if 'forbid_prompt' in step and (
                not isinstance(step['forbid_prompt'], list)
                or any(not isinstance(value, str) or not value for value in step['forbid_prompt'])
            ):
                raise ValueError(f'{name}: forbid_prompt must contain non-empty strings')
            if 'tool_calls' in step:
                calls = step['tool_calls']
                if not isinstance(calls, list) or any(
                    not isinstance(call, dict)
                    or not isinstance(call.get('name'), str)
                    or not isinstance(call.get('arguments'), dict)
                    for call in calls
                ):
                    raise ValueError(f'{name}: tool_calls need a name and arguments object')
        if type(scenario.get('status', 200)) is not int or scenario.get('status', 200) not in (200, 401, 429, 500, 503):
            raise ValueError(f'{name}: unsupported injected HTTP status')
        for key in ('delay_seconds', 'chunk_delay_seconds', 'stall_seconds'):
            value = scenario.get(key, 0)
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not 0 <= value <= 60:
                raise ValueError(f'{name}: {key} must be between 0 and 60')
        for key in ('recover_after', 'disconnect_after_chunks', 'stall_after_chunks'):
            if key in scenario and (type(scenario[key]) is not int or not 1 <= scenario[key] <= 100):
                raise ValueError(f'{name}: {key} must be an integer in 1..100')
        if ('stall_after_chunks' in scenario) != ('stall_seconds' in scenario):
            raise ValueError(f'{name}: stall_after_chunks and stall_seconds must be set together')
        if scenario.get('embedding_fault') not in (None, 'count', 'dimension'):
            raise ValueError(f'{name}: embedding_fault must be count or dimension')
        if scenario.get('kind') == 'embedding':
            if any(key in scenario for key in ('disconnect_after_chunks', 'stall_after_chunks', 'chunk_delay_seconds')):
                raise ValueError(f'{name}: embedding scenarios cannot set stream controls')
        elif 'embedding_fault' in scenario:
            raise ValueError(f'{name}: embedding_fault requires kind=embedding')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--port', type=int, default=18080)
    parser.add_argument(
        '--scenarios',
        type=Path,
        default=Path(__file__).resolve().parents[1] / 'fixtures' / 'mock_llm_scenarios.json',
    )
    parser.add_argument(
        '--record',
        type=Path,
        help='Append request/response JSONL without HTTP headers; use test data only',
    )
    args = parser.parse_args()
    scenarios = json.loads(args.scenarios.read_text(encoding='utf-8'))
    try:
        validate_scenarios(scenarios)
    except ValueError as exc:
        parser.error(str(exc))
    with MockServer((args.host, args.port), scenarios, args.record) as server:
        print(f'Mock LLM: http://{args.host}:{server.server_port}/v1', flush=True)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass


if __name__ == '__main__':
    main()
