"""Observe adapter calls without collecting their arguments or response content."""

from __future__ import annotations

import asyncio
import functools
from contextvars import ContextVar

from .execution import record

processing_mode: ContextVar[str] = ContextVar('telemetry_processing_mode', default='none')


def result_outcome(result):
    # Empty returns do not prove a remote operation succeeded.
    if result is None:
        return 'unknown'
    if result is False:
        return 'failed'
    raw = getattr(result, 'raw', result)
    if isinstance(raw, dict):
        if raw.get('ok') is False or raw.get('success') is False or raw.get('status') == 'failed':
            return 'failed'
        for key in ('errcode', 'retcode'):
            if key in raw and raw[key] not in (0, '0', None):
                return 'failed'
        if raw.get('error'):
            return 'failed'
        if isinstance(raw.get('results'), list):
            outcomes = [result_outcome(item) for item in raw['results']]
            if 'failed' in outcomes:
                return 'failed'
            if not outcomes or 'unknown' in outcomes:
                return 'unknown'
            return 'success'
    # Arbitrary error envelopes or empty mappings are not affirmative evidence.
    if isinstance(raw, dict):
        if raw.get('ok') is True or raw.get('success') is True or raw.get('status') == 'ok':
            return 'success'
        if any(raw.get(key) not in (None, '') for key in ('message_id', 'id')):
            return 'success'
        if any(key in raw and raw[key] in (0, '0') for key in ('errcode', 'retcode')):
            return 'success'
        return 'unknown'
    return 'success' if result is True or getattr(result, 'message_id', None) is not None else 'unknown'


def observe_adapter(ap, context, adapter):
    """Install once on a concrete bot; identity never comes from task-local tenants."""
    if getattr(adapter, '_execution_observed', False):
        return
    try:
        declared = frozenset(adapter.get_supported_apis())
    except Exception:
        return
    for name in declared:
        if '.' in name:
            continue
        original = getattr(adapter, name, None)
        if not asyncio.iscoroutinefunction(original):
            continue

        def make_wrapper(method, operation):
            @functools.wraps(method)
            async def wrapped(*args, **kwargs):
                observed_operation = operation
                if operation == 'call_platform_api':
                    action = args[0] if args else kwargs.get('action')
                    if action in declared:
                        observed_operation = action
                outcome = 'unknown'
                try:
                    result = await method(*args, **kwargs)
                    outcome = result_outcome(result)
                    return result
                except asyncio.CancelledError:
                    outcome = 'cancelled'
                    raise
                except TimeoutError:
                    outcome = 'timeout'
                    raise
                except Exception:
                    outcome = 'failed'
                    raise
                finally:
                    record(
                        ap,
                        context,
                        family='platform_api',
                        operation=observed_operation,
                        adapter=adapter.__class__.__name__,
                        mode=processing_mode.get(),
                        outcome=outcome,
                    )

            return wrapped

        setattr(adapter, name, make_wrapper(original, name))
    setattr(adapter, '_execution_observed', True)
