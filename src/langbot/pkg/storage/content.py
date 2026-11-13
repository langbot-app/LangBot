"""Tenant-scoped immutable bytes with durable database or named S3 locators."""

from __future__ import annotations

import asyncio
import hashlib
import json
import re
from types import SimpleNamespace

import sqlalchemy as sa

from ..entity.persistence.content import ContentAlias, ContentObject
from ..persistence.tenant_uow import PersistenceScopeKind, TenantScopeRequiredError
from .provider import HARD_MAX_STORAGE_OBJECT_BYTES, normalize_read_limit
from .providers.s3storage import S3StorageProvider


class ContentStore:
    def __init__(self, ap):
        self.ap = ap
        self._providers = {}
        self._provider_lock = asyncio.Lock()
        self._cleanup_tasks = set()

    def _delete_after_transaction(self, provider, key, *, committed):
        gate = self.ap.persistence_mgr.create_after_commit_gate()
        if gate is None:
            raise RuntimeError('Content cleanup requires an active transaction')

        def completed(future):
            if (not future.cancelled()) != committed:
                return

            async def cleanup():
                try:
                    await provider.delete(key)
                except Exception:
                    self.ap.logger.exception('Failed to remove unreferenced content object')

            task = asyncio.create_task(cleanup())
            self._cleanup_tasks.add(task)
            task.add_done_callback(self._cleanup_tasks.discard)

        gate.add_done_callback(completed)

    def _config(self):
        return self.ap.instance_config.data.get('storage', {}).get('content', {}) or {}

    @staticmethod
    async def _save_complete(provider, key, value):
        operation = asyncio.create_task(provider.save(key, value))
        try:
            await asyncio.shield(operation)
        except asyncio.CancelledError:
            # A boto thread may still be writing; rollback deletion must run after it ends.
            while not operation.done():
                try:
                    await asyncio.shield(operation)
                except asyncio.CancelledError:
                    continue
                except Exception:
                    break
            if not operation.cancelled():
                operation.exception()
            raise

    async def _validate(self, context):
        from .mgr import StorageMgr

        await StorageMgr._require_active_execution_scope(self, context)

    # Reuse the existing trusted scope validation without weakening its types.
    @staticmethod
    def _require_execution_scope(context):
        from .mgr import StorageMgr

        return StorageMgr._require_execution_scope(context)

    async def _s3(self, name, locator=None):
        config = (self._config().get('backends') or {}).get(name)
        if not isinstance(config, dict) or config.get('type', 's3') != 's3':
            raise ValueError(f'Content backend {name!r} is not configured')
        identity = {
            'endpoint_url': config.get('endpoint_url', '').rstrip('/'),
            'bucket': config.get('bucket', 'langbot-storage'),
            'region': config.get('region', 'us-east-1'),
        }
        if locator is not None and any(locator.get(key) != value for key, value in identity.items()):
            raise ValueError('Historical content backend location has changed')
        async with self._provider_lock:
            if name not in self._providers:
                proxy = SimpleNamespace(
                    instance_config=SimpleNamespace(data={'storage': {'s3': config}}), logger=self.ap.logger
                )
                provider = S3StorageProvider(proxy)
                await provider.initialize()
                self._providers[name] = (provider, identity)
            provider, initialized_identity = self._providers[name]
            if identity != initialized_identity:
                raise ValueError('A named content backend cannot change location while running')
            return provider, identity

    async def put(self, context, *, owner_type, owner, key, value):
        await self._validate(context)
        async with self.ap.persistence_mgr.tenant_uow(context.workspace_uuid) as uow:
            return await self._put(uow, context.workspace_uuid, owner_type, owner, key, value)

    async def _put(self, uow, workspace, owner_type, owner, key, value, *, public_key=None):
        if not isinstance(value, bytes) or len(value) > HARD_MAX_STORAGE_OBJECT_BYTES:
            raise ValueError('Content must be bytes within the storage size limit')
        if not isinstance(owner_type, str) or not re.fullmatch(r'[a-z][a-z0-9_-]{0,63}', owner_type):
            raise ValueError('Invalid content owner type')
        if not isinstance(owner, str) or not owner or len(owner) > 255 or not isinstance(key, str) or not key:
            raise ValueError('Content owner and key are required')
        digest = hashlib.sha256(value).hexdigest()
        identity = json.dumps([workspace, owner_type, owner, key, digest, public_key], separators=(',', ':'))
        ref = 'ct1_' + hashlib.sha256(identity.encode()).hexdigest()
        existing = (
            await uow.execute(
                sa.select(ContentObject.ref).where(ContentObject.workspace_uuid == workspace, ContentObject.ref == ref)
            )
        ).scalar_one_or_none()
        if existing is not None:
            return ref
        backend = self._config().get('backend', 'database')
        locator = None
        if backend != 'database':
            provider, location = await self._s3(backend)
            # Unique publication keys cannot overwrite objects referenced by a committed version.
            import uuid

            # shortcut: process crashes can leave UUID uploads; reclaim only aged keys absent from committed locators.
            object_key = f'content/{workspace}/{uuid.uuid4().hex}'
            self._delete_after_transaction(provider, object_key, committed=False)
            await self._save_complete(provider, object_key, value)
            locator = {**location, 'key': object_key}
        values = dict(
            ref=ref,
            workspace_uuid=workspace,
            public_media=public_key is not None,
            public_key=public_key,
            owner_type=owner_type,
            owner=owner,
            key=key,
            digest=digest,
            size=len(value),
            backend=backend,
            locator=locator,
            value=value if backend == 'database' else None,
        )
        # The same immutable bytes may be published concurrently by two Core instances.
        dialect = self.ap.persistence_mgr.get_db_engine().dialect.name
        if dialect == 'postgresql':
            from sqlalchemy.dialects.postgresql import insert
        elif dialect == 'sqlite':
            from sqlalchemy.dialects.sqlite import insert
        else:
            raise ValueError('Persistent content requires PostgreSQL or SQLite')
        inserted = await uow.execute(
            insert(ContentObject).values(**values).on_conflict_do_nothing(index_elements=['ref'])
        )
        if locator is not None and inserted.rowcount == 0:
            self._delete_after_transaction(provider, object_key, committed=True)
        return ref

    async def _row(self, uow, workspace, ref):
        if not isinstance(ref, str) or not re.fullmatch(r'ct1_[0-9a-f]{64}', ref):
            raise FileNotFoundError('Unknown content reference')
        row = (
            (
                await uow.execute(
                    sa.select(ContentObject.__table__).where(
                        ContentObject.workspace_uuid == workspace, ContentObject.ref == ref
                    )
                )
            )
            .mappings()
            .first()
        )
        if row is None:
            raise FileNotFoundError('Unknown content reference')
        return row

    async def _read(self, row, max_bytes):
        limit = normalize_read_limit(max_bytes)
        if row['size'] > limit:
            raise ValueError('Content exceeds the read size limit')
        if row['backend'] == 'database':
            value = bytes(row['value'])
        else:
            provider, _ = await self._s3(row['backend'], row['locator'])
            value = await provider.load_bounded(row['locator']['key'], max_bytes=limit)
        if len(value) != row['size'] or hashlib.sha256(value).hexdigest() != row['digest']:
            raise ValueError('Persisted content failed digest verification')
        return value

    async def get(self, context, ref, *, max_bytes=HARD_MAX_STORAGE_OBJECT_BYTES):
        await self._validate(context)
        async with self.ap.persistence_mgr.tenant_uow(context.workspace_uuid) as uow:
            row = await self._row(uow, context.workspace_uuid, ref)
            return await self._read(row, max_bytes)

    async def size(self, context, ref):
        await self._validate(context)
        async with self.ap.persistence_mgr.tenant_uow(context.workspace_uuid) as uow:
            return (await self._row(uow, context.workspace_uuid, ref))['size']

    async def delete(self, context, ref):
        """Remove an unreferenced object; callers must release their business references first."""
        await self._validate(context)
        async with self.ap.persistence_mgr.tenant_uow(context.workspace_uuid) as uow:
            row = await self._row(uow, context.workspace_uuid, ref)
            await uow.execute(
                sa.delete(ContentObject).where(
                    ContentObject.workspace_uuid == context.workspace_uuid, ContentObject.ref == ref
                )
            )
            if row['backend'] != 'database':
                provider, _ = await self._s3(row['backend'], row['locator'])
                self._delete_after_transaction(provider, row['locator']['key'], committed=True)

    async def save_alias(self, context, object_key, *, owner_type, owner, value):
        await self._validate(context)
        async with self.ap.persistence_mgr.tenant_uow(context.workspace_uuid) as uow:
            ref = await self._put(uow, context.workspace_uuid, owner_type, owner, object_key, value)
            dialect = self.ap.persistence_mgr.get_db_engine().dialect.name
            if dialect == 'postgresql':
                from sqlalchemy.dialects.postgresql import insert
            elif dialect == 'sqlite':
                from sqlalchemy.dialects.sqlite import insert
            else:
                raise ValueError('Persistent content requires PostgreSQL or SQLite')
            await uow.execute(
                insert(ContentAlias)
                .values(workspace_uuid=context.workspace_uuid, key=object_key, content_ref=ref)
                .on_conflict_do_update(index_elements=['workspace_uuid', 'key'], set_={'content_ref': ref})
            )

    async def alias_ref(self, context, object_key):
        await self._validate(context)
        async with self.ap.persistence_mgr.tenant_uow(context.workspace_uuid) as uow:
            return (
                await uow.execute(
                    sa.select(ContentAlias.content_ref).where(
                        ContentAlias.workspace_uuid == context.workspace_uuid, ContentAlias.key == object_key
                    )
                )
            ).scalar_one_or_none()

    async def delete_alias(self, context, object_key):
        await self._validate(context)
        async with self.ap.persistence_mgr.tenant_uow(context.workspace_uuid) as uow:
            await uow.execute(
                sa.delete(ContentAlias).where(
                    ContentAlias.workspace_uuid == context.workspace_uuid, ContentAlias.key == object_key
                )
            )

    async def save_public_media(self, key, value):
        self._media_key(key)
        scope = self.ap.persistence_mgr.current_scope()
        if scope is None or scope.kind != PersistenceScopeKind.WORKSPACE:
            raise TenantScopeRequiredError('Publishing media requires a trusted Workspace scope')
        workspace = dict(scope.settings)['langbot.workspace_uuid']
        async with self.ap.persistence_mgr.tenant_uow(workspace) as uow:
            return await self._put(uow, workspace, 'public_media', key, key, value, public_key=key)

    @staticmethod
    def _media_key(key):
        if not isinstance(key, str) or not re.fullmatch(r'media_cache/[a-f0-9]{32,64}(?:\.[a-zA-Z0-9]{1,10})?', key):
            raise ValueError('Invalid public media key')

    async def get_public_media(self, key, *, max_bytes=HARD_MAX_STORAGE_OBJECT_BYTES):
        self._media_key(key)
        async with self.ap.persistence_mgr.public_media_uow(key) as uow:
            row = (
                (
                    await uow.execute(
                        sa.select(ContentObject.__table__)
                        .where(ContentObject.public_media.is_(True), ContentObject.public_key == key)
                        .limit(1)
                    )
                )
                .mappings()
                .first()
            )
            return None if row is None else await self._read(row, max_bytes)

    async def shutdown(self):
        # Let transaction completion callbacks enqueue cleanup before closing their clients.
        await asyncio.sleep(0)
        if self._cleanup_tasks:
            await asyncio.gather(*self._cleanup_tasks)
        for provider, _ in self._providers.values():
            await provider.shutdown()
        self._providers.clear()
