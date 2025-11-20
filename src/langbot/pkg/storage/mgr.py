from __future__ import annotations


from ..core import app
from . import provider
from .providers import localstorage, s3storage


class StorageMgr:
    """Storage manager"""

    ap: app.Application

    storage_provider: provider.StorageProvider

    def __init__(self, ap: app.Application):
        self.ap = ap

    async def initialize(self):
        storage_config = self.ap.instance_config.data.get('storage', {})
        storage_type = storage_config.get('use', 'local')

        if storage_type == 's3':
            self.storage_provider = s3storage.S3StorageProvider(self.ap)
            self.ap.logger.info('Initialized S3 storage backend.')
        else:
            self.storage_provider = localstorage.LocalStorageProvider(self.ap)
            self.ap.logger.info('Initialized local storage backend.')

        await self.storage_provider.initialize()
