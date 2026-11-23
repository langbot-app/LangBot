"""Host-owned LLM deadlines, retries and additive diagnostics.

No SDK wire shape changes: request_policy is a reserved model/call extra argument.
Context-local state lets adapters report raw events without sharing mutable state.
"""

from __future__ import annotations

import asyncio
from contextvars import ContextVar
from dataclasses import dataclass, fields
from email.utils import parsedate_to_datetime
import hashlib
import json
import math
import random
import time

from .errors import RequesterError
from .codex_errors import CodexProviderError

STRUCTURED_ERRORS = (RequesterError, CodexProviderError)


@dataclass
class RequestPolicy:
    retries: int = 0
    total_timeout: float = 300
    first_event_timeout: float = 120
    stream_idle_timeout: float = 120
    connect_timeout: float = 10
    read_timeout: float = 120
    write_timeout: float = 30
    pool_timeout: float = 10
    backoff_base: float = 0.5
    backoff_max: float = 8
    attribution: bool = True
    conversation_header: str | None = None

    @classmethod
    def resolve(cls, *layers):
        values = {}
        names = {field.name for field in fields(cls)}
        for layer in layers:
            if not isinstance(layer, dict):
                continue
            # Preserve the legacy per-model/call retry knob, including zero.
            if 'max_retries' in layer:
                values['retries'] = layer['max_retries']
            if 'num_retries' in layer:
                values['retries'] = layer['num_retries']
            if isinstance(layer.get('timeout'), (int, float)):
                values['read_timeout'] = layer['timeout']
                values['first_event_timeout'] = layer['timeout']
                values['stream_idle_timeout'] = layer['timeout']
            policy = layer.get('request_policy', {})
            if not isinstance(policy, dict) or set(policy) - names:
                raise RequesterError('Invalid request_policy fields', code='invalid_policy')
            values.update(policy)
        policy = cls(**values)
        for field in fields(cls):
            value = getattr(policy, field.name)
            if field.name == 'conversation_header':
                if value not in (None, 'x-session-id', 'x-litellm-session-id', 'x-langbot-conversation-id'):
                    raise RequesterError('Unsupported conversation header', code='invalid_policy')
            elif field.name == 'attribution':
                if not isinstance(value, bool):
                    raise RequesterError('attribution must be boolean', code='invalid_policy')
            elif field.name == 'retries':
                if type(value) is not int or not 0 <= value <= 5:
                    raise RequesterError('retries must be an integer from 0 to 5', code='invalid_policy')
            elif (
                isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value <= 0
            ):
                raise RequesterError(f'{field.name} must be finite and positive', code='invalid_policy')
        return policy


class CallState:
    def __init__(self, policy, conversation_id=None):
        self.policy = policy
        self.conversation_id = conversation_id
        self.start = time.perf_counter()
        self.attempt_start = self.start
        self.metrics = {'attempts': 0, 'retry_wait_ms': 0}
        self.raw_started = False
        self.error = None
        self.usage = None
        self.prepared = {}

    def mark(self, name):
        self.metrics.setdefault(name, round((time.perf_counter() - self.start) * 1000, 3))

    async def wait(self, operation, phase, limit):
        remaining = self.policy.total_timeout - (time.perf_counter() - self.start)
        if phase == 'first_event':
            limit = min(limit, self.policy.first_event_timeout - (time.perf_counter() - self.attempt_start))
        token = current_call.set(self)
        try:
            # timeout(0) only cancels at a scheduling point. Buffered SDK
            # responses can complete synchronously, so enforce expired budgets
            # before starting another operation as well.
            if min(limit, remaining) <= 0:
                raise TimeoutError
            async with asyncio.timeout(max(0, min(limit, remaining))):
                return await operation()
        except TimeoutError as exc:
            raise RequesterError(
                'LLM request timed out', code='timeout', retryable=True, phase='total' if remaining <= limit else phase
            ) from exc
        finally:
            current_call.reset(token)

    async def retry(self, error):
        self.error = error.as_dict() if isinstance(error, STRUCTURED_ERRORS) else {'code': 'provider_error'}
        self.metrics.setdefault('attempt_errors', []).append(dict(self.error))
        if not isinstance(error, STRUCTURED_ERRORS) or not error.retryable or self.raw_started:
            return False
        if self.metrics['attempts'] > self.policy.retries:
            return False
        delay = random.uniform(
            0, min(self.policy.backoff_max, self.policy.backoff_base * 2 ** (self.metrics['attempts'] - 1))
        )
        delay = max(delay, error.retry_after or 0)
        remaining = self.policy.total_timeout - (time.perf_counter() - self.start)
        if delay >= remaining:
            return False
        started = time.perf_counter()
        await asyncio.sleep(delay)
        self.metrics['retry_wait_ms'] += round((time.perf_counter() - started) * 1000, 3)
        return True


current_call: ContextVar[CallState | None] = ContextVar('llm_call', default=None)


def opaque_conversation_id(query, context):
    if query is None:
        return None
    session = getattr(query, 'session', None)
    session_id = getattr(session, 'session_id', None)
    if not isinstance(session_id, (str, int)):
        launcher = getattr(query, 'launcher_id', None)
        if not isinstance(launcher, (str, int)):
            return None
        launcher_type = getattr(query, 'launcher_type', '')
        session_id = [str(getattr(launcher_type, 'value', launcher_type)), str(launcher)]
    scope = [context.workspace_uuid, query.bot_uuid, query.pipeline_uuid, session_id]
    return 'lb-' + hashlib.sha256(json.dumps(scope, ensure_ascii=True).encode()).hexdigest()


def error_metadata(exc):
    status = getattr(exc, 'status_code', None)
    status = status if isinstance(status, int) else None
    response = getattr(exc, 'response', None)
    headers = getattr(response, 'headers', {})
    headers = headers if hasattr(headers, 'get') else {}
    retry_after = None
    raw = headers.get('retry-after')
    if raw:
        try:
            retry_after = float(raw)
        except (ValueError, TypeError):
            try:
                retry_after = parsedate_to_datetime(raw).timestamp() - time.time()
            except (ValueError, TypeError, OverflowError):
                pass
    if retry_after is not None:
        retry_after = max(0, retry_after) if math.isfinite(retry_after) else None
    request_id = headers.get('x-request-id') or headers.get('request-id')
    if not isinstance(request_id, str):
        request_id = None
    return {'status_code': status, 'retry_after': retry_after, 'request_id': request_id[:256] if request_id else None}
