"""Native ChatGPT Codex Responses/SSE requester (never Chat Completions)."""

from __future__ import annotations

import asyncio
import json
import secrets
import time
from collections import OrderedDict

import httpx
import langbot
import langbot_plugin.api.entities.builtin.provider.message as pm

from .. import requester, reasoning
from ..codex_auth import BASE_URL, CodexAuth, LOGIN_REQUIRED
from ..codex_errors import CodexProviderError


async def sse_events(response):
    """Decode SSE records, including CRLF, comments, and multiline data."""
    data = []
    size = 0
    async for line in response.aiter_lines():
        if not line:
            if data:
                text = '\n'.join(data)
                if text == '[DONE]':
                    return
                try:
                    event = json.loads(text)
                    if not isinstance(event, dict):
                        raise ValueError
                except ValueError:
                    raise ValueError('Codex returned an invalid stream event') from None
                yield event
            data, size = [], 0
        elif line.startswith('data:'):
            value = line[5:]
            if value.startswith(' '):
                value = value[1:]
            size += len(value)
            if size > 4 * 1024 * 1024:
                raise ValueError('Codex stream event exceeds the size limit')
            data.append(value)
    # SSE requires the blank separator; unterminated records cannot prove completion.


def _content(message):
    content = message.content
    if isinstance(content, str):
        return [{'type': 'output_text' if message.role == 'assistant' else 'input_text', 'text': content}]
    result = []
    for part in content or []:
        if part.type == 'text':
            result.append(
                {'type': 'output_text' if message.role == 'assistant' else 'input_text', 'text': part.text or ''}
            )
        elif part.type == 'image_url' and part.image_url is not None:
            result.append({'type': 'input_image', 'image_url': part.image_url.url})
        elif part.type == 'image_base64' and part.image_base64:
            value = part.image_base64
            result.append(
                {
                    'type': 'input_image',
                    'image_url': value if value.startswith('data:') else 'data:image/png;base64,' + value,
                }
            )
        else:
            raise ValueError('Codex supports text and images only; this message contains unsupported content')
    return result


def _tool(item):
    try:
        return pm.ToolCall(
            id=item['call_id'],
            type='function',
            function=pm.FunctionCall(name=item['name'], arguments=item.get('arguments') or ''),
        )
    except (KeyError, ValueError, TypeError):
        raise ValueError('Codex returned an invalid function call') from None


def _usage(response):
    usage = response.get('usage') or {}
    return {
        'prompt_tokens': usage.get('input_tokens', 0),
        'completion_tokens': usage.get('output_tokens', 0),
        'total_tokens': usage.get('total_tokens', usage.get('input_tokens', 0) + usage.get('output_tokens', 0)),
        'prompt_tokens_details': usage.get('input_tokens_details', {}),
        'completion_tokens_details': usage.get('output_tokens_details', {}),
    }


class CodexRequester(requester.ProviderAPIRequester):
    async def initialize(self):
        self.auth = CodexAuth(self.ap)
        self.workspace = self.requester_cfg['workspace_uuid']
        self.provider = self.requester_cfg['provider_uuid']
        # Opaque replay data stays server-side; handles are scoped to the same query,
        # model and OAuth connection. No token or encrypted reasoning enters messages.
        self._replay = OrderedDict()

    async def aclose(self):
        self._replay.clear()

    def get_reasoning_capabilities(self, model):
        return {
            'supported': True,
            'levels': ['provider_default', 'low', 'medium', 'high', 'xhigh'],
            'source': 'provider',
        }

    @staticmethod
    def _headers(tokens, *, stream=False):
        return {
            'Authorization': 'Bearer ' + tokens['access_token'],
            'ChatGPT-Account-ID': tokens['account_id'],
            'User-Agent': 'LangBot/' + langbot.__version__,
            'originator': 'langbot',
            'OpenAI-Beta': 'responses=experimental',
            'Accept': 'text/event-stream' if stream else 'application/json',
        }

    @staticmethod
    def _http_error(status):
        if status == 401:
            # Upstream authentication is not LangBot authentication: HTTP401 would
            # make the browser discard its own valid user session.
            return CodexProviderError(LOGIN_REQUIRED, 400, 'codex_reauthentication_required')
        if status == 429:
            return CodexProviderError(
                'ChatGPT request was limited (rate limit or usage restriction). Please retry later or check your plan.',
                429,
                'codex_rate_limited',
            )
        if status == 403:
            return CodexProviderError(
                'ChatGPT denied this request. Check subscription and workspace permissions.',
                403,
                'codex_access_denied',
            )
        if status == 400:
            return CodexProviderError(
                'ChatGPT rejected the model or request. Check the selected model and request settings.',
                400,
                'codex_invalid_request',
            )
        return CodexProviderError('ChatGPT Codex upstream request failed. Please retry later.')

    async def _response_error(self, response):
        # Inspect only a bounded 429 error record and an allowlisted machine code.
        # Never expose upstream prose, reset metadata, headers or credentials.
        if response.status_code == 429:
            payload = bytearray()
            async for chunk in response.aiter_bytes():
                if len(payload) + len(chunk) > 8192:
                    return self._http_error(429)
                payload.extend(chunk)
            try:
                data = json.loads(payload)
                error = data.get('error') if isinstance(data, dict) else None
                if isinstance(error, dict) and (
                    error.get('type') == 'usage_limit_reached' or error.get('code') == 'usage_limit_reached'
                ):
                    return CodexProviderError(
                        'ChatGPT subscription usage limit reached. Please retry later or check your plan.',
                        429,
                        'codex_usage_limit_reached',
                    )
            except (ValueError, UnicodeError):
                pass
        return self._http_error(response.status_code)

    def _scope(self, query, model, tokens):
        return (
            id(query),
            getattr(query, 'query_id', None),
            model.model_entity.name,
            tokens.get('connection_id'),
            tokens['account_id'],
        )

    def _body(self, query, model, messages, funcs, extra_args, tokens):
        args = {**(model.model_entity.extra_args or {}), **(extra_args or {})}
        # Never permit credentials, transport overrides, store/history or arbitrary
        # SDK kwargs to be smuggled through model advanced parameters.
        allowed = {'reasoning', 'text', 'parallel_tool_calls', 'tool_choice'}
        unknown = set(args) - allowed
        if unknown:
            raise ValueError('Unsupported Codex advanced parameters: ' + ', '.join(sorted(unknown)))
        instructions = []
        items = []
        scope = self._scope(query, model, tokens)
        for message in messages:
            if message.role in ('system', 'developer'):
                instructions.append('\n'.join(p['text'] for p in _content(message) if 'text' in p))
                continue
            if message.role == 'tool':
                if not message.tool_call_id:
                    raise ValueError('Codex tool results require a tool_call_id')
                output = (
                    message.content
                    if isinstance(message.content, str)
                    else json.dumps([p.model_dump(exclude_none=True) for p in message.content or []])
                )
                items.append({'type': 'function_call_output', 'call_id': message.tool_call_id, 'output': output or ''})
                continue
            if message.role not in ('assistant', 'user'):
                raise ValueError('Unsupported Codex message role')
            handle = (message.provider_specific_fields or {}).get('codex_replay_id')
            cached = self._replay.get(handle) if isinstance(handle, str) else None
            if query is not None and cached and cached[0] == scope and cached[1] > time.time():
                items.extend(cached[2])
                continue
            content = _content(message)
            if content:
                items.append({'type': 'message', 'role': message.role, 'content': content})
            for call in message.tool_calls or []:
                items.append(
                    {
                        'type': 'function_call',
                        'call_id': call.id,
                        'name': call.function.name,
                        'arguments': call.function.arguments,
                    }
                )
        body = {
            **args,
            'model': model.model_entity.name,
            'instructions': '\n\n'.join(instructions),
            'input': items,
            'store': False,
            'stream': True,
            'include': ['reasoning.encrypted_content'],
        }
        level = reasoning.normalize_reasoning_config(getattr(model.model_entity, 'reasoning_config', None))['level']
        if level != 'provider_default':
            reasoning.validate_reasoning_capabilities(
                {'level': level}, self.get_reasoning_capabilities(model), model.model_entity.name
            )
            body['reasoning'] = {'effort': level, 'summary': 'auto'}
        if funcs:
            body['tools'] = [
                {
                    'type': 'function',
                    'name': f.name,
                    'description': f.description,
                    'parameters': f.parameters,
                    'strict': False,
                }
                for f in funcs
            ]
        return body

    async def _events(self, query, model, messages, funcs, extra_args):
        tokens = await self.auth.access(self.workspace, self.provider)
        try:
            async with asyncio.timeout(300), httpx.AsyncClient(timeout=120, follow_redirects=False) as client:
                for attempt in range(2):
                    body = self._body(query, model, messages, funcs, extra_args, tokens)
                    async with client.stream(
                        'POST', BASE_URL + '/responses', json=body, headers=self._headers(tokens, stream=True)
                    ) as response:
                        if response.status_code == 401 and attempt == 0:
                            tokens = await self.auth.access(
                                self.workspace, self.provider, rejected_token=tokens['access_token']
                            )
                            continue
                        if response.status_code != 200:
                            raise await self._response_error(response)
                        async for event in sse_events(response):
                            yield event, tokens
                        return
        except (httpx.HTTPError, TimeoutError):
            raise ValueError('ChatGPT Codex network error or timeout. Please retry.') from None

    async def _chunks(self, query, model, messages, funcs, extra_args, remove_think, usage_out):
        text = ''
        seen_calls = set()
        output_items = {}
        response_id = None
        async for event, tokens in self._events(query, model, messages, funcs, extra_args):
            kind = event.get('type')
            response = event.get('response') or {}
            response_id = response.get('id') or response_id
            if kind in ('error', 'response.failed', 'response.incomplete'):
                raise CodexProviderError('ChatGPT Codex response failed or was incomplete. Please retry.')
            if kind == 'response.output_text.delta':
                delta = event.get('delta', '')
                text += delta
                yield pm.MessageChunk(role='assistant', content=delta, resp_message_id=response_id)
            elif kind in ('response.reasoning_summary_text.delta', 'response.reasoning_text.delta'):
                if not remove_think:
                    yield pm.MessageChunk(
                        role='assistant',
                        content='',
                        provider_specific_fields={'reasoning_content': event.get('delta', '')},
                    )
            elif kind == 'response.output_item.done':
                item = event.get('item') or {}
                output_items[event.get('output_index', len(output_items))] = item
                if item.get('type') == 'function_call' and item.get('call_id') not in seen_calls:
                    seen_calls.add(item.get('call_id'))
                    yield pm.MessageChunk(role='assistant', content='', tool_calls=[_tool(item)])
            elif kind in ('response.completed', 'response.done'):
                if response.get('status') not in (None, 'completed'):
                    raise CodexProviderError('ChatGPT Codex response was not completed')
                output = response.get('output') or [output_items[k] for k in sorted(output_items)]
                for item in output:
                    if item.get('type') == 'function_call' and item.get('call_id') not in seen_calls:
                        seen_calls.add(item.get('call_id'))
                        yield pm.MessageChunk(role='assistant', content='', tool_calls=[_tool(item)])
                # Some servers send only the terminal output, without text deltas.
                final_text = ''.join(
                    p.get('text', '')
                    for item in output
                    if item.get('type') == 'message'
                    for p in item.get('content', [])
                    if p.get('type') == 'output_text'
                )
                if not text and final_text:
                    text = final_text
                    yield pm.MessageChunk(role='assistant', content=text, resp_message_id=response_id)
                usage_out.update(_usage(response))
                if query is not None:
                    if query.variables is None:
                        query.variables = {}
                    query.variables[requester.STREAM_USAGE_QUERY_VARIABLE] = dict(usage_out)
                fields = None
                if query is not None and output:
                    handle = secrets.token_urlsafe(24)
                    self._replay[handle] = (self._scope(query, model, tokens), time.time() + 3600, output)
                    while len(self._replay) > 64:
                        self._replay.popitem(last=False)
                    fields = {'codex_replay_id': handle}
                yield pm.MessageChunk(
                    role='assistant',
                    content='',
                    all_content=text,
                    is_final=True,
                    resp_message_id=response_id,
                    provider_specific_fields=fields,
                )
                return
        raise CodexProviderError('ChatGPT Codex stream ended before completion. Please retry.')

    async def invoke_llm_stream(self, query, model, messages, funcs=None, extra_args=None, remove_think=False):
        async for chunk in self._chunks(query, model, messages, funcs, extra_args, remove_think, {}):
            yield chunk

    async def invoke_llm(self, query, model, messages, funcs=None, extra_args=None, remove_think=False):
        usage = {}
        text = ''
        calls = []
        fields = {}
        response_id = None
        async for chunk in self._chunks(query, model, messages, funcs, extra_args, remove_think, usage):
            text += chunk.content or ''
            calls.extend(chunk.tool_calls or [])
            response_id = chunk.resp_message_id or response_id
            for key, value in (chunk.provider_specific_fields or {}).items():
                fields[key] = fields.get(key, '') + value if key == 'reasoning_content' else value
        return pm.Message(
            role='assistant',
            content=text,
            tool_calls=calls or None,
            resp_message_id=response_id,
            provider_specific_fields=fields or None,
        ), usage

    async def scan_models(self, api_key=None):
        tokens = await self.auth.access(self.workspace, self.provider)
        try:
            async with asyncio.timeout(90), httpx.AsyncClient(timeout=30, follow_redirects=False) as client:
                for attempt in range(2):
                    response = await client.get(
                        BASE_URL + '/models',
                        params={'client_version': langbot.__version__},
                        headers=self._headers(tokens),
                    )
                    if response.status_code == 401 and attempt == 0:
                        tokens = await self.auth.access(
                            self.workspace, self.provider, rejected_token=tokens['access_token']
                        )
                        continue
                    if response.status_code != 200:
                        raise await self._response_error(response)
                    data = response.json()
                    if not isinstance(data, dict) or not isinstance(data.get('models'), list):
                        raise ValueError('ChatGPT returned an invalid model catalog')
                    result = {}
                    for item in data['models']:
                        name = item.get('slug') or item.get('id')
                        if not isinstance(name, str) or not name or item.get('visibility') == 'hide':
                            continue
                        modalities = item.get('input_modalities') or ['text']
                        abilities = ['func_call']
                        if 'image' in modalities:
                            abilities.append('vision')
                        if item.get('supported_reasoning_levels'):
                            abilities.append('reasoning')
                        result[name] = {
                            'id': name,
                            'name': name,
                            'type': 'llm',
                            'abilities': abilities,
                            'display_name': item.get('display_name'),
                            'description': item.get('description'),
                            'context_length': item.get('context_window'),
                            'input_modalities': modalities,
                            'output_modalities': ['text'],
                            'owned_by': 'openai',
                        }
                    return {'models': list(result.values()), 'debug': None}
        except (httpx.HTTPError, TimeoutError):
            raise ValueError('ChatGPT model discovery network error. Please retry.') from None
        except (ValueError, TypeError, KeyError, AttributeError) as exc:
            # Never echo upstream response bodies (which may contain credentials).
            if isinstance(exc, ValueError) and str(exc).startswith(('ChatGPT', 'Codex')):
                raise
            raise ValueError('ChatGPT returned an invalid model catalog') from None
