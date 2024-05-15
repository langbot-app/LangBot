from __future__ import annotations

import typing
import abc

from ..core import app


preregistered_services: list[typing.Type[OSSService]] = []

def service_class(
    name: str
) -> typing.Callable[[typing.Type[OSSService]], typing.Type[OSSService]]:
    """OSS服务类装饰器

    Args:
        name (str): 服务名称

    Returns:
        typing.Callable[[typing.Type[OSSService]], typing.Type[OSSService]]: 装饰器
    """
    def decorator(cls: typing.Type[OSSService]) -> typing.Type[OSSService]:
        assert issubclass(cls, OSSService)

        cls.name = name

        preregistered_services.append(cls)

        return cls

    return decorator


class OSSService(metaclass=abc.ABCMeta):
    """OSS抽象类"""

    name: str

    ap: app.Application

    cfg: dict

    def __init__(self, ap: app.Application, cfg: dict) -> None:
        self.ap = ap
        self.cfg = cfg

    async def initialize(self):
        pass

    @abc.abstractmethod
    async def upload(
        self,
        local_file: str=None,
        file_bytes: bytes=None,
        ext: str=None,
    ) -> str:
        """上传文件

        Args:
            local_file (str, optional): 本地文件路径. Defaults to None.
            file_bytes (bytes, optional): 文件字节. Defaults to None.
            ext (str, optional): 文件扩展名. Defaults to None.

        Returns:
            str: 文件URL
        """
        pass
