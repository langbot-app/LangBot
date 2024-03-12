from __future__ import annotations
import abc
import typing

from ...core import app


preregistered_algos: list[typing.Type[ReteLimitAlgo]] = []

def algo_class(name: str):
    
    def decorator(cls: typing.Type[ReteLimitAlgo]) -> typing.Type[ReteLimitAlgo]:
        cls.name = name
        preregistered_algos.append(cls)
        return cls
    
    return decorator


class ReteLimitAlgo(metaclass=abc.ABCMeta):
    
    name: str = None

    ap: app.Application

    def __init__(self, ap: app.Application):
        self.ap = ap

    async def initialize(self):
        pass

    @abc.abstractmethod
    async def require_access(self, launcher_type: str, launcher_id: int) -> bool:
        raise NotImplementedError
    
    @abc.abstractmethod
    async def release_access(self, launcher_type: str, launcher_id: int):
        raise NotImplementedError
 