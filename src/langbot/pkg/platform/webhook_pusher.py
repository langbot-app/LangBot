from __future__ import annotations

import asyncio
import logging
import aiohttp
import uuid
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..core import app

import langbot_plugin.api.entities.builtin.platform.events as platform_events


class WebhookPusher:
    """Push bot events to configured webhooks"""

    ap: app.Application
    logger: logging.Logger

    def __init__(self, ap: app.Application):
        self.ap = ap
        self.logger = self.ap.logger

    async def push_person_message(self, event: platform_events.FriendMessage, bot_uuid: str, adapter_name: str) -> None:
        """Push person message event to webhooks"""
        try:
            webhooks = await self.ap.webhook_service.get_enabled_webhooks()
            if not webhooks:
                return

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

            # Push to all webhooks asynchronously
            tasks = [self._push_to_webhook(webhook['url'], payload) for webhook in webhooks]
            await asyncio.gather(*tasks, return_exceptions=True)

        except Exception as e:
            self.logger.error(f'Failed to push person message to webhooks: {e}')

    async def push_group_message(self, event: platform_events.GroupMessage, bot_uuid: str, adapter_name: str) -> None:
        """Push group message event to webhooks"""
        try:
            webhooks = await self.ap.webhook_service.get_enabled_webhooks()
            if not webhooks:
                return

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

            # Push to all webhooks asynchronously
            tasks = [self._push_to_webhook(webhook['url'], payload) for webhook in webhooks]
            await asyncio.gather(*tasks, return_exceptions=True)

        except Exception as e:
            self.logger.error(f'Failed to push group message to webhooks: {e}')

    async def _push_to_webhook(self, url: str, payload: dict) -> None:
        """Push payload to a single webhook URL"""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    url,
                    json=payload,
                    headers={'Content-Type': 'application/json'},
                    timeout=aiohttp.ClientTimeout(total=15),
                ) as response:
                    if response.status >= 400:
                        self.logger.warning(f'Webhook {url} returned status {response.status}')
                    else:
                        self.logger.debug(f'Successfully pushed to webhook {url}')
        except asyncio.TimeoutError:
            self.logger.warning(f'Timeout pushing to webhook {url}')
        except Exception as e:
            self.logger.warning(f'Error pushing to webhook {url}: {e}')
