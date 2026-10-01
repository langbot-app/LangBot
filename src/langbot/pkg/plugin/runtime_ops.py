"""Cloud Edition runtime ops sample reporter.

Aggregates this instance's plugin Runtime health (probed from the Runtime
``/healthz`` endpoint) together with the connector's own desired-state and
failure registries, then pushes one compact sample to the Space control
plane where the internal ops dashboard stores and renders it.

This is a Cloud-only ops channel, deliberately separate from product
telemetry so ``space.disable_telemetry`` cannot blind operations. Sending is
best-effort: a failed probe or upload never raises out of the reporter.
"""

from __future__ import annotations

import asyncio
import contextlib
import datetime
import math
import os
import typing
from urllib.parse import urlsplit, urlunsplit

import httpx

from ..utils import constants, httpclient

_CONTROL_PLANE_TOKEN_ENV = 'LANGBOT_SPACE_CONTROL_PLANE_TOKEN'
_RUNTIME_OPS_PATH = '/api/v1/cloud/v2/internal/runtime-ops'
_DEFAULT_INTERVAL_SECONDS = 30.0
_DEFAULT_TIMEOUT_SECONDS = 10.0
_DEFAULT_MAX_FAILURES = 5
_MAX_FAILURE_MESSAGE_CHARS = 512


def _utc_now_iso() -> str:
    """Return the current UTC time as a second-precision RFC 3339 string."""

    return datetime.datetime.now(datetime.timezone.utc).isoformat(timespec='seconds').replace('+00:00', 'Z')


def _coerce_bool(value: typing.Any, default: bool) -> bool:
    return value if isinstance(value, bool) else default


def _coerce_positive_float(value: typing.Any, default: float) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return default
    value = float(value)
    if not math.isfinite(value) or value <= 0:
        return default
    return value


def _coerce_positive_int(value: typing.Any, default: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        return default
    return value


def _sanitize_failure_message(value: typing.Any) -> str:
    """Flatten and bound one failure message for the wire.

    Mirrors the connector's own sanitization so ops never receives control
    characters, unbounded payloads, or newline-injected log content.
    """

    candidate = str(value or '').replace('\r', ' ').replace('\n', ' ').strip()
    return candidate[:_MAX_FAILURE_MESSAGE_CHARS]


class RuntimeOpsReporter:
    """Collect and push one runtime ops sample per interval.

    The reporter never raises out of its send loop; failures are counted and
    surfaced through :meth:`get_stats`.
    """

    def __init__(self, ap: typing.Any):
        self.ap = ap
        instance_data = getattr(getattr(ap, 'instance_config', None), 'data', None)
        if not isinstance(instance_data, dict):
            instance_data = {}
        plugin_config = instance_data.get('plugin', {})
        if not isinstance(plugin_config, dict):
            plugin_config = {}
        config = plugin_config.get('runtime_ops', {})
        if not isinstance(config, dict):
            config = {}
        self.config = config

        deployment_mode = getattr(getattr(ap, 'deployment', None), 'mode', 'oss')
        cloud_edition = deployment_mode == 'cloud'
        # Cloud-only feature: an explicit flag may turn it off, but a
        # non-cloud deployment is never enabled.
        self.enabled = cloud_edition and _coerce_bool(config.get('enabled'), True)
        self.interval_seconds = _coerce_positive_float(config.get('interval_seconds'), _DEFAULT_INTERVAL_SECONDS)
        self.timeout_seconds = _coerce_positive_float(config.get('timeout_seconds'), _DEFAULT_TIMEOUT_SECONDS)
        self.max_failures = _coerce_positive_int(config.get('max_failures'), _DEFAULT_MAX_FAILURES)

        self.health_url = self._derive_health_url(plugin_config.get('runtime_ws_url'))
        self.space_url = str(instance_data.get('space', {}).get('url', '') or '').rstrip('/')
        self._token = str(os.environ.get(_CONTROL_PLANE_TOKEN_ENV, '') or '').strip()

        if self.enabled and not self.health_url:
            self._log_info(
                'Plugin runtime ops reporter is disabled: no plugin runtime WebSocket URL is configured'
            )
            self.enabled = False
        if self.enabled and not self.space_url:
            self._log_info('Plugin runtime ops reporter is disabled: no Space URL is configured')
            self.enabled = False

        self._task: asyncio.Task | None = None
        self._client: httpx.AsyncClient | None = None
        self._sent_total = 0
        self._dropped_total = 0
        self._last_error: str | None = None

    def _log_info(self, message: str) -> None:
        logger = getattr(self.ap, 'logger', None)
        info = getattr(logger, 'info', None)
        if callable(info):
            info(message)

    @staticmethod
    def _derive_health_url(runtime_ws_url: typing.Any) -> str | None:
        """Derive the Runtime ``/healthz`` URL from the control WebSocket URL."""

        if not isinstance(runtime_ws_url, str):
            return None
        candidate = runtime_ws_url.strip()
        if not candidate:
            return None
        try:
            parts = urlsplit(candidate)
            port = parts.port
        except ValueError:
            return None
        if parts.scheme not in ('ws', 'wss') or not parts.hostname:
            return None
        scheme = 'https' if parts.scheme == 'wss' else 'http'
        netloc = parts.hostname if port is None else f'{parts.hostname}:{port}'
        return urlunsplit((scheme, netloc, '/healthz', '', ''))

    def start(self) -> None:
        """Start the background sample loop once the control link is up."""

        if not self.enabled:
            return
        if self._task is not None and not self._task.done():
            return
        self._task = asyncio.create_task(self._run())

    async def stop(self) -> None:
        """Cancel the sample loop and release the HTTP client."""

        task = self._task
        self._task = None
        if task is not None and task is not asyncio.current_task():
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
        client = self._client
        self._client = None
        if client is not None and not client.is_closed:
            with contextlib.suppress(Exception):
                await client.aclose()

    def get_stats(self) -> dict[str, typing.Any]:
        """Return in-memory counters for the instance liveness surface."""

        return {
            'sent_total': self._sent_total,
            'dropped_total': self._dropped_total,
            'last_error': self._last_error,
        }

    @contextlib.asynccontextmanager
    async def _client_context(self):
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(self.timeout_seconds),
                event_hooks=httpclient.httpx_response_limit_hooks(),
            )
        yield self._client

    async def _run(self) -> None:
        while True:
            try:
                await self._collect_and_send()
            except asyncio.CancelledError:
                raise
            except Exception as exc:  # never let the ops channel crash the connector
                self._last_error = _sanitize_failure_message(f'sample cycle failed: {exc}')
            await asyncio.sleep(self.interval_seconds)

    async def _collect_and_send(self) -> None:
        health = await self._fetch_health()
        if health is None:
            self._dropped_total += 1
            return
        await self._post(self.build_payload(health))

    async def _fetch_health(self) -> dict[str, typing.Any] | None:
        """Probe the Runtime ``/healthz`` endpoint, returning its verbatim JSON."""

        try:
            async with self._client_context() as client:
                response = await asyncio.wait_for(
                    client.get(self.health_url),
                    timeout=self.timeout_seconds,
                )
            if response.status_code >= 400:
                self._last_error = f'health probe returned status {response.status_code}'
                return None
            payload = await httpclient.parse_json_response(response)
            if not isinstance(payload, dict):
                self._last_error = 'health probe returned a non-object payload'
                return None
            self._last_error = None
            return payload
        except asyncio.TimeoutError:
            self._last_error = 'health probe timed out'
            return None
        except Exception as exc:
            self._last_error = _sanitize_failure_message(f'health probe failed: {exc}')
            return None

    async def _post(self, payload: dict[str, typing.Any]) -> None:
        """Best-effort POST of one sample; never raises."""

        url = f'{self.space_url}{_RUNTIME_OPS_PATH}'
        headers = {'Authorization': f'Bearer {self._token}'}
        try:
            async with self._client_context() as client:
                response = await asyncio.wait_for(
                    client.post(url, json=payload, headers=headers),
                    timeout=self.timeout_seconds,
                )
            if response.status_code >= 400:
                body = await httpclient.response_text(response, max_chars=200)
                self._dropped_total += 1
                self._last_error = f'POST {url} returned status {response.status_code} - {body}'
                return
            self._sent_total += 1
            self._last_error = None
        except asyncio.TimeoutError:
            self._dropped_total += 1
            self._last_error = f'POST {url} timed out'
        except Exception as exc:
            self._dropped_total += 1
            self._last_error = _sanitize_failure_message(f'POST {url} failed: {exc}')

    def build_payload(self, health: dict[str, typing.Any]) -> dict[str, typing.Any]:
        """Assemble one ops sample in the frozen Core -> Space contract shape."""

        connector = getattr(self.ap, 'plugin_connector', None)
        instance_data = getattr(getattr(self.ap, 'instance_config', None), 'data', None)
        if not isinstance(instance_data, dict):
            instance_data = {}
        system_config = instance_data.get('system', {})
        if not isinstance(system_config, dict):
            system_config = {}
        instance_uuid = str(system_config.get('instance_id', '') or '') or str(constants.instance_id or '')
        edition = str(system_config.get('edition', 'oss') or 'oss')
        return {
            'event': 'runtime_ops_sample',
            'kind': 'aggregate',
            'instance_uuid': instance_uuid,
            'generated_at': _utc_now_iso(),
            'core': {
                'version': constants.semantic_version,
                'edition': edition,
                'connected': self._runtime_connected(connector),
                'runtime_profile': getattr(connector, 'runtime_profile', 'oss_dev'),
                'worker_policy': self._worker_policy(connector),
                'desired_states': self._desired_states(connector),
                'reconcile': self._reconcile_summary(connector),
            },
            'health': health,
            'failures': self._failures(connector),
        }

    @staticmethod
    def _runtime_connected(connector: typing.Any) -> bool:
        available = getattr(connector, '_runtime_available', None)
        if not callable(available):
            return False
        try:
            return bool(available())
        except Exception:
            return False

    @staticmethod
    def _worker_policy(connector: typing.Any) -> dict[str, typing.Any] | None:
        policy = getattr(connector, 'worker_policy', None)
        if policy is None:
            return None
        model_dump = getattr(policy, 'model_dump', None)
        if callable(model_dump):
            return model_dump()
        if isinstance(policy, dict):
            return dict(policy)
        return None

    @staticmethod
    def _desired_states(connector: typing.Any) -> dict[str, typing.Any]:
        states = getattr(connector, '_known_desired_states', None)
        if not isinstance(states, dict):
            states = {}
        enabled = 0
        by_mode: dict[str, int] = {}
        for state in states.values():
            if bool(getattr(state, 'enabled', False)):
                enabled += 1
            mode = getattr(getattr(state, 'execution_mode', None), 'value', None)
            mode = str(mode) if isinstance(mode, str) and mode else 'dedicated'
            by_mode[mode] = by_mode.get(mode, 0) + 1
        return {'total': len(states), 'enabled': enabled, 'by_mode': by_mode}

    @staticmethod
    def _reconcile_summary(connector: typing.Any) -> dict[str, typing.Any]:
        summary = getattr(connector, '_reconcile_summary', None)
        if isinstance(summary, dict):
            return dict(summary)
        return {
            'last_started_at': None,
            'last_duration_ms': None,
            'last_ok': None,
            'failed_installations': 0,
            'missing_artifacts': 0,
        }

    def _failures(self, connector: typing.Any) -> list[dict[str, typing.Any]]:
        records = getattr(connector, '_installation_failures', None)
        if not isinstance(records, dict):
            return []
        states = getattr(connector, '_known_desired_states', None)
        if not isinstance(states, dict):
            states = {}
        identities = self._plugin_identities(connector)
        observed_at = _utc_now_iso()
        failures: list[dict[str, typing.Any]] = []
        for installation_uuid in list(records)[: self.max_failures]:
            record = records.get(installation_uuid)
            if not isinstance(record, dict):
                continue
            state = states.get(installation_uuid)
            binding = getattr(state, 'binding', None)
            mode = getattr(getattr(state, 'execution_mode', None), 'value', None)
            mode = str(mode) if isinstance(mode, str) and mode else 'dedicated'
            plugin_author, plugin_name = identities.get(str(installation_uuid), ('', ''))
            failures.append(
                {
                    'workspace_uuid': str(getattr(binding, 'workspace_uuid', '') or ''),
                    'installation_uuid': str(installation_uuid),
                    'plugin_author': plugin_author,
                    'plugin_name': plugin_name,
                    'execution_mode': mode,
                    'error_code': str(record.get('error_code', '') or ''),
                    'message': _sanitize_failure_message(record.get('message')),
                    'observed_at': observed_at,
                }
            )
        return failures

    @staticmethod
    def _plugin_identities(connector: typing.Any) -> dict[str, tuple[str, str]]:
        """Read the connector handler's installation identity registry.

        The Runtime connection handler binds every desired installation to
        its plugin identity; the connector's failure records themselves only
        carry the installation UUID, so the reporter joins them here.
        """

        handler = getattr(connector, 'handler', None)
        bindings = getattr(handler, '_installation_bindings', None)
        if not isinstance(bindings, dict):
            return {}
        identities: dict[str, tuple[str, str]] = {}
        for installation_uuid, entry in bindings.items():
            try:
                identity = entry[1]
            except (TypeError, IndexError, KeyError):
                continue
            identities[str(installation_uuid)] = (
                str(getattr(identity, 'plugin_author', '') or ''),
                str(getattr(identity, 'plugin_name', '') or ''),
            )
        return identities
