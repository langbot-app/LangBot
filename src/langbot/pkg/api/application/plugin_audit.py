"""Core-owned plugin audit ancestry and live outbound correlations."""

from __future__ import annotations

import asyncio
import contextlib
import logging
import secrets
import time
from contextvars import ContextVar
from dataclasses import dataclass, field

from langbot_plugin.api.proxies.invocation import current_audit_correlation

from .contracts import ApplicationAPIError, ApplicationAPIException

logger = logging.getLogger(__name__)


@dataclass
class AuditCall:
    chain: tuple[dict, ...]
    request_id: str = field(default_factory=lambda: secrets.token_urlsafe(16))
    active: bool = True
    outcome: str = 'ok'
    status: int = 200

    def observe(self, response):
        if response.code != 0:
            self.outcome, self.status = 'error', 400


_current_call: ContextVar[AuditCall | None] = ContextVar('core_plugin_audit_call', default=None)


def _frame(binding, action):
    return {'installation_uuid': binding.installation_uuid, 'action': action}


def application_audit_chain(installation_uuid, operation_id):
    call = _current_call.get()
    if call is None or not call.active or call.chain[-1]['installation_uuid'] != installation_uuid:
        return None
    return [*call.chain, {'installation_uuid': installation_uuid, 'action': operation_id}]


def _ancestry(ap, binding):
    correlation = current_audit_correlation()
    if correlation is None:
        return ()
    entry = getattr(ap, '_plugin_audit_calls', {}).get(correlation) if isinstance(correlation, str) else None
    if entry is None or entry[0] != binding or not entry[1].active:
        raise ApplicationAPIException(
            ApplicationAPIError(
                'permission_denied',
                'Invalid or expired plugin audit correlation',
                403,
            )
        )
    return entry[1].chain


@contextlib.contextmanager
def outbound_tool_call(ap, binding):
    parent = _current_call.get()
    if parent is not None and not parent.active:
        raise RuntimeError('Plugin audit invocation has ended')
    call = AuditCall((parent.chain if parent else ()) + (_frame(binding, 'tool.invoke'),))
    registry = getattr(ap, '_plugin_audit_calls', None)
    if registry is None:
        registry = ap._plugin_audit_calls = {}
    correlation = secrets.token_urlsafe(32)
    registry[correlation] = (binding, call)
    try:
        yield correlation
    finally:
        call.active = False
        registry.pop(correlation, None)


@contextlib.asynccontextmanager
async def audit_action(ap, binding, action, *, side_effect=False):
    observed_at = time.monotonic()
    call = AuditCall(())
    token = None
    cancelled = False
    try:
        call.chain = _ancestry(ap, binding) + (_frame(binding, action),)
        token = _current_call.set(call)
        yield call
    except (asyncio.CancelledError, GeneratorExit):
        cancelled = True
        call.outcome, call.status = ('unknown' if side_effect else 'error'), 499
        raise
    except ApplicationAPIException as exc:
        call.outcome = 'denied' if exc.error.code in {'permission_denied', 'invalid_authentication'} else 'error'
        call.status = exc.error.status_code
        raise
    except Exception:
        call.outcome, call.status = 'error', 500
        raise
    finally:
        call.active = False
        if token is not None:
            _current_call.reset(token)
        if cancelled:
            # A further cancellation must not interrupt the write halfway and
            # strand its database connection; let the record finish on its own.
            await asyncio.shield(asyncio.ensure_future(_record(ap, binding, action, call, observed_at, side_effect)))
        else:
            await _record(ap, binding, action, call, observed_at, side_effect)


async def _record(ap, binding, action, call, observed_at, side_effect):
    service = getattr(ap, 'workspace_settings_service', None)
    if service is None:
        return
    # Actions cancelled by shutdown finish after persistence closed; writing
    # then would open a connection on the disposed engine that is never closed.
    if getattr(ap, 'stopping', False) is True:
        return
    from ...operation_trace.service import ActionRule, bucket_allows

    try:
        level = await service.get_configured_level(binding.workspace_uuid)
        bucket = 'write' if side_effect else 'read'
        if not bucket_allows(bucket, level):
            return
        await service.record(
            binding.workspace_uuid,
            rule=ActionRule('update' if side_effect else 'view', 'resource', bucket, 'plugin'),
            level=level,
            principal_type='plugin',
            actor_name=binding.installation_uuid,
            auth_type='plugin',
            request_id=call.request_id,
            dedupe_actor=f'plugin:{call.request_id}',
            route=f'execution.{action}',
            resource_id=binding.installation_uuid,
            outcome=call.outcome,
            status_code=call.status,
            detail={
                'operation': f'execution.{action}',
                'installation_uuid': binding.installation_uuid,
                'chain': list(call.chain or (_frame(binding, action),)),
            },
            duration_ms=int((time.monotonic() - observed_at) * 1000),
        )
    except Exception:
        logger.warning('Plugin action audit could not be recorded')
