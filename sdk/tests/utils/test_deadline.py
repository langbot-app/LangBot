from __future__ import annotations

import asyncio
import time

import pytest

from langbot_plugin.utils import deadline


async def _empty_generator():
    if False:
        yield None


@pytest.mark.anyio
async def test_anext_with_deadline_preserves_natural_exhaustion_after_deadline(
    monkeypatch,
):
    """A naturally exhausted generator must not be reported as a timeout."""
    now = time.time()
    ticks = iter([now, now + 2])
    monkeypatch.setattr(deadline.time, "time", lambda: next(ticks, now + 2))

    with pytest.raises(StopAsyncIteration):
        await deadline.anext_with_deadline(_empty_generator(), now + 1)


@pytest.mark.anyio
async def test_anext_with_deadline_observes_extension_while_waiting():
    state = {"deadline_at": time.time() + 0.03}

    async def delayed_result():
        await asyncio.sleep(0.07)
        yield "submitted"

    async def extend():
        await asyncio.sleep(0.01)
        state["deadline_at"] += 0.1

    extension = asyncio.create_task(extend())
    try:
        assert (
            await deadline.anext_with_deadline(
                delayed_result(), lambda: state["deadline_at"]
            )
            == "submitted"
        )
    finally:
        await extension
