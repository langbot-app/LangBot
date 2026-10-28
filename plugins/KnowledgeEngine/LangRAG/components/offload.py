"""Bound CPU/file parsing work per installation, including cancelled callers."""
import asyncio
import contextvars
from components.shared_state import settle


class BoundedOffload:
    def __init__(self, concurrency=2):
        self._slots = asyncio.Semaphore(concurrency)

    async def run(self, function, *args, **kwargs):
        async with self._slots:
            # A worker cannot be interrupted. Run with an empty context so it
            # never inherits the invocation's revocable tenant capability.
            # Settle before releasing the slot; discard the result on cancel.
            worker_context = contextvars.Context()
            task = asyncio.create_task(
                asyncio.to_thread(worker_context.run, function, *args, **kwargs)
            )
            return await settle(task)
