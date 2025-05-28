from __future__ import annotations


from ..core import app
from . import provider
from .providers import localstorage


class StorageMgr:
    """存储管理器"""

    ap: app.Application

    storage_provider: provider.StorageProvider

    def __init__(self, ap: app.Application):
        self.ap = ap
        self.storage_provider = localstorage.LocalStorageProvider(ap)

    async def initialize(self):
        await self.storage_provider.initialize()
