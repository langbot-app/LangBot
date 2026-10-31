from __future__ import annotations

import asyncio
import logging
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from langbot.pkg.platform.webhook_pusher import WebhookPusher


pytestmark = pytest.mark.asyncio


def _application(max_inflight_requests: object) -> SimpleNamespace:
    return SimpleNamespace(
        instance_config=SimpleNamespace(
            data={
                'webhooks': {
                    'max_inflight_requests': max_inflight_requests,
                }
            }
        ),
        logger=logging.getLogger(__name__),
    )


async def test_delivery_admission_never_queues_above_instance_limit():
    pusher = WebhookPusher(_application(2))
    release = asyncio.Event()
    both_started = asyncio.Event()
    calls = 0
    active = 0
    peak_active = 0

    async def fake_push(url: str, payload: dict) -> dict:
        nonlocal calls, active, peak_active
        calls += 1
        active += 1
        peak_active = max(peak_active, active)
        if active == 2:
            both_started.set()
        try:
            await release.wait()
            return {'url': url}
        finally:
            active -= 1

    pusher._push_to_webhook = fake_push
    webhooks = [{'url': f'https://example.invalid/{index}'} for index in range(5)]

    first_delivery = asyncio.create_task(pusher._push_to_webhooks(webhooks, {}))
    await asyncio.wait_for(both_started.wait(), timeout=1)
    second_results = await pusher._push_to_webhooks(webhooks, {})
    release.set()
    first_results = await first_delivery

    assert len(first_results) == 2
    assert second_results == []
    assert calls == 2
    assert peak_active == 2
    assert pusher._inflight_requests == 0


async def test_cancelled_delivery_reaps_children_and_releases_slots():
    pusher = WebhookPusher(_application(1))
    started = asyncio.Event()
    never = asyncio.Event()

    async def blocking_push(url: str, payload: dict) -> dict:
        started.set()
        await never.wait()
        return {}

    pusher._push_to_webhook = blocking_push
    delivery = asyncio.create_task(
        pusher._push_to_webhooks([{'url': 'https://example.invalid'}], {}),
    )
    await asyncio.wait_for(started.wait(), timeout=1)

    delivery.cancel()
    with pytest.raises(asyncio.CancelledError):
        await delivery

    assert pusher._inflight_requests == 0
    pusher._push_to_webhook = AsyncMock(return_value={})
    assert await pusher._push_to_webhooks([{'url': 'https://example.invalid'}], {}) == [{}]


async def test_max_inflight_requests_clamps_config():
    pusher = WebhookPusher(_application(999999))
    assert pusher._max_inflight_requests() == 128

    pusher.ap.instance_config.data['webhooks']['max_inflight_requests'] = 0
    assert pusher._max_inflight_requests() == 1

    pusher.ap.instance_config.data['webhooks']['max_inflight_requests'] = 'invalid'
    assert pusher._max_inflight_requests() == 16
