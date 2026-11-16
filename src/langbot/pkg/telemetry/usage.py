"""Bounded, process-local usage deltas carried by instance heartbeats."""

from __future__ import annotations

import functools
import contextvars
import re
import time
import uuid
from dataclasses import dataclass, field


MAX_KEYS = 256
MAX_WORKSPACES = 10000
MAX_COUNT = 1000000
VERSION = re.compile(r'[0-9A-Za-z.+_-]{1,32}')
COMMAND = re.compile(r'[a-z0-9-]+(?:\.[a-z0-9-]+){0,5}')
ERROR = re.compile(r'[A-Za-z0-9_.]{0,64}')
GROUPS: set[str] = set()
SCHEMA = {
    'alert.state': ('enabled', 'channel'),
    'alert.settings.update': ('enabled', 'channel'),
    'alert.incident': ('rule', 'event'),
    'alert.delivery': ('notice', 'via', 'outcome'),
    'api.call': ('group', 'method', 'client', 'status'),
    'lbctl.cmd': ('cmd', 'status'),
    'lbctl.client': ('version', 'os'),
    'kb.create': ('engine',),
    'kb.update': ('engine',),
    'kb.delete': ('engine',),
    'kb.file.upload': ('engine', 'ext', 'size'),
    'kb.file.ingest': ('engine', 'parser', 'outcome', 'err', 'dur'),
    'kb.file.delete': ('engine',),
    'kb.retrieve': ('engine', 'origin', 'outcome', 'hit', 'dur'),
    'kb.migration.run': ('outcome',),
    'ugc.share.preview': ('type',),
    'ugc.share.submit': ('type', 'mode', 'outcome', 'err'),
    'ugc.library.browse': ('kind',),
    'ugc.prompt.apply': ('kind',),
    'ugc.install': ('type', 'source', 'outcome', 'unfilled'),
}
ALERT_ENUMS = {
    'enabled': ('yes', 'no'),
    'channel': ('auto', 'instance', 'space', 'off'),
    'rule': ('pipeline_failures', 'model_failures', 'bot_offline', 'other'),
    'event': ('opened', 'resolved'),
    'notice': ('fired', 'reminder', 'resolved', 'test'),
    'via': ('email', 'space', 'webhook'),
    'outcome': ('ok', 'failed', 'rate_limited'),
}
ENUMS = {
    'method': ('GET', 'POST', 'PUT', 'PATCH', 'DELETE'),
    'client': ('webui', 'lbctl', 'mcp', 'api_other'),
    'status': ('2xx', '3xx', '4xx', '5xx'),
    'os': ('linux', 'darwin', 'windows', 'other'),
    'ext': ('pdf', 'docx', 'doc', 'md', 'txt', 'html', 'xlsx', 'csv', 'pptx', 'json', 'zip', 'other'),
    'size': ('<1M', '<10M', '<50M', '>=50M'),
    'parser': ('builtin', 'plugin'),
    'outcome': ('ok', 'failed', 'cancelled'),
    'origin': ('pipeline', 'agent', 'plugin', 'webui_test', 'api'),
    'hit': ('empty', 'nonempty'),
    'type': ('prompt', 'skill', 'mcp', 'plugin'),
    'mode': ('new', 'update'),
    'kind': ('messaging', 'agent', 'other'),
    'source': ('market', 'community', 'local', 'github', 'other'),
    'unfilled': ('yes', 'no'),
}
MCP_DOMAINS = (
    'plugin',
    'workspace',
    'sandbox',
    'system',
    'knowledge',
    'pipeline',
    'monitoring',
    'session',
    'slack',
    'bot',
    'processor',
    'agent',
    'model',
    'mcp',
    'skill',
)
MCP_GROUPS = frozenset(f'mcp:{domain}' for domain in MCP_DOMAINS)


@dataclass
class Counters:
    since: int = field(default_factory=lambda: int(time.time()))
    counts: dict = field(default_factory=dict)
    pending: dict | None = None


_workspaces: dict[str, Counters] = {}
origin = contextvars.ContextVar('usage_retrieval_origin', default=None)
install_source = contextvars.ContextVar('usage_install_source', default=None)


def enabled(ap) -> bool:
    try:
        return not ap.instance_config.data.get('space', {}).get('disable_telemetry', False)
    except Exception:
        return False


def normalize(metric: str, dims: dict) -> tuple:
    values = []
    for name in SCHEMA[metric]:
        value = dims.get(name, '')
        value = value if isinstance(value, str) else ''
        if metric.startswith('alert.'):
            allowed = ALERT_ENUMS[name]
            if value not in allowed:
                if 'other' not in allowed:
                    raise ValueError('Invalid alert dimension')
                value = 'other'
        elif name == 'engine':
            value = value[:64]
        elif name == 'group':
            value = value if len(value) <= 64 and (value in GROUPS or value in MCP_GROUPS) else 'other'
        elif name == 'cmd':
            value = value if len(value) <= 64 and COMMAND.fullmatch(value) else 'other'
        elif name == 'version':
            value = value if VERSION.fullmatch(value) else 'other'
        elif name == 'err':
            value = '' if dims.get('outcome') == 'ok' else value if ERROR.fullmatch(value) else 'other'
        elif name == 'dur':
            allowed = (
                ('<10s', '<60s', '<5m', '>=5m') if metric == 'kb.file.ingest' else ('<500ms', '<2s', '<10s', '>=10s')
            )
            value = value if value in allowed else 'other'
        else:
            allowed = ENUMS[name]
            if name == 'outcome' and metric != 'kb.file.ingest':
                allowed = ('ok', 'failed')
            if name == 'type' and metric == 'ugc.install':
                allowed = ('plugin', 'mcp', 'skill')
            value = value if value in allowed else 'other'
        values.append(value)
    return tuple(values)


def inc(ap, workspace_uuid, metric, amount: int = 1, **dims) -> None:
    try:
        if not enabled(ap) or metric not in SCHEMA or not isinstance(workspace_uuid, str) or not workspace_uuid:
            return
        if not isinstance(amount, int) or isinstance(amount, bool) or amount <= 0:
            return
        key = (metric, normalize(metric, dims))
        state = _workspaces.get(workspace_uuid)
        if state is None:
            if len(_workspaces) >= MAX_WORKSPACES:
                return
            state = _workspaces[workspace_uuid] = Counters()
        if key not in state.counts and len(state.counts) >= MAX_KEYS:
            return
        state.counts[key] = state.counts.get(key, 0) + min(amount, MAX_COUNT)
    except Exception:
        pass


def take_batch(ws: str) -> dict | None:
    state = _workspaces.get(ws)
    if state is None or not state.counts:
        return None
    entries = [
        [metric, dict(zip(SCHEMA[metric], dims)), min(count, MAX_COUNT)]
        for (metric, dims), count in state.counts.items()
    ]
    if state.pending is None or state.pending['c'] != entries:
        state.pending = {'v': 1, 'batch_id': str(uuid.uuid4()), 'since': state.since, 'c': entries}
    return state.pending


def ack(ws: str, batch: dict | None) -> None:
    state = _workspaces.get(ws)
    if state is None or batch is None or state.pending is None:
        return
    if state.pending['batch_id'] != batch['batch_id']:
        return
    for metric, dims, count in batch['c']:
        key = (metric, tuple(dims[name] for name in SCHEMA[metric]))
        remaining = state.counts.get(key, 0) - count
        if remaining > 0:
            state.counts[key] = remaining
        else:
            state.counts.pop(key, None)
    state.pending = None
    if not state.counts:
        _workspaces.pop(ws, None)


def nack(ws: str, batch: dict | None) -> None:
    """Leave the unacknowledged counts in place; take_batch merges new increments."""


def bucket(value: float, limits: tuple, labels: tuple) -> str:
    return next((label for limit, label in zip(limits, labels) if value < limit), labels[-1])


def client_dimensions(context, headers, *, api_key_auth=False) -> tuple[str, dict]:
    principal = getattr(getattr(context, 'principal', None), 'principal_type', None)
    api_key = (
        principal == 'api_key'
        if principal is not None
        else bool(
            api_key_auth or headers.get('X-API-Key') or headers.get('Authorization', '').startswith('Bearer lbk_')
        )
    )
    ua = headers.get('User-Agent', '')
    client = 'lbctl' if api_key and ua.startswith('lbctl/') else 'api_other' if api_key else 'webui'
    match = re.fullmatch(r'lbctl/([^ ]+) \(([^/]+)/[^)]+\)', ua)
    return client, {'version': match[1] if match else 'other', 'os': match[2] if match else 'other'}


def record_http(ap, context, headers, group, method, status, *, api_key_auth=False) -> None:
    try:
        ws = getattr(context, 'workspace_uuid', None) or ap.__dict__.get('_telemetry_default_workspace')
        client, details = client_dimensions(context, headers, api_key_auth=api_key_auth)
        status = f'{max(2, min(int(status) // 100, 5))}xx'
        inc(ap, ws, 'api.call', group=group, method=method, client=client, status=status)
        if client == 'lbctl':
            inc(ap, ws, 'lbctl.cmd', cmd=headers.get('X-LangBot-Client-Command', ''), status=status)
            inc(ap, ws, 'lbctl.client', **details)
    except Exception:
        pass


def retrieval_origin(context) -> str:
    if origin.get() is not None:
        return origin.get()
    principal = getattr(context, 'trigger_principal', None)
    if getattr(principal, 'principal_type', None) == 'plugin':
        return 'plugin'
    if getattr(context, 'pipeline_uuid', None):
        return 'pipeline'
    if getattr(principal, 'processor_kind', None) == 'agent':
        return 'agent'
    if getattr(principal, 'principal_type', None) == 'account':
        return 'webui_test'
    return 'api'


def observe_runtime(metric):
    def decorate(fn):
        @functools.wraps(fn)
        async def observed(self, execution_context, *args, **kwargs):
            started = time.monotonic()
            outcome, error, result = 'ok', '', None
            try:
                result = await fn(self, execution_context, *args, **kwargs)
                return result
            except BaseException as exc:
                outcome = (
                    'cancelled' if metric == 'kb.file.ingest' and type(exc).__name__ == 'CancelledError' else 'failed'
                )
                error = type(exc).__name__
                raise
            finally:
                try:
                    dims = {} if metric == 'kb.migration.run' else {'engine': self.get_knowledge_engine_plugin_id()}
                    elapsed = time.monotonic() - started
                    if metric == 'kb.retrieve':
                        dims.update(
                            origin=retrieval_origin(execution_context),
                            outcome=outcome,
                            hit='nonempty' if result else 'empty',
                            dur=bucket(elapsed, (0.5, 2, 10), ('<500ms', '<2s', '<10s', '>=10s')),
                        )
                    elif metric == 'kb.file.ingest':
                        parser = kwargs.get('parser_plugin_id', args[2] if len(args) > 2 else None)
                        dims.update(
                            parser='plugin' if parser else 'builtin',
                            outcome=outcome,
                            err=error,
                            dur=bucket(elapsed, (10, 60, 300), ('<10s', '<60s', '<5m', '>=5m')),
                        )
                    elif metric == 'kb.migration.run':
                        dims['outcome'] = outcome
                    if outcome == 'ok' or metric in ('kb.retrieve', 'kb.file.ingest', 'kb.migration.run'):
                        inc(self.ap, execution_context.workspace_uuid, metric, **dims)
                except Exception:
                    pass

        return observed

    return decorate


def observe_install(content_type, source):
    def decorate(fn):
        @functools.wraps(fn)
        async def observed(self, context, *args, **kwargs):
            outcome = 'failed'
            resolved_source = install_source.get() or source
            unfilled = 'no'
            if content_type == 'mcp':
                data = args[0] if args else kwargs.get('mcp_data', {})
                resolved_source = 'community' if data.get('source') == 'community' else source
                unfilled = 'yes' if data.get('required_inputs') else 'no'
            try:
                result = await fn(self, context, *args, **kwargs)
                outcome = 'ok'
                return result
            finally:
                inc(
                    self.ap,
                    getattr(context, 'workspace_uuid', None),
                    'ugc.install',
                    type=content_type,
                    source=resolved_source,
                    outcome=outcome,
                    unfilled=unfilled,
                )

        return observed

    return decorate


def observe_share(ap, content_type, *, preview=False):
    def decorate(fn):
        @functools.wraps(fn)
        async def observed(*args, **kwargs):
            import quart

            status, error = 500, ''
            try:
                response = await fn(*args, **kwargs)
                status = response[1] if isinstance(response, tuple) else response.status_code
                return response
            except Exception as exc:
                error = type(exc).__name__
                raise
            finally:
                try:
                    context = kwargs.get('request_context')
                    body = await quart.request.get_json(silent=True) or {}
                    body = body if isinstance(body, dict) else {}
                    dims = {'type': content_type}
                    if not preview:
                        dims.update(
                            mode=body.get('mode', 'new'),
                            outcome='ok' if status < 400 else 'failed',
                            err=error or getattr(quart.g, 'usage_error', ''),
                        )
                    inc(ap, context.workspace_uuid, 'ugc.share.preview' if preview else 'ugc.share.submit', **dims)
                except Exception:
                    pass

        return observed

    return decorate
