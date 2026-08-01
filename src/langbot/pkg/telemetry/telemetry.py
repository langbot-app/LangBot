from __future__ import annotations

import asyncio
import contextlib
import os
import typing

import httpx

from ..core import app as core_app
from ..utils import httpclient


_MAX_INFLIGHT_TELEMETRY_TASKS = 8


class TelemetryManager:
    """TelemetryManager handles sending telemetry for a given application instance.

    Usage:
        telemetry = TelemetryManager(ap)
        await telemetry.send({ ... })
    """

    def __init__(self, ap: core_app.Application):
        self.ap = ap

        self.telemetry_config: dict[str, typing.Any] = {}
        self.send_tasks: list[asyncio.Task] = []
        self._client: httpx.AsyncClient | None = None

    async def initialize(self):
        self.telemetry_config = self.ap.instance_config.data.get('space', {})

    async def start_send_task(self, payload: dict):
        self.send_tasks = [task for task in self.send_tasks if not task.done()]
        if len(self.send_tasks) >= _MAX_INFLIGHT_TELEMETRY_TASKS:
            self.ap.logger.debug('Telemetry queue is full; dropping best-effort event')
            return
        task = asyncio.create_task(self.send(payload))
        self.send_tasks.append(task)
        task.add_done_callback(self._send_task_done)

    def _send_task_done(self, task: asyncio.Task) -> None:
        try:
            self.send_tasks.remove(task)
        except ValueError:
            pass

    async def shutdown(self) -> None:
        tasks = list(self.send_tasks)
        for task in tasks:
            task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        self.send_tasks.clear()
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    @contextlib.asynccontextmanager
    async def _client_context(self):
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(10),
                event_hooks=httpclient.httpx_response_limit_hooks(),
            )
        yield self._client

    async def send(self, payload: dict):
        """Send telemetry payload to configured telemetry server (non-blocking).

        Expects ap.instance_config.data.telemetry to have:
          - enabled: bool
          - server: str (base URL, e.g. https://space.example.com)
          - timeout_seconds: optional int, overall request timeout (default 10)

        Posts to {server.rstrip('/')}/api/v1/telemetry as JSON. Failures are logged but do not raise.
        """

        try:
            cfg = self.telemetry_config
            if not cfg:
                return
            if cfg.get('disable_telemetry', False):
                return
            server = cfg.get('url', '')
            if not server:
                return

            # Normalize URL
            url = server.rstrip('/') + '/api/v1/telemetry'

            try:
                # Sanitize payload so string fields are strings and not nulls
                sanitized = dict(payload)
                if 'query_id' in sanitized:
                    try:
                        sanitized['query_id'] = '' if sanitized['query_id'] is None else str(sanitized['query_id'])
                    except Exception:
                        sanitized['query_id'] = str(sanitized.get('query_id', ''))

                for sfield in (
                    'adapter',
                    'runner',
                    'runner_category',
                    'model_name',
                    'version',
                    'edition',
                    'error',
                    'timestamp',
                    'event_type',
                ):
                    if sfield not in sanitized:
                        continue
                    v = sanitized.get(sfield)
                    sanitized[sfield] = '' if v is None else str(v)

                # event_type defaults to 'query' for backward compatibility
                if not sanitized.get('event_type'):
                    sanitized['event_type'] = 'query'

                # features must be a JSON object
                if 'features' in sanitized and not isinstance(sanitized['features'], dict):
                    sanitized['features'] = {}

                if 'duration_ms' in sanitized:
                    try:
                        sanitized['duration_ms'] = (
                            int(sanitized['duration_ms']) if sanitized['duration_ms'] is not None else 0
                        )
                    except Exception:
                        sanitized['duration_ms'] = 0

                async with self._client_context() as client:
                    try:
                        # Use asyncio.wait_for to ensure we always bound the total time
                        telemetry_token = os.getenv('LANGBOT_TELEMETRY_INGEST_TOKEN', '').strip()
                        if telemetry_token:
                            request = client.post(
                                url,
                                json=sanitized,
                                headers={'X-LangBot-Telemetry-Token': telemetry_token},
                            )
                        else:
                            request = client.post(url, json=sanitized)
                        resp = await asyncio.wait_for(request, timeout=10 + 1)

                        if resp.status_code >= 400:
                            body = await httpclient.response_text(resp, max_chars=200)
                            self.ap.logger.warning(
                                f'Telemetry post to {url} returned status {resp.status_code} - {body}'
                            )
                        else:
                            # Detect application-level errors inside HTTP 200 responses
                            app_err = False
                            try:
                                j = await httpclient.parse_json_response(resp)
                                app_code = j.get('code') if isinstance(j, dict) else None
                                if app_code is not None and int(app_code) >= 400:
                                    app_err = True
                                    self.ap.logger.warning(
                                        f'Telemetry post to {url} returned application error code {j.get("code")} - {j.get("msg")}'
                                    )
                            except Exception:
                                pass

                            if app_err:
                                body = await httpclient.response_text(resp, max_chars=200)
                                self.ap.logger.warning(
                                    f'Telemetry post to {url} returned app-level error - response: {body}'
                                )
                            else:
                                body = await httpclient.response_text(resp, max_chars=200)
                                self.ap.logger.debug(
                                    f'Telemetry posted to {url}, status {resp.status_code} - response: {body}'
                                )
                    except asyncio.TimeoutError:
                        self.ap.logger.warning(f'Telemetry post to {url} timed out')
                    except Exception as e:
                        self.ap.logger.warning(f'Failed to post telemetry to {url}: {e}', exc_info=True)
            except Exception as e:
                try:
                    self.ap.logger.warning(
                        f'Failed to create HTTP client for telemetry or sanitize payload: {e}', exc_info=True
                    )
                except Exception:
                    pass
        except Exception as e:
            # Never raise from telemetry; surface as warning for visibility
            try:
                self.ap.logger.warning(f'Unexpected telemetry error: {e}', exc_info=True)
            except Exception:
                pass
