from __future__ import annotations

import abc
import typing

from ..core import app


preregistered_runners: list[typing.Type[RequestRunner]] = []


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
        self, query: core_entities.Query
    ) -> typing.AsyncGenerator[llm_entities.Message | llm_entities.MessageChunk, None]:
        """运行请求"""
        pass
