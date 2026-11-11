"""Recognize redelivered copies of one native platform message."""

from __future__ import annotations

import asyncio
import contextlib
import typing
from collections import OrderedDict

import langbot_plugin.api.entities.builtin.platform.events as platform_events

DeliveryKey = tuple[str, ...]


def delivery_key(event: platform_events.EBAEvent) -> DeliveryKey | None:
    """Identify one native message, or return None when it cannot be identified.

    Message IDs are only unique inside a chat on several platforms and may be
    reused over time, so chat, sender and the platform timestamp are part of the
    identity. A message without an ID or timestamp is never treated as a copy.
    """
    if not isinstance(event, platform_events.MessageReceivedEvent):
        return None
    message_id = str(event.message_id if event.message_id is not None else '')
    if message_id in ('', '0', '-1') or not event.timestamp:
        return None
    return (
        str(getattr(event.chat_type, 'value', event.chat_type)),
        str(event.chat_id),
        str(event.sender.id),
        message_id,
        str(event.timestamp),
    )


class InboundDelivery:
    """One admitted delivery; ``accept`` marks it as handed over for processing."""

    def __init__(self, outcome: asyncio.Future[bool] | None):
        self._outcome = outcome

    def accept(self) -> None:
        if self._outcome is not None and not self._outcome.done():
            self._outcome.set_result(True)


class InboundDeliveries:
    """Admit each native message once per bot without serializing other messages."""

    def __init__(self, limit: int = 4096):
        self._limit = limit
        self._outcomes: OrderedDict[DeliveryKey, asyncio.Future[bool]] = OrderedDict()

    @contextlib.asynccontextmanager
    async def admit(self, key: DeliveryKey | None) -> typing.AsyncIterator[InboundDelivery | None]:
        """Yield the delivery to process, or None for a copy of an accepted one.

        A copy arriving while the first delivery is still pending waits for its
        outcome and takes over when that delivery failed or was cancelled, so a
        platform retry is never discarded in favour of a lost attempt.
        """
        if key is None:
            yield InboundDelivery(None)
            return
        while (pending := self._outcomes.get(key)) is not None:
            if await asyncio.shield(pending):
                yield None
                return
        outcome = asyncio.get_running_loop().create_future()
        self._outcomes[key] = outcome
        while len(self._outcomes) > self._limit:
            self._outcomes.popitem(last=False)
        try:
            yield InboundDelivery(outcome)
        finally:
            if not outcome.done():
                if self._outcomes.get(key) is outcome:
                    del self._outcomes[key]
                outcome.set_result(False)
