from __future__ import annotations

import abc

from ..core import app


class StorageProvider(abc.ABC):
    ap: app.Application

    def __init__(self, ap: app.Application):
        self.ap = ap

    async def initialize(self):
        pass

    @abc.abstractmethod
    async def save(
        self,
        key: str,
        value: bytes,
    ):
        pass

    @abc.abstractmethod
    async def load(
        self,
        key: str,
    ) -> bytes:
        pass

    @abc.abstractmethod
    async def exists(
        self,
        key: str,
    ) -> bool:
        pass

    @abc.abstractmethod
    async def delete(
        self,
        key: str,
    ):
        pass

    @abc.abstractmethod
    async def delete_dir_recursive(
        self,
        dir_path: str,
    ):
        pass
