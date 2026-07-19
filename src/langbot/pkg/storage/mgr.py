from __future__ import annotations

import hashlib
import json
import re
from pathlib import PurePath

from ..core import app
from ..api.http.authz import WorkspaceRequiredError
from ..api.http.context import ExecutionContext, RequestContext
from . import provider
from .providers import localstorage


_SAFE_OWNER_TYPE = re.compile(r'^[a-z][a-z0-9_-]{0,63}$')
_SCOPED_KEY = re.compile(
    r'^v1/(?P<instance>[a-f0-9]{24})/'
    r'(?P<workspace>[0-9a-fA-F-]{36})/'
    r'(?P<generation>[1-9][0-9]*)/'
    r'(?P<owner_type>[a-z][a-z0-9_-]{0,63})/'
    r'(?P<owner>[a-f0-9]{32})/'
    r'(?P<key>[a-f0-9]{64})(?P<suffix>\.[a-zA-Z0-9]{1,16})?$'
)


class StorageMgr:
    """Storage manager"""

    ap: app.Application

    storage_provider: provider.StorageProvider

    def __init__(self, ap: app.Application):
        self.ap = ap

    @staticmethod
    def _require_execution_scope(
        context: ExecutionContext | RequestContext,
    ) -> tuple[str, str, int]:
        if not isinstance(context, (ExecutionContext, RequestContext)):
            raise WorkspaceRequiredError('Storage operations require an explicit Workspace context')
        instance_uuid = context.instance_uuid.strip()
        workspace_uuid = context.workspace_uuid.strip()
        generation = context.placement_generation
        if not instance_uuid or not workspace_uuid:
            raise WorkspaceRequiredError('Storage operations require an instance and Workspace')
        if generation <= 0:
            raise WorkspaceRequiredError('Storage operations require a positive placement generation')
        return instance_uuid, workspace_uuid, generation

    @staticmethod
    def _digest(value: str, length: int) -> str:
        return hashlib.sha256(value.encode('utf-8')).hexdigest()[:length]

    async def _require_active_execution_scope(
        self,
        context: ExecutionContext | RequestContext,
    ) -> None:
        """Revalidate the captured generation before touching object storage."""
        instance_uuid, workspace_uuid, generation = self._require_execution_scope(context)
        workspace_service = getattr(self.ap, 'workspace_service', None)
        if workspace_service is None:
            raise WorkspaceRequiredError('Storage execution scope is unavailable')
        try:
            binding = await workspace_service.get_execution_binding(
                workspace_uuid,
                expected_generation=generation,
            )
        except Exception as exc:
            raise WorkspaceRequiredError('Storage execution scope is unavailable') from exc
        if (
            getattr(binding, 'instance_uuid', None) != instance_uuid
            or getattr(binding, 'workspace_uuid', None) != workspace_uuid
            or getattr(binding, 'placement_generation', None) != generation
        ):
            raise WorkspaceRequiredError('Storage execution scope is unavailable')

    @classmethod
    def canonical_binary_storage_key(
        cls,
        context: ExecutionContext | RequestContext,
        *,
        owner_type: str,
        owner: str,
        key: str,
    ) -> str:
        """Return a bounded canonical key over every BinaryStorage owner dimension."""

        instance_uuid, workspace_uuid, _ = cls._require_execution_scope(context)
        if not _SAFE_OWNER_TYPE.fullmatch(owner_type):
            raise ValueError('Invalid storage owner_type')
        if not owner or not key:
            raise ValueError('Storage owner and key are required')
        canonical = json.dumps(
            [instance_uuid, workspace_uuid, owner_type, owner, key],
            ensure_ascii=False,
            separators=(',', ':'),
        )
        return f'v1:{cls._digest(instance_uuid, 24)}:{workspace_uuid}:{owner_type}:{hashlib.sha256(canonical.encode()).hexdigest()}'

    @classmethod
    def scoped_object_key(
        cls,
        context: ExecutionContext | RequestContext,
        *,
        owner_type: str,
        owner: str,
        key: str,
        preserve_suffix: bool = True,
    ) -> str:
        """Build a non-enumerable object key with an explicit tenant boundary."""

        instance_uuid, workspace_uuid, generation = cls._require_execution_scope(context)
        if not _SAFE_OWNER_TYPE.fullmatch(owner_type):
            raise ValueError('Invalid storage owner_type')
        if not owner or not key:
            raise ValueError('Storage owner and key are required')
        suffix = PurePath(key).suffix.lower() if preserve_suffix else ''
        if not re.fullmatch(r'\.[a-z0-9]{1,16}', suffix):
            suffix = ''
        return (
            f'v1/{cls._digest(instance_uuid, 24)}/{workspace_uuid}/{generation}/'
            f'{owner_type}/{cls._digest(owner, 32)}/{cls._digest(key, 64)}{suffix}'
        )

    @classmethod
    def scoped_prefix(
        cls,
        context: ExecutionContext | RequestContext,
        *,
        owner_type: str | None = None,
    ) -> str:
        instance_uuid, workspace_uuid, generation = cls._require_execution_scope(context)
        prefix = f'v1/{cls._digest(instance_uuid, 24)}/{workspace_uuid}/{generation}/'
        if owner_type is not None:
            if not _SAFE_OWNER_TYPE.fullmatch(owner_type):
                raise ValueError('Invalid storage owner_type')
            prefix += f'{owner_type}/'
        return prefix

    async def save_scoped(
        self,
        context: ExecutionContext | RequestContext,
        *,
        owner_type: str,
        owner: str,
        key: str,
        value: bytes,
        preserve_suffix: bool = True,
    ) -> str:
        await self._require_active_execution_scope(context)
        object_key = self.scoped_object_key(
            context,
            owner_type=owner_type,
            owner=owner,
            key=key,
            preserve_suffix=preserve_suffix,
        )
        await self.storage_provider.save(object_key, value)
        return object_key

    async def load_scoped(
        self,
        context: ExecutionContext | RequestContext,
        *,
        owner_type: str,
        owner: str,
        key: str,
        preserve_suffix: bool = True,
    ) -> bytes:
        await self._require_active_execution_scope(context)
        object_key = self.scoped_object_key(
            context,
            owner_type=owner_type,
            owner=owner,
            key=key,
            preserve_suffix=preserve_suffix,
        )
        return await self.storage_provider.load(object_key)

    async def delete_scoped(
        self,
        context: ExecutionContext | RequestContext,
        *,
        owner_type: str,
        owner: str,
        key: str,
        preserve_suffix: bool = True,
    ) -> None:
        await self._require_active_execution_scope(context)
        object_key = self.scoped_object_key(
            context,
            owner_type=owner_type,
            owner=owner,
            key=key,
            preserve_suffix=preserve_suffix,
        )
        await self.storage_provider.delete(object_key)

    async def resolve_public_object(
        self,
        object_key: str,
        *,
        expected_owner_type: str,
    ) -> bytes | None:
        """Load an opaque public object after validating its trusted scope."""

        match = _SCOPED_KEY.fullmatch(object_key)
        if match is None or match.group('owner_type') != expected_owner_type:
            return None
        if match.group('instance') != self._digest(self.ap.workspace_service.instance_uuid, 24):
            return None
        workspace_uuid = match.group('workspace')
        generation = int(match.group('generation'))
        try:
            await self.ap.workspace_service.get_execution_binding(
                workspace_uuid,
                expected_generation=generation,
            )
        except Exception:
            return None
        if not await self.storage_provider.exists(object_key):
            return None
        return await self.storage_provider.load(object_key)

    @classmethod
    def require_scoped_object_key(
        cls,
        context: ExecutionContext | RequestContext,
        object_key: str,
        *,
        expected_owner_type: str,
    ) -> None:
        """Validate an opaque object key against every captured scope field."""

        instance_uuid, workspace_uuid, generation = cls._require_execution_scope(context)
        match = _SCOPED_KEY.fullmatch(object_key)
        if (
            match is None
            or match.group('instance') != cls._digest(instance_uuid, 24)
            or match.group('workspace') != workspace_uuid
            or int(match.group('generation')) != generation
            or match.group('owner_type') != expected_owner_type
        ):
            raise WorkspaceRequiredError('Object key does not belong to the execution scope')

    async def exists_scoped_object_key(
        self,
        context: ExecutionContext | RequestContext,
        object_key: str,
        *,
        expected_owner_type: str,
    ) -> bool:
        await self._require_active_execution_scope(context)
        self.require_scoped_object_key(
            context,
            object_key,
            expected_owner_type=expected_owner_type,
        )
        return await self.storage_provider.exists(object_key)

    async def load_scoped_object_key(
        self,
        context: ExecutionContext | RequestContext,
        object_key: str,
        *,
        expected_owner_type: str,
    ) -> bytes:
        await self._require_active_execution_scope(context)
        self.require_scoped_object_key(
            context,
            object_key,
            expected_owner_type=expected_owner_type,
        )
        return await self.storage_provider.load(object_key)

    async def size_scoped_object_key(
        self,
        context: ExecutionContext | RequestContext,
        object_key: str,
        *,
        expected_owner_type: str,
    ) -> int:
        await self._require_active_execution_scope(context)
        self.require_scoped_object_key(
            context,
            object_key,
            expected_owner_type=expected_owner_type,
        )
        return await self.storage_provider.size(object_key)

    async def delete_scoped_object_key(
        self,
        context: ExecutionContext | RequestContext,
        object_key: str,
        *,
        expected_owner_type: str,
    ) -> None:
        """Delete a previously returned key only inside the captured scope."""

        await self._require_active_execution_scope(context)
        self.require_scoped_object_key(
            context,
            object_key,
            expected_owner_type=expected_owner_type,
        )
        if await self.storage_provider.exists(object_key):
            await self.storage_provider.delete(object_key)

    @classmethod
    def is_scoped_object_key(
        cls,
        object_key: str,
        *,
        expected_owner_type: str | None = None,
    ) -> bool:
        match = _SCOPED_KEY.fullmatch(object_key)
        return match is not None and (expected_owner_type is None or match.group('owner_type') == expected_owner_type)

    async def initialize(self):
        storage_config = self.ap.instance_config.data.get('storage', {})
        storage_type = storage_config.get('use', 'local')

        if storage_type == 's3':
            from .providers import s3storage

            self.storage_provider = s3storage.S3StorageProvider(self.ap)
            self.ap.logger.info('Initialized S3 storage backend.')
        else:
            self.storage_provider = localstorage.LocalStorageProvider(self.ap)
            self.ap.logger.info('Initialized local storage backend.')

        await self.storage_provider.initialize()
