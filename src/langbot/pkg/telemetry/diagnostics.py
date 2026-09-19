"""Explicit diagnostic boundaries, preserving coroutine and generator semantics."""

from __future__ import annotations

import asyncio
import contextlib
import contextvars
import functools
import inspect
import time
from uuid import uuid4

from .diagnostic_transport import DiagnosticsManager  # noqa: F401
from . import diagnostic_privacy as privacy

_CURRENT = contextvars.ContextVar('beta_diagnostic_span', default=None)


def current_span():
    return _CURRENT.get()


def set_outcome(outcome, *, reason_code=''):
    span = current_span()
    if span is not None:
        span.outcome = outcome if outcome in privacy.OUTCOMES else 'unknown'
        span.fields['reason_code'] = privacy.category('reason_code', reason_code)


def annotate(**fields):
    """Trusted hook metadata is still projected at the transport boundary."""
    span = current_span()
    if span is not None:
        span.fields.update(fields)


def adapter_event_received(owner, event):
    """Record one converted event before dispatch, including native callback paths."""
    with contextlib.suppress(Exception):
        manager = _manager(owner)
        if manager is None:
            return
        from langbot_plugin.api.entities.builtin.platform.events import EBAEvent
        from .adapter_diagnostics import message_scenario

        if not isinstance(event, EBAEvent) or not _context_matches(manager, owner, _owner_context(owner)):
            return
        fields = _context_fields(owner, {'event': event})
        fields['attributes'] = {
            **fields.get('attributes', {}),
            'adapter_evidence': True,
            **message_scenario({'event': event}),
        }
        parent = current_span()
        if (
            parent
            and parent.manager is manager
            and not (
                fields.get('workspace_uuid')
                and parent.fields.get('workspace_uuid')
                and fields['workspace_uuid'] != parent.fields['workspace_uuid']
            )
        ):
            fields['trace_id'] = parent.fields['trace_id']
            fields['parent_span_id'] = parent.fields['span_id']
            if parent.fields.get('source') in ('webui_debug', 'synthetic'):
                fields['source'] = parent.fields['source']
                fields['attributes']['synthetic'] = True
        fields.setdefault('source', 'platform')
        privacy.code_value('operation', 'platform.adapter_event')
        manager.emit('event', 'platform.adapter_event', 'succeeded', stage='accepted', **fields)


def _owner_app(owner):
    """An explicit owner (even absent/disabled) is an inheritance barrier."""
    if owner is None:
        return None, False
    if hasattr(owner, 'ap'):
        return owner.ap, True
    if hasattr(owner, 'diagnostics') or hasattr(owner, 'instance_config'):
        return owner, True
    for name in ('requester', 'logger', 'adapter'):
        nested = getattr(owner, name, None)
        if nested is not None and nested is not owner:
            app, explicit = _owner_app(nested)
            if explicit:
                return app, True
    return None, False


def _manager(owner):
    app, _ = _owner_app(owner)
    manager = getattr(app, 'diagnostics', None)
    if manager is None or not callable(getattr(manager, 'emit', None)) or not getattr(manager, 'enabled', False):
        return None
    # Honor the shared Span/management producer interface without inheriting a
    # different producer just because this application's producer is absent.
    config = getattr(getattr(app, 'instance_config', None), 'data', {}).get('space', {})
    if config.get('disable_telemetry', False) or config.get('disable_beta_diagnostics', False):
        return None
    # Direct manager holders (e.g. ReplyStreamSession) are intentional. An app
    # must never borrow another app's manager, policy, or credential resolver.
    if hasattr(app, 'instance_config') and getattr(manager, 'ap', app) is not app:
        return None
    return manager


def _owner_context(owner):
    context = getattr(owner, 'execution_context', None)
    if context is not None:
        return context
    for name in ('requester', 'logger', 'adapter'):
        nested = getattr(owner, name, None)
        if nested is not None and nested is not owner:
            context = _owner_context(nested)
            if context is not None:
                return context
    return None


def _execution_context(owner, bound):
    context = bound.get('execution_context') or _owner_context(owner)
    adapter_context = bound.get('adapter_context')
    if isinstance(adapter_context, dict):
        context = adapter_context.get('_execution_context') or context
    query = bound.get('query')
    if query is not None:
        context = getattr(query, '_execution_context', None) or context
    return context


def _context_matches(manager, owner, context):
    from ..api.http.context import ExecutionContext

    if not isinstance(context, ExecutionContext):
        return True
    instance = getattr(getattr(manager.ap, 'workspace_service', None), 'instance_uuid', manager.instance_id)
    if instance != context.instance_uuid:
        return False
    owned = _owner_context(owner)
    return not isinstance(owned, ExecutionContext) or (
        owned.instance_uuid,
        owned.workspace_uuid,
        owned.placement_generation,
    ) == (context.instance_uuid, context.workspace_uuid, context.placement_generation)


def _context_fields(owner, bound):
    context = _execution_context(owner, bound)
    query = bound.get('query')
    from .diagnostic_catalog import adapter_fields

    adapter = getattr(owner, 'adapter', None) or owner
    fields = adapter_fields(adapter)
    # ExecutionContext is constructed/validated by the existing auth boundary;
    # do not infer Workspace identity from arbitrary payload dicts or event IDs.
    if context is not None:
        from ..api.http.context import ExecutionContext

        if isinstance(context, ExecutionContext):
            fields['workspace_uuid'] = context.workspace_uuid
            saved = getattr(query, '_diagnostic_context', None) if query is not None else None
            if isinstance(saved, dict) and saved.get('workspace_uuid') == context.workspace_uuid:
                fields.update(saved)
    binding = bound.get('binding')
    if binding is not None:
        fields['processor_type'] = getattr(binding, 'processor_type', '')
    event = bound.get('event')
    if event is not None:
        fields['platform_event_type'] = getattr(event, 'event_type', None) or getattr(event, 'type', '')
        delivery = getattr(event, 'delivery', None)
        if getattr(delivery, 'surface', None) == 'webui':
            fields['source'] = 'webui_debug'
            fields['attributes'] = {'synthetic': True}
    if getattr(owner, 'mock', False) is True:
        fields['source'] = 'webui_debug'
        fields['attributes'] = {'synthetic': True}
    return fields


class Span:
    def __init__(self, manager, kind, operation, fields):
        parent = current_span()
        self.manager = manager
        self.kind = kind
        self.operation = operation
        self.fields = dict(fields)
        self.adapter_api_active = bool(self.fields.pop('_adapter_api_active', False))
        self.adapter_void_ack = bool(self.fields.pop('_adapter_void_ack', False))
        self.adapter_read_ack = bool(self.fields.pop('_adapter_read_ack', False))
        self.adapter_api_result = None
        if (
            parent
            and parent.fields.get('workspace_uuid')
            and self.fields.get('workspace_uuid')
            and parent.fields['workspace_uuid'] != self.fields['workspace_uuid']
        ):
            parent = None
        if self.fields.get('operation'):
            self.operation = privacy.category('operation', self.fields.pop('operation')) or operation
        self.outcome = None
        self.finished = False
        self.started = time.monotonic()
        self.fields['trace_id'] = (
            parent.fields['trace_id']
            if parent and parent.manager is manager
            else (privacy.opaque(self.fields.get('trace_id')) or str(uuid4()))
        )
        self.fields['span_id'] = str(uuid4())
        if parent and parent.manager is manager:
            self.adapter_api_active = self.adapter_api_active or parent.adapter_api_active
            self.fields['parent_span_id'] = parent.fields['span_id']
            for key in ('workspace_uuid', 'adapter', 'processor_type', 'platform_event_type', 'run_id'):
                if not self.fields.get(key) and parent.fields.get(key):
                    self.fields[key] = parent.fields[key]
            if parent.fields.get('source') in ('webui_debug', 'synthetic'):
                self.fields['source'] = parent.fields['source']
                self.fields['attributes'] = {**self.fields.get('attributes', {}), 'synthetic': True}
        self.emit('started')

    def emit(self, outcome, **extra):
        if self.manager is not None:
            self.manager.emit(self.kind, self.operation, outcome, **{**self.fields, **extra})

    @contextlib.contextmanager
    def activate(self):
        token = _CURRENT.set(self)
        try:
            yield self
        finally:
            _CURRENT.reset(token)

    def finish(self, error=None):
        if self.finished:
            return
        self.finished = True
        error = error if error is not None else self.fields.pop('error', None)
        if isinstance(error, (asyncio.CancelledError, GeneratorExit)):
            outcome = 'cancelled'
        elif isinstance(error, TimeoutError):
            outcome = 'timeout'
        elif error is not None:
            outcome = self.outcome if self.outcome in ('timeout', 'partial', 'rejected') else 'failed'
        else:
            outcome = self.outcome or 'succeeded'
        self.emit(outcome, error=error, duration_ms=(time.monotonic() - self.started) * 1000)


def result_outcome(value):
    """Inspect only the SDK response's status, not arbitrary result contents."""
    from langbot_plugin.api.entities.builtin.platform.events import EBAEvent
    from langbot_plugin.runtime.io.handler import ActionResponse

    span = current_span()
    if span is not None and span.fields.get('stage') == 'convert':
        if isinstance(value, EBAEvent):
            annotate(platform_event_type=value.type)
            if span.fields.get('attributes', {}).get('adapter_evidence'):
                from .adapter_diagnostics import message_scenario

                annotate(attributes={**span.fields['attributes'], **message_scenario({'event': value})})
                # Successful conversion is counted once at dispatch, which also
                # covers adapters constructing EBA events in native callbacks.
                span.fields['attributes']['adapter_evidence'] = False
        elif value is None:
            set_outcome('skipped', reason_code='not_matched')
        if not isinstance(value, EBAEvent) and span.fields.get('attributes', {}).get('adapter_evidence'):
            span.fields['attributes']['adapter_evidence'] = False
    if span is not None and span.kind == 'api' and span.fields.get('attributes', {}).get('adapter_evidence'):
        from .adapter_diagnostics import response_outcome

        # A normal return is not an acknowledgement. Fail closed for acceptance
        # (but never for the business call) even if result inspection raises.
        if span.outcome is None:
            set_outcome('skipped')
            outcome = span.adapter_api_result
            if outcome is None:
                if (value is None and span.adapter_void_ack) or (
                    span.adapter_read_ack and value is not None and value != ''
                ):
                    outcome = 'succeeded'
                else:
                    outcome = response_outcome(value, span.fields.get('adapter'))
            set_outcome(outcome, **({'reason_code': 'response_error'} if outcome == 'failed' else {}))
    if isinstance(value, ActionResponse):
        if value.code != 0:
            set_outcome('failed', reason_code='response_error')


def observe(kind, operation, *, source='internal', stage='execute', ap=None, fields=None):
    """Explicit boundary with a stable/off fast path and transparent generators."""
    privacy.code_value('operation', operation)
    privacy.code_value('stage', stage)

    def decorate(fn):
        signature = inspect.signature(fn)

        def span_for(args, kwargs):
            try:
                bound = signature.bind_partial(*args, **kwargs).arguments
                owner = bound.get(next(iter(signature.parameters), ''))
                manager_owner = (ap() if callable(ap) else ap) if ap is not None else owner
                manager = _manager(manager_owner)
                _, explicit = _owner_app(manager_owner)
                context = _execution_context(owner, bound)
                parent = current_span()
                if manager is None and not explicit and ap is None and parent is not None:
                    # Stateless converters may inherit, but a different explicit
                    # Workspace must not select a parent's credentials/policy.
                    if context is not None and getattr(context, 'workspace_uuid', None) != parent.fields.get(
                        'workspace_uuid'
                    ):
                        return None
                    manager = parent.manager
                if manager is None or not manager.enabled:
                    return None
                if not _context_matches(manager, owner, context):
                    return None
                metadata = {'source': source, 'stage': stage}
                metadata.update(_context_fields(owner, bound))
                from .diagnostic_catalog import catalog

                for directory, entry in catalog().items():
                    if directory in fn.__module__.split('.') and '.platform.' in fn.__module__:
                        metadata['adapter'] = entry['adapter']
                        break
                if fields:
                    extra = fields(bound)
                    extra['attributes'] = {**metadata.get('attributes', {}), **extra.get('attributes', {})}
                    metadata.update(extra)
                from .adapter_diagnostics import boundary_fields

                if parent and (
                    parent.manager is not manager
                    or (
                        metadata.get('workspace_uuid')
                        and parent.fields.get('workspace_uuid')
                        and metadata['workspace_uuid'] != parent.fields['workspace_uuid']
                    )
                ):
                    parent = None
                evidence = (
                    boundary_fields(fn.__module__, kind, operation, bound, parent)
                    if metadata.get('attributes', {}).get('adapter_evidence') is not False
                    else {}
                )
                metadata['attributes'] = {**metadata.get('attributes', {}), **evidence.pop('attributes', {})}
                metadata.update(evidence)
                return Span(manager, kind, operation, metadata)
            except Exception:
                return None

        def inspect_result(value):
            with contextlib.suppress(Exception):
                result_outcome(value)

        def finish(span, error=None):
            if span is not None:
                with contextlib.suppress(Exception):
                    span.finish(error)

        if inspect.isasyncgenfunction(fn):
            from collections.abc import AsyncGenerator

            class ObservedGenerator(AsyncGenerator):
                """Delegate each native protocol operation, without extra close.

                A yield-based proxy cannot distinguish athrow(GeneratorExit)
                (which may yield) from aclose() (which must reject a yield).
                Let the native generator implement that distinction and retain
                its own primary/cleanup exception and cancellation semantics.
                """

                def __init__(self, args, kwargs):
                    self.gen = fn(*args, **kwargs)
                    self.args, self.kwargs = args, kwargs
                    self.span = None
                    self.started = False

                def __getattr__(self, name):
                    return getattr(self.gen, name)

                async def _advance(self, method, *values):
                    if not self.started:
                        self.started = True
                        self.span = span_for(self.args, self.kwargs)
                    token = _CURRENT.set(self.span)
                    try:
                        value = await method(*values)
                        if self.span is not None and method != self.gen.aclose:
                            inspect_result(value)
                        if method == self.gen.aclose:
                            finish(self.span, GeneratorExit())
                        return value
                    except StopAsyncIteration:
                        finish(self.span)
                        raise
                    except BaseException as exc:
                        # Rejected protocol calls (e.g. concurrent asend, a
                        # yielded GeneratorExit) need not terminate the stream.
                        if self.gen.ag_frame is None:
                            finish(self.span, exc)
                        raise
                    finally:
                        _CURRENT.reset(token)

                def __anext__(self):
                    return self._advance(self.gen.__anext__)

                def asend(self, value):
                    return self._advance(self.gen.asend, value)

                def athrow(self, *values):
                    return self._advance(self.gen.athrow, *values)

                def aclose(self):
                    return self._advance(self.gen.aclose)

            @functools.wraps(fn)
            def stream(*args, **kwargs):
                return ObservedGenerator(args, kwargs)

            return stream

        @functools.wraps(fn)
        async def call(*args, **kwargs):
            span = span_for(args, kwargs)
            if span is None:
                token = _CURRENT.set(None)
                try:
                    return await fn(*args, **kwargs)
                finally:
                    _CURRENT.reset(token)
            try:
                with span.activate():
                    value = await fn(*args, **kwargs)
                    inspect_result(value)
                finish(span)
                return value
            except BaseException as exc:
                finish(span, exc)
                raise

        return call

    return decorate


def event(owner, kind, operation, outcome, **fields):
    """Emit a point-in-time fact from an existing state transition."""
    try:
        manager = _manager(owner)
        _, explicit = _owner_app(owner)
        parent = current_span()
        context = _owner_context(owner)
        if manager is None and not explicit and parent:
            if context is not None and getattr(context, 'workspace_uuid', None) != parent.fields.get('workspace_uuid'):
                return
            manager = parent.manager
        if manager is not None and _context_matches(manager, owner, context):
            inherited = dict(parent.fields) if parent and parent.manager is manager else {}
            if context is not None and getattr(context, 'workspace_uuid', None) != inherited.get('workspace_uuid'):
                inherited = _context_fields(owner, {})
            inherited.update(fields)
            manager.emit(kind, operation, outcome, **inherited)
    except Exception:
        pass


def capture_context():
    span = current_span()
    if span is None or not span.manager.enabled:
        return None
    result = {
        k: span.fields[k]
        for k in ('trace_id', 'workspace_uuid', 'run_id', 'adapter', 'processor_type', 'platform_event_type', 'source')
        if k in span.fields
    }
    result['parent_span_id'] = span.fields['span_id']
    return result


def link_context(saved):
    """Link only after the existing Host run/installation validator accepted it."""
    span = current_span()
    if span is None or not isinstance(saved, dict):
        return
    if span.fields.get('workspace_uuid') and span.fields['workspace_uuid'] != saved.get('workspace_uuid'):
        return
    for key in ('trace_id', 'parent_span_id', 'workspace_uuid', 'run_id'):
        if privacy.opaque(saved.get(key)):
            span.fields[key] = saved[key]
    for key in ('adapter', 'platform_event_type'):
        if privacy.category(key, saved.get(key)):
            span.fields[key] = saved[key]
    if saved.get('processor_type') in privacy.PROCESSORS:
        span.fields['processor_type'] = saved['processor_type']
    if saved.get('source') in ('webui_debug', 'synthetic'):
        span.fields['source'] = saved['source']
        span.fields['attributes'] = {**span.fields.get('attributes', {}), 'synthetic': True}


def declare_runner(descriptor):
    """Allow only identifiers from a validated installed public Runner manifest."""
    import re

    pairs = {'plugin_id': descriptor.get_plugin_id(), 'runner_id': descriptor.id}
    for field, value in pairs.items():
        allowed = privacy.VOCABULARY.setdefault(field, set())
        if (
            isinstance(value, str)
            and len(value) <= 128
            and len(allowed) < 1024
            and re.fullmatch(r'(?:plugin:)?[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+(?:/[A-Za-z0-9_.-]+)?', value)
        ):
            allowed.add(value)


def runner_metadata(owner, descriptor, processor_type):
    manager = _manager(owner)
    if manager is None or not manager.enabled:
        return
    metadata = {
        'plugin_id': descriptor.get_plugin_id(),
        'runner_id': descriptor.id,
        'plugin_version': getattr(descriptor, 'plugin_version', ''),
        'runner_usage': 'event' if processor_type == 'event_processor' else 'agent',
    }
    annotate(attributes=metadata)
    event(
        owner,
        'capability',
        'runner.run',
        'succeeded',
        source='runtime',
        stage='snapshot',
        processor_type=processor_type,
        attributes={
            **metadata,
            'capability_type': 'processor',
            'capability_name': processor_type,
            'supported': True,
            'configured': True,
            'available': True,
        },
    )
