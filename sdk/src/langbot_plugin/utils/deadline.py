from __future__ import annotations

import asyncio
import time
from typing import Any, AsyncGenerator, Callable, TypeVar

_T = TypeVar("_T")


def remaining_deadline_seconds(deadline_at: Any) -> float | None:
    """Return seconds until a Unix deadline timestamp, or None if absent/invalid."""
    if deadline_at is None:
        return None
    try:
        return float(deadline_at) - time.time()
    except (TypeError, ValueError):
        return None


async def anext_with_deadline(
    gen: AsyncGenerator[_T, None],
    deadline_at: Any | Callable[[], Any],
) -> _T:
    """Return the next item from an async generator before the deadline expires."""
    current_deadline = deadline_at if callable(deadline_at) else lambda: deadline_at
    remaining = remaining_deadline_seconds(current_deadline())
    if remaining is not None and remaining <= 0:
        await gen.aclose()
        raise asyncio.TimeoutError

    next_result = asyncio.create_task(anext(gen))
    try:
        while True:
            try:
                if remaining is None:
                    return await next_result
                return await asyncio.wait_for(
                    asyncio.shield(next_result), timeout=max(remaining, 0)
                )
            except asyncio.TimeoutError:
                remaining = remaining_deadline_seconds(current_deadline())
                if next_result.done() or (remaining is not None and remaining <= 0):
                    raise
    except asyncio.TimeoutError:
        next_result.cancel()
        await asyncio.gather(next_result, return_exceptions=True)
        await gen.aclose()
        raise
    finally:
        if not next_result.done():
            next_result.cancel()
            await asyncio.gather(next_result, return_exceptions=True)
