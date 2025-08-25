from __future__ import annotations
import abc
import typing

from ...core import app
import langbot_plugin.api.entities.builtin.pipeline.query as pipeline_query


preregistered_algos: list[typing.Type[ReteLimitAlgo]] = []


def algo_class(name: str):
    def decorator(cls: typing.Type[ReteLimitAlgo]) -> typing.Type[ReteLimitAlgo]:
        cls.name = name
        preregistered_algos.append(cls)
        return cls

    return decorator


class ReteLimitAlgo(metaclass=abc.ABCMeta):
    """限流算法抽象类"""

    name: str = None

    ap: app.Application

    def __init__(self, ap: app.Application):
        self.ap = ap

    async def initialize(self):
        pass

    @abc.abstractmethod
    async def require_access(
        self,
        query: pipeline_query.Query,
        launcher_type: str,
        launcher_id: typing.Union[int, str],
    ) -> bool:
        """进入处理流程

        这个方法对等待是友好的，意味着算法可以实现在这里等待一段时间以控制速率。

        Args:
            launcher_type (str): 请求者类型 群聊为 group 私聊为 person
            launcher_id (int): 请求者ID

        Returns:
            bool: 是否允许进入处理流程，若返回false，则直接丢弃该请求
        """
        raise NotImplementedError

    @abc.abstractmethod
    async def release_access(
        self,
        query: pipeline_query.Query,
        launcher_type: str,
        launcher_id: typing.Union[int, str],
    ):
        """退出处理流程

        Args:
            launcher_type (str): 请求者类型 群聊为 group 私聊为 person
            launcher_id (int): 请求者ID
        """

        raise NotImplementedError
