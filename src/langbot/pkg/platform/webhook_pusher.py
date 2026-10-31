from __future__ import annotations

import asyncio
import logging
import aiohttp

from langbot.pkg.utils import httpclient
from langbot.pkg.api.http.context import ExecutionContext
import uuid
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..core import app

import langbot_plugin.api.entities.builtin.platform.events as platform_events


_DEFAULT_MAX_INFLIGHT_WEBHOOK_REQUESTS = 16
_HARD_MAX_INFLIGHT_WEBHOOK_REQUESTS = 128


class WebhookPusher:
    """Push bot events to configured webhooks"""

    ap: app.Application
    logger: logging.Logger

    def __init__(self, ap: app.Application):
        self.ap = ap
        self.logger = self.ap.logger
        self._delivery_lock = asyncio.Lock()
        self._inflight_requests = 0

    def _max_inflight_requests(self) -> int:
        config = getattr(getattr(self.ap, 'instance_config', None), 'data', {})
        try:
            value = int(
                config.get('webhooks', {}).get(
                    'max_inflight_requests',
                    _DEFAULT_MAX_INFLIGHT_WEBHOOK_REQUESTS,
                )
            )
        except (AttributeError, TypeError, ValueError):
            value = _DEFAULT_MAX_INFLIGHT_WEBHOOK_REQUESTS
        return min(max(value, 1), _HARD_MAX_INFLIGHT_WEBHOOK_REQUESTS)

    async def _reserve_delivery_slots(self, requested: int) -> int:
        async with self._delivery_lock:
            available = max(self._max_inflight_requests() - self._inflight_requests, 0)
            admitted = min(max(requested, 0), available)
            self._inflight_requests += admitted
            return admitted

    async def _release_delivery_slots(self, released: int) -> None:
        async with self._delivery_lock:
            self._inflight_requests = max(self._inflight_requests - released, 0)

    async def _push_to_webhooks(self, webhooks: list[dict], payload: dict) -> list[object]:
        """Dispatch only requests admitted by the instance-wide hard bound."""

        admitted = await self._reserve_delivery_slots(len(webhooks))
        if admitted < len(webhooks):
            self.logger.warning(
                'Webhook delivery capacity reached; skipped %d of %d destinations',
                len(webhooks) - admitted,
                len(webhooks),
            )
        if admitted == 0:
            return []

        tasks = [asyncio.create_task(self._push_to_webhook(webhook['url'], payload)) for webhook in webhooks[:admitted]]
        try:
            return await asyncio.gather(*tasks, return_exceptions=True)
        except asyncio.CancelledError:
            for task in tasks:
                task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)
            raise
        finally:
            await self._release_delivery_slots(admitted)

    async def push_person_message(
        self,
        execution_context: ExecutionContext,
        event: platform_events.FriendMessage,
        bot_uuid: str,
        adapter_name: str,
    ) -> bool:
        """Push person message event to webhooks

        Returns:
            bool: True if any webhook responded with skip_pipeline=true, False otherwise
        """
        try:
            webhooks = await self.ap.webhook_service.get_enabled_webhooks(execution_context)
            if not webhooks:
                return False

            # Build payload
            payload = {
                'uuid': str(uuid.uuid4()),  # unique id for the event
                'event_type': 'bot.person_message',
                'data': {
                    'bot_uuid': bot_uuid,
                    'adapter_name': adapter_name,
                    'sender': {
                        'id': str(event.sender.id),
                        'name': getattr(event.sender, 'name', ''),
                    },
                    'message': event.message_chain.model_dump(),
                    'timestamp': event.time if hasattr(event, 'time') else None,
                },
            }

            results = await self._push_to_webhooks(webhooks, payload)

            # Check if any webhook responded with skip_pipeline=true
            for result in results:
                if isinstance(result, dict) and result.get('skip_pipeline') is True:
                    self.logger.info('Webhook responded with skip_pipeline=true, skipping pipeline for person message')
                    return True

            return False

        except Exception as e:
            self.logger.error(f'Failed to push person message to webhooks: {e}')
            return False

    async def push_group_message(
        self,
        execution_context: ExecutionContext,
        event: platform_events.GroupMessage,
        bot_uuid: str,
        adapter_name: str,
    ) -> bool:
        """Push group message event to webhooks

        Returns:
            bool: True if any webhook responded with skip_pipeline=true, False otherwise
        """
        try:
            webhooks = await self.ap.webhook_service.get_enabled_webhooks(execution_context)
            if not webhooks:
                return False

            # Build payload
            payload = {
                'uuid': str(uuid.uuid4()),  # unique id for the event
                'event_type': 'bot.group_message',
                'data': {
                    'bot_uuid': bot_uuid,
                    'adapter_name': adapter_name,
                    'group': {
                        'id': str(event.group.id),
                        'name': getattr(event.group, 'name', ''),
                    },
                    'sender': {
                        'id': str(event.sender.id),
                        'name': getattr(event.sender, 'name', ''),
                    },
                    'message': event.message_chain.model_dump(),
                    'timestamp': event.time if hasattr(event, 'time') else None,
                },
            }

            results = await self._push_to_webhooks(webhooks, payload)

            # Check if any webhook responded with skip_pipeline=true
            for result in results:
                if isinstance(result, dict) and result.get('skip_pipeline') is True:
                    self.logger.info('Webhook responded with skip_pipeline=true, skipping pipeline for group message')
                    return True

            return False

        except Exception as e:
            self.logger.error(f'Failed to push group message to webhooks: {e}')
            return False

    async def _push_to_webhook(self, url: str, payload: dict) -> dict | None:
        """Push payload to a single webhook URL

        Returns:
            dict | None: The response JSON if successful, None otherwise
        """
        try:
            session = httpclient.get_session()
            async with session.post(
                url,
                json=payload,
                headers={'Content-Type': 'application/json'},
                timeout=aiohttp.ClientTimeout(total=15),
            ) as response:
                if response.status >= 400:
                    self.logger.warning(f'Webhook {url} returned status {response.status}')
                    return None
                else:
                    self.logger.debug(f'Successfully pushed to webhook {url}')
                    try:
                        result = await httpclient.read_json_limited(response)
                        return result if isinstance(result, dict) else None
                    except Exception as json_error:
                        self.logger.debug(f'Failed to parse JSON response from webhook {url}: {json_error}')
                        return None
        except asyncio.TimeoutError:
            self.logger.warning(f'Timeout pushing to webhook {url}')
            return None
        except Exception as e:
            self.logger.warning(f'Error pushing to webhook {url}: {e}')
            return None
