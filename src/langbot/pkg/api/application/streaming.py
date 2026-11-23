"""Bounded streaming that keeps producer authorization scopes out of the consumer."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from contextlib import aclosing, suppress
from typing import TypeVar

T = TypeVar('T')


async def isolated_stream(source: AsyncIterator[T]) -> AsyncIterator[T]:
    queue: asyncio.Queue[tuple[bool, T | Exception | None]] = asyncio.Queue(maxsize=1)

    async def produce():
        try:
            async with aclosing(source):
                async for item in source:
                    await queue.put((True, item))
        except Exception as exc:
            await queue.put((False, exc))
        else:
            await queue.put((False, None))

    producer = asyncio.create_task(produce())
    try:
        while True:
            receive = asyncio.create_task(queue.get())
            try:
                done, _ = await asyncio.wait({receive, producer}, return_when=asyncio.FIRST_COMPLETED)
                if receive not in done and queue.empty():
                    # Cancellation inside a provider must also wake the consumer.
                    await producer
                available, value = await receive
            finally:
                receive.cancel()
                with suppress(asyncio.CancelledError):
                    await receive
            if available:
                yield value
            elif value is None:
                return
            else:
                raise value
    finally:
        producer.cancel()
        with suppress(asyncio.CancelledError):
            await producer
