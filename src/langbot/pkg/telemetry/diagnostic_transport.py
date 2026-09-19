"""Bounded, memory-only Beta diagnostics transport, isolated from usage telemetry."""

from __future__ import annotations

import asyncio
import contextlib
import importlib.metadata
import json
import os
import random
import re
import time
import platform
import sys
from pathlib import Path
from collections import Counter
from datetime import datetime, timezone
from uuid import uuid4

import httpx
from packaging.version import Version, InvalidVersion

from . import diagnostic_privacy as privacy


class DiagnosticsManager:
    """All producers are synchronous; only this owned worker performs I/O.

    Retention: 2048 events / 15 minutes, 5 attempts, 8 KiB per event. An in-flight
    event stays in the same bounded queue until explicitly ACKed. No disk spool
    means abrupt process loss cannot be counted after restart (documented).
    """

    def __init__(self, ap, *, version=None, instance_id=None, capacity=2048, marker_path=None):
        from ..utils import constants
        from .diagnostic_catalog import catalog

        with contextlib.suppress(Exception):
            catalog()
        self.ap = ap
        self.marker_path = Path(marker_path) if marker_path is not None else None
        self._session_id = str(uuid4())
        self._marker_active = False
        raw_version = version or importlib.metadata.version('langbot')
        try:
            parsed = Version(raw_version)
            self.version = str(parsed)
            self.beta = bool(parsed.pre and parsed.pre[0] == 'b' and not parsed.local)
        except InvalidVersion:
            self.version, self.beta = '', False
        self.instance_id = instance_id or constants.instance_id
        try:
            from langbot._build_info import CORE_REVISION
        except ImportError:
            CORE_REVISION = ''
        candidate = os.getenv('LANGBOT_BUILD_REVISION', CORE_REVISION)
        self.revision = candidate.lower() if re.fullmatch('[a-fA-F0-9]{40}', candidate or '') else ''
        try:
            self.sdk_version = privacy.version_string(importlib.metadata.version('langbot-plugin'))
        except importlib.metadata.PackageNotFoundError:
            self.sdk_version = ''
        self.capacity = max(1, min(capacity, 2048))
        self.pending: list[dict] = []
        self.counters = Counter()
        self._reported = Counter()
        self._last_retry = False
        self.max_attempts = 5
        self.retention_seconds = 900
        self.request_timeout = 10
        self.client: httpx.AsyncClient | None = None
        self._attempts: dict[str, int] = {}
        self._born: dict[str, float] = {}
        self._worker = None
        self._request = None
        self._closing = False
        self._wake = asyncio.Event()
        self._flush_lock = asyncio.Lock()

    async def start_session(self):
        """One bounded, content-free marker per process; never per-event disk I/O."""
        if not self.enabled:
            await self._clear_marker()
            return
        previous = False
        if self.marker_path is not None:

            def mark():
                previous = self.marker_path.exists()
                self.marker_path.parent.mkdir(parents=True, exist_ok=True)
                self.marker_path.write_text(self._session_id)
                return previous

            with contextlib.suppress(Exception):
                previous = await asyncio.to_thread(mark)
                self._marker_active = True
        privacy.code_value('operation', 'startup.session')
        self.emit(
            'lifecycle',
            'startup.session',
            'started',
            source='startup',
            stage='snapshot',
            attributes={
                'previous_session_unclean': previous,
                'os': platform.system().lower(),
                'arch': platform.machine().lower(),
                'python_version': '.'.join(map(str, sys.version_info[:3])),
                'database': self.ap.instance_config.data.get('database', {}).get('use', ''),
                'edition': self.ap.instance_config.data.get('system', {}).get('edition', ''),
            },
        )

    async def _clear_marker(self):
        if self.marker_path is None:
            return

        def remove():
            if self.marker_path.exists():
                with self.marker_path.open() as handle:
                    owner = handle.read(64)
                if owner == self._session_id or not self._marker_active:
                    self.marker_path.unlink(missing_ok=True)

        with contextlib.suppress(Exception):
            await asyncio.to_thread(remove)
        self._marker_active = False

    @property
    def enabled(self):
        config = getattr(getattr(self.ap, 'instance_config', None), 'data', {}).get('space', {})
        return (
            self.beta
            and not self._closing
            and not config.get('disable_telemetry', False)
            and not config.get('disable_beta_diagnostics', False)
            and bool(config.get('url'))
        )

    def clear(self):
        self.pending.clear()
        self._attempts.clear()
        self._born.clear()
        if self._request is not None and not self._request.done():
            self._request.cancel()

    def emit(
        self,
        kind,
        operation,
        outcome,
        *,
        source='internal',
        workspace_uuid='',
        attributes=None,
        stage='execute',
        adapter='',
        processor_type='',
        platform_event_type='',
        reason_code='',
        duration_ms=0,
        error=None,
        trace_id='',
        span_id='',
        parent_span_id='',
        run_id='',
        **ignored,
    ):
        """Project known scalar fields; failures in diagnostics never escape."""
        try:
            if not self.enabled:
                self.clear()
                return
            if kind not in privacy.KINDS or outcome not in privacy.OUTCOMES:
                return
            self.counters['generated'] += 1
            event = {
                'schema_version': 1,
                'event_id': str(uuid4()),
                'kind': kind,
                'instance_id': self.instance_id,
                'workspace_uuid': privacy.opaque(workspace_uuid),
                'core_version': self.version,
                'core_revision': self.revision,
                'sdk_version': self.sdk_version,
                'release_channel': 'beta',
                'source': source if source in privacy.SOURCES else 'internal',
                'operation': privacy.category('operation', operation),
                'stage': privacy.category('stage', stage),
                'outcome': outcome,
                'reason_code': privacy.category('reason_code', reason_code),
                'adapter': privacy.category('adapter', adapter),
                'processor_type': processor_type if processor_type in privacy.PROCESSORS else '',
                'platform_event_type': privacy.category('platform_event_type', platform_event_type),
                'occurred_at': datetime.now(timezone.utc).isoformat(),
                'count': 1,
                'sample_rate': 1,
                'duration_ms': max(0, min(float(duration_ms), 86400000)),
                'attributes': privacy.attributes(attributes),
            }
            for key, value in (
                ('trace_id', trace_id),
                ('span_id', span_id),
                ('parent_span_id', parent_span_id),
                ('run_id', run_id),
            ):
                if privacy.opaque(value):
                    event[key] = privacy.opaque(value)
            if error is not None:
                event.update(privacy.error_fields(error, event['operation'], event['stage']))
            encoded = json.dumps(event, allow_nan=False).encode()
            if (
                not isinstance(self.instance_id, str)
                or not 0 < len(self.instance_id) <= 128
                or len(encoded) > 8192
                or len(self.pending) >= self.capacity
            ):
                self.counters['dropped'] += 1
                return
            self.pending.append(event)
            self._born[event['event_id']] = time.monotonic()
            self.counters['queued'] += 1
            self._wake.set()
        except Exception:
            self.counters['dropped'] += 1

    async def credentials(self, workspace_uuid):
        # Resolve each Workspace independently in the background. No OSS secret.
        token = os.getenv('LANGBOT_TELEMETRY_INGEST_TOKEN', '').strip()
        if token:
            return {'X-LangBot-Telemetry-Token': token}
        if not workspace_uuid:
            return {}
        users = getattr(self.ap, 'user_service', None)
        space = getattr(self.ap, 'space_service', None)
        if users is None or space is None:
            return {}
        owner = await users.get_workspace_owner(workspace_uuid)
        email = getattr(owner, 'user', None)
        token = await space.get_valid_access_token(email) if email else None
        return {'Authorization': f'Bearer {token}'} if token else {}

    def _remove(self, ids):
        self.pending[:] = [e for e in self.pending if e['event_id'] not in ids]
        for event_id in ids:
            self._attempts.pop(event_id, None)
            self._born.pop(event_id, None)

    async def flush_once(self):
        async with self._flush_lock:
            if not self.enabled:
                self.clear()
                return
            expired = {
                e['event_id']
                for e in self.pending
                if time.monotonic() - self._born.get(e['event_id'], 0) > self.retention_seconds
            }
            self.counters['dropped'] += len(expired)
            self._remove(expired)
            if not self.pending:
                return
            # Do not authenticate a mixed-Workspace batch with one owner's token.
            workspace = self.pending[0]['workspace_uuid']
            batch, size = [], 64
            for event in self.pending:
                n = len(json.dumps(event).encode()) + 2
                if event['workspace_uuid'] != workspace:
                    continue
                if len(batch) == 50 or size + n > 256 * 1024:
                    break
                batch.append(event)
                size += n
            ids = {e['event_id'] for e in batch}
            for event_id in ids:
                self._attempts[event_id] = self._attempts.get(event_id, 0) + 1
            acked, rejected = set(), set()
            permanent = False
            try:
                async with asyncio.timeout(self.request_timeout):
                    headers = {}
                    try:
                        async with asyncio.timeout(min(1.0, self.request_timeout / 3)):
                            headers = await self.credentials(workspace)
                    except Exception:
                        pass
                    if not self.enabled:
                        self.clear()
                        return
                    if self.client is None:
                        self.client = httpx.AsyncClient(timeout=self.request_timeout, follow_redirects=False)
                    url = (
                        self.ap.instance_config.data['space']['url'].rstrip('/') + '/api/v1/telemetry/diagnostics/batch'
                    )
                    # Stream the response to bound malicious/old server responses too.
                    async with self.client.stream(
                        'POST', url, json={'schema_version': 1, 'events': batch}, headers=headers
                    ) as response:
                        body = bytearray()
                        async for chunk in response.aiter_bytes():
                            body.extend(chunk)
                            if len(body) > 65536:
                                raise ValueError('diagnostics_response_limit')
                        if response.status_code == 200:
                            payload = json.loads(body)
                            if payload.get('code') == 200 and isinstance(payload.get('data'), dict):
                                data = payload['data']
                                acked = {x for x in data.get('accepted_event_ids', []) if isinstance(x, str)} & ids
                                rejected = {
                                    x.get('event_id')
                                    for x in data.get('rejected', [])
                                    if isinstance(x, dict) and x.get('code') == 'invalid_event'
                                } & ids
                            elif isinstance(payload.get('code'), int):
                                permanent = 400 <= payload['code'] < 500 and payload['code'] != 429
                        else:
                            permanent = 400 <= response.status_code < 500 and response.status_code != 429
            except asyncio.CancelledError:
                raise
            except Exception:
                pass
            if not self.enabled:
                self.clear()
                return
            rejected -= acked
            remaining = ids - acked - rejected
            if remaining:
                self.counters['failed'] += 1
            exhausted = {i for i in remaining if permanent or self._attempts.get(i, 0) >= self.max_attempts}
            self.counters['acked'] += len(acked)
            self.counters['dropped'] += len(rejected | exhausted)
            self._last_retry = bool(remaining - exhausted)
            self.counters['retried'] += len(remaining - exhausted)
            self._remove(acked | rejected | exhausted)

    def report_transport(self, stage='snapshot'):
        # Snapshot interval deltas before enqueue; retries retain this event ID.
        snapshot = self.counters.copy()
        delta = snapshot - self._reported
        before = self.counters['queued']
        self.emit(
            'transport',
            'diagnostics.transport',
            'partial' if delta['dropped'] else 'succeeded',
            stage=stage,
            attributes={**dict(delta), 'queue_size': len(self.pending), 'capacity': self.capacity},
        )
        if self.counters['queued'] > before:
            self._reported = snapshot

    def start(self):
        if self.beta and self._worker is None:
            self._worker = asyncio.create_task(self._loop(), name='beta-diagnostics')

    async def _loop(self):
        next_send, next_summary, backoff = 0.0, time.monotonic() + 60, 0.0
        try:
            while not self._closing:
                if not self.enabled:
                    self.clear()
                    if self._marker_active:
                        await self._clear_marker()
                elif time.monotonic() >= next_summary:
                    self.report_transport()
                    next_summary = time.monotonic() + 60
                if self._request is not None and self._request.done():
                    with contextlib.suppress(asyncio.CancelledError, Exception):
                        self._request.result()
                    self._request = None
                    backoff = min(30, max(1, backoff * 2)) if self._last_retry else 0
                    next_send = time.monotonic() + random.uniform(0.5, 1.5) * backoff
                if self.enabled and self.pending and self._request is None and time.monotonic() >= next_send:
                    self._request = asyncio.create_task(self.flush_once(), name='beta-diagnostics-batch')
                self._wake.clear()
                with contextlib.suppress(TimeoutError):
                    await asyncio.wait_for(self._wake.wait(), 0.1)
        finally:
            if self._request is not None:
                self._request.cancel()
                await asyncio.gather(self._request, return_exceptions=True)

    async def shutdown(self, drain_timeout=2):
        if self._worker is not None:
            self._worker.cancel()
            await asyncio.gather(self._worker, return_exceptions=True)
            self._worker = None
        if self.enabled and drain_timeout > 0:
            self.report_transport(stage='shutdown')
            with contextlib.suppress(Exception):
                async with asyncio.timeout(drain_timeout):
                    while self.pending:
                        await self.flush_once()
                        if self.pending:
                            await asyncio.sleep(0.1)
        self.counters['dropped'] += len(self.pending)
        self._closing = True
        self.clear()
        await self._clear_marker()
        if self.client is not None:
            await self.client.aclose()
