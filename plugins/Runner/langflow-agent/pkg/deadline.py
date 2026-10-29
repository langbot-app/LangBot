"""Total deadlines without retaining a cancellation scope across a yield."""

import asyncio
import functools
import inspect
import math
from contextlib import aclosing


def deadline(method):
    signature = inspect.signature(method)

    def seconds(args, kwargs):
        bound = signature.bind(*args, **kwargs)
        bound.apply_defaults()
        value = float(bound.arguments.get("timeout", getattr(args[0], "timeout", 120)))
        if not math.isfinite(value) or value <= 0 or value > 3600:
            raise ValueError("timeout must be finite and in (0, 3600]")
        return value

    if inspect.isasyncgenfunction(method):

        @functools.wraps(method)
        async def stream(*args, **kwargs):
            end = asyncio.get_running_loop().time() + seconds(args, kwargs)
            async with aclosing(method(*args, **kwargs)) as source:
                while True:
                    remaining = end - asyncio.get_running_loop().time()
                    if remaining <= 0:
                        raise TimeoutError("Provider total deadline exceeded")
                    try:
                        # Same task: preserve SDK invocation context, and cancel
                        # only while the provider owns control, never its consumer.
                        async with asyncio.timeout(remaining):
                            item = await anext(source)
                    except StopAsyncIteration:
                        return
                    yield item

        return stream

    @functools.wraps(method)
    async def call(*args, **kwargs):
        async with asyncio.timeout(seconds(args, kwargs)):
            return await method(*args, **kwargs)

    return call
