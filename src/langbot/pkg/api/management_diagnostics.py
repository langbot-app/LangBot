"""Content-free management boundaries. Diagnostics never participate in I/O.

Only source-code identities and status categories enter these helpers. Never
pass a URL, request, frame, token, tool argument, or serialized result to them.
"""

from __future__ import annotations

import contextlib
import contextvars
import functools
import re

import quart
from quart.wrappers.response import IterableBody, ResponseBody

from ..telemetry import diagnostics as d
from ..telemetry import diagnostic_privacy as privacy

_ACTIVE_BOUNDARY = contextvars.ContextVar('management_diagnostic_boundary', default=None)


def operation_id(source, fn, *, rule='', methods=()):
    """Called at registration with a Core function, never a client tool name."""
    module = fn.__module__.split('.groups.', 1)[-1]
    if source != 'http':
        module = ''
    name = fn.__name__
    if source == 'http' and name == '_':
        # Many Core routes use the anonymous function name `_`. Disambiguate
        # using ONLY the source-declared template and methods at registration.
        # This is never quart.request.path, url_rule, endpoint or request.method.
        template = re.sub(r'[^A-Za-z0-9_.:-]+', '.', rule).strip('.') or 'root'
        name = '.'.join((*sorted(methods or ('GET',)), template))
    return '.'.join(part for part in (source, module, name) if part)[:128]


def outcome(value, reason_code='response_error'):
    try:
        d.set_outcome(value, reason_code=reason_code)
    except Exception:
        pass


def workspace(context):
    """Annotate only this boundary's owned span with a matching trusted context."""
    try:
        from .http.context import ExecutionContext, RequestContext

        if not isinstance(context, (ExecutionContext, RequestContext)):
            return
        boundary = _ACTIVE_BOUNDARY.get()
        span = d.current_span()
        if boundary is None or span is None or span is not boundary.span:
            return
        if d._manager(boundary.ap) is not span.manager:
            return
        instance = getattr(
            getattr(boundary.ap, 'workspace_service', None),
            'instance_uuid',
            getattr(span.manager, 'instance_id', None),
        )
        # Structural recorders need not expose instance metadata. Real managers
        # do, and must never receive another instance's Workspace annotation.
        if instance is not None and instance != context.instance_uuid:
            return
        d.annotate(workspace_uuid=context.workspace_uuid)
    except Exception:
        pass


class Boundary:
    def __init__(self, ap, operation, source):
        self.ap = ap
        self.span = None
        try:
            manager = d._manager(ap)
            if manager is not None:
                fields = {'source': source, 'stage': 'execute'}
                if source == 'webui_debug':
                    fields['attributes'] = {'synthetic': True}
                self.span = d.Span(manager, 'api', operation, fields)
        except Exception:
            pass

    @contextlib.contextmanager
    def activate(self):
        # None is an explicit inheritance barrier, not a no-op: disabled or
        # broken B work must not borrow enabled A's span through ContextVars.
        token = d._CURRENT.set(self.span)
        boundary_token = _ACTIVE_BOUNDARY.set(self)
        try:
            yield
        finally:
            _ACTIVE_BOUNDARY.reset(boundary_token)
            d._CURRENT.reset(token)

    def finish(self, error=None):
        if self.span is not None:
            try:
                self.span.finish(error)
            except Exception:
                pass


class _ObservedBody(ResponseBody):
    """Carry the HTTP parent through iteration, not generator suspension."""

    def __init__(self, body, boundary):
        self.body = body
        self.boundary = boundary
        self.iterator = None
        self.exhausted = False

    async def __aenter__(self):
        try:
            with self.boundary.activate():
                entered = await self.body.__aenter__()
                self.iterator = entered.__aiter__()
            return self
        except BaseException as exc:
            self.boundary.finish(exc)
            raise

    async def __aexit__(self, exc_type, exc_value, tb):
        try:
            with self.boundary.activate():
                result = await self.body.__aexit__(exc_type, exc_value, tb)
        except BaseException as exc:
            self.boundary.finish(exc)
            raise
        finally:
            self.boundary.finish(exc_value if exc_value is not None else (None if self.exhausted else GeneratorExit()))
        return result

    async def __aiter__(self):
        try:
            if self.iterator is None:
                with self.boundary.activate():
                    self.iterator = self.body.__aiter__()
            while True:
                try:
                    with self.boundary.activate():
                        value = await anext(self.iterator)
                except StopAsyncIteration:
                    self.exhausted = True
                    self.boundary.finish()
                    return
                yield value
        except BaseException as exc:
            self.boundary.finish(exc)
            raise


def _response_status(value):
    """Inspect response metadata only; never read or deserialize a body."""
    response = value[0] if isinstance(value, tuple) else value
    status = response.status_code if isinstance(response, quart.Response) else 200
    if isinstance(value, tuple) and len(value) > 1 and type(value[1]) is int:
        status = value[1]
    if status in (401, 403):
        outcome('rejected')
    elif status >= 400:
        outcome('failed')
    elif isinstance(response, dict) and 'code' in response and response['code'] != 0:
        outcome('failed')
    return response


@contextlib.contextmanager
def scope(ap, operation, *, source):
    """A fixed operation around an existing non-generator statement block."""
    try:
        privacy.code_value('operation', operation)
    except Exception:
        pass
    boundary = Boundary(ap, operation, source)
    try:
        with boundary.activate():
            yield
    except BaseException as exc:
        boundary.finish(exc)
        raise
    finally:
        boundary.finish()


def observe(operation, *, source, ap=None, http=False):
    # The operation is supplied by Core registration code, not request data.
    try:
        privacy.code_value('operation', operation)
    except Exception:
        pass

    def decorator(fn):
        @functools.wraps(fn)
        async def wrapped(*args, **kwargs):
            try:
                owner = (ap() if callable(ap) else ap) if ap is not None else getattr(args[0], 'ap', None)
            except Exception:
                owner = None
            boundary = Boundary(owner, operation, source)
            streaming = False
            try:
                with boundary.activate():
                    value = await fn(*args, **kwargs)
                    if http:
                        try:
                            response = _response_status(value)
                            if isinstance(response, quart.Response) and isinstance(response.response, IterableBody):
                                response.response = _ObservedBody(response.response, boundary)
                                streaming = True
                        except Exception:
                            pass
                return value
            except BaseException as exc:
                boundary.finish(exc)
                raise
            finally:
                if not streaming:
                    boundary.finish()

        return wrapped

    return decorator
