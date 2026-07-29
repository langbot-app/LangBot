from __future__ import annotations

import abc
import asyncio
import typing
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..core import app
    import langbot_plugin.api.entities.builtin.pipeline.query as pipeline_query
    import langbot_plugin.api.entities.builtin.provider.message as provider_message


preregistered_runners: list[typing.Type[RequestRunner]] = []
_DEFAULT_SYNC_ITERATION_LIMIT = 100_000

_T = typing.TypeVar('_T')


def _next_sync(iterator: typing.Iterator[_T]) -> tuple[bool, _T | None]:
    try:
        return True, next(iterator)
    except StopIteration:
        return False, None


async def iterate_sync(
    iterable: typing.Iterable[_T],
    *,
    max_items: int = _DEFAULT_SYNC_ITERATION_LIMIT,
) -> typing.AsyncGenerator[_T, None]:
    """Consume a blocking SDK iterator without stalling the event loop."""

    iterator = iter(iterable)
    for _ in range(max(max_items, 1)):
        has_item, item = await asyncio.to_thread(_next_sync, iterator)
        if not has_item:
            return
        yield typing.cast(_T, item)
    raise RuntimeError('Synchronous provider stream exceeded the event limit')


def runner_class(name: str):
    """注册一个请求运行器"""

    def decorator(cls: typing.Type[RequestRunner]) -> typing.Type[RequestRunner]:
        cls.name = name
        preregistered_runners.append(cls)
        return cls

    return decorator


class RequestRunner(abc.ABC):
    """请求运行器"""

    name: str = None

    ap: app.Application

    pipeline_config: dict

    def __init__(self, ap: app.Application, pipeline_config: dict):
        self.ap = ap
        self.pipeline_config = pipeline_config

    @abc.abstractmethod
    async def run(
        self, query: pipeline_query.Query
    ) -> typing.AsyncGenerator[provider_message.Message | provider_message.MessageChunk, None]:
        """运行请求"""
        pass

    async def aclose(self) -> None:
        """Release request-scoped resources after one runner invocation."""
