"""Bounded, content-free execution counters for the existing telemetry sender.

This module reports observations only. Coverage catalogs and acceptance rules
belong to Space. Aggregation keys include both immutable execution identities.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from uuid import uuid4

from .identity import workspace_identity

MAX_KEYS = 512
MAX_BATCH = 32
FLUSH_SECONDS = 60
MODES = frozenset({'pipeline', 'agent', 'event_processor', 'none'})
OUTCOMES = frozenset({'success', 'failed', 'cancelled', 'timeout', 'skipped', 'unknown'})


class ExecutionCounters:
    def __init__(self, manager):
        self.manager = manager
        self.pending: dict[tuple, dict] = {}
        self.task: asyncio.Task | None = None
        self.dropped = 0

    def record(
        self,
        context,
        *,
        family: str,
        operation: str,
        mode: str = 'none',
        adapter: str = '',
        runner: str = '',
        outcome: str = 'unknown',
        synthetic: bool = False,
    ):
        try:
            cfg = self.manager.telemetry_config
            if not cfg or cfg.get('disable_telemetry', False) or not cfg.get('url'):
                return
            if family not in {'platform_event', 'event_route', 'runner', 'platform_api'}:
                return
            if mode not in MODES or outcome not in OUTCOMES:
                return
            # Only code-defined identifiers are accepted; never pass user values.
            if any(not isinstance(v, str) or len(v) > 160 for v in (operation, adapter, runner)):
                return
            identity = workspace_identity(context)
            key = (
                identity['instance_id'],
                identity['workspace_uuid'],
                family,
                operation,
                mode,
                adapter,
                runner,
                outcome,
                bool(synthetic),
            )
            row = self.pending.get(key)
            if row is None:
                if len(self.pending) >= MAX_KEYS:
                    self.dropped += 1
                    return
                row = {'count': 0, 'first_seen': datetime.now(timezone.utc).isoformat()}
                self.pending[key] = row
            row['count'] = min(row['count'] + 1, 2147483647)
            row['last_seen'] = datetime.now(timezone.utc).isoformat()
            if self.task is None or self.task.done():
                self.task = asyncio.create_task(self._loop())
        except Exception:
            # Observability must never change execution behavior.
            return

    async def _loop(self):
        while self.pending:
            await asyncio.sleep(FLUSH_SECONDS)
            await self.flush()

    async def flush(self):
        from ..utils import constants

        # Remove only one bounded batch; subsequent windows drain the remainder.
        # Drain one tenant per minute, at most one request, round-robin by insertion.
        if not self.pending:
            return
        tenant = next(iter(self.pending))[:2]
        keys = [key for key in self.pending if key[:2] == tenant][:MAX_BATCH]
        groups: dict[tuple[str, str], list[dict]] = {}
        for key in keys:
            row = self.pending.pop(key)
            instance, workspace, family, operation, mode, adapter, runner, outcome, synthetic = key
            groups.setdefault((instance, workspace), []).append(
                {
                    **row,
                    'family': family,
                    'operation': operation,
                    'mode': mode,
                    'adapter': adapter,
                    'runner': runner,
                    'outcome': outcome,
                    'synthetic': synthetic,
                }
            )
        for (instance, workspace), observations in groups.items():
            payload = {
                'event_type': 'feature_execution',
                'query_id': str(uuid4()),
                'instance_id': instance,
                'workspace_uuid': workspace,
                'version': constants.semantic_version,
                'edition': constants.edition,
                'timestamp': datetime.now(timezone.utc).isoformat(),
                'features': {'schema': 1, 'observations': observations},
            }
            if not await self.manager.send(payload):
                await asyncio.sleep(1)
                await self.manager.send(payload)

    async def shutdown(self):
        if self.task is not None:
            self.task.cancel()
            await asyncio.gather(self.task, return_exceptions=True)
            self.task = None
        try:
            await asyncio.wait_for(self.flush(), timeout=2)
        except (Exception, asyncio.CancelledError):
            pass
        self.pending.clear()


def record(ap, context, **observation):
    """Best-effort bridge usable with optional telemetry and test doubles."""
    try:
        counters = getattr(getattr(ap, 'telemetry', None), 'execution', None)
        if isinstance(counters, ExecutionCounters):
            counters.record(context, **observation)
    except Exception:
        pass
