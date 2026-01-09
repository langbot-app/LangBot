from __future__ import annotations

import asyncio
import httpx


class TelemetryManager:
    """TelemetryManager handles sending telemetry for a given application instance.

    Usage:
        telemetry = TelemetryManager(ap)
        await telemetry.send({ ... })
    """

    send_tasks: list[asyncio.Task] = []

    def __init__(self, ap):
        self.ap = ap

        self.telemetry_config = {}

    async def initialize(self):
        self.telemetry_config = self.ap.instance_config.data.get('space', {})

    async def start_send_task(self, payload: dict):
        task = asyncio.create_task(self.send(payload))
        self.send_tasks.append(task)

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

                for sfield in ('adapter', 'runner', 'model_name', 'version', 'error', 'timestamp'):
                    v = sanitized.get(sfield)
                    sanitized[sfield] = '' if v is None else str(v)

                if 'duration_ms' in sanitized:
                    try:
                        sanitized['duration_ms'] = (
                            int(sanitized['duration_ms']) if sanitized['duration_ms'] is not None else 0
                        )
                    except Exception:
                        sanitized['duration_ms'] = 0

                async with httpx.AsyncClient(timeout=httpx.Timeout(10)) as client:
                    try:
                        # Use asyncio.wait_for to ensure we always bound the total time
                        resp = await asyncio.wait_for(client.post(url, json=sanitized), timeout=10 + 1)

                        if resp.status_code >= 400:
                            self.ap.logger.warning(
                                f'Telemetry post to {url} returned status {resp.status_code} - {resp.text}'
                            )
                        else:
                            # Detect application-level errors inside HTTP 200 responses
                            app_err = False
                            try:
                                j = resp.json()
                                if isinstance(j, dict) and j.get('code') is not None and int(j.get('code')) >= 400:
                                    app_err = True
                                    self.ap.logger.warning(
                                        f'Telemetry post to {url} returned application error code {j.get("code")} - {j.get("msg")}'
                                    )
                            except Exception:
                                pass

                            if app_err:
                                self.ap.logger.warning(
                                    f'Telemetry post to {url} returned app-level error - response: {resp.text[:200]}'
                                )
                            else:
                                self.ap.logger.debug(
                                    f'Telemetry posted to {url}, status {resp.status_code} - response: {resp.text[:200]}'
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
