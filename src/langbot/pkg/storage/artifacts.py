"""Authorized assets over ContentStore, independent of execution caches."""

from __future__ import annotations

import datetime as dt
import hashlib
import re
import uuid

import sqlalchemy as sa

from ..api.authz import Permission, require_permission
from ..api.context import ExecutionContext, PrincipalType, RequestContext
from ..entity.persistence.artifact import Artifact, ArtifactReference
from ..entity.persistence.content import ContentObject

MAX_ARTIFACT_BYTES = 10 * 1024 * 1024
DEFAULT_TTL_SECONDS = 86400
MAX_TTL_SECONDS = 7 * DEFAULT_TTL_SECONDS


class ArtifactError(Exception):
    def __init__(self, error_code: str, message: str, status_code: int):
        super().__init__(message)
        self.error_code = error_code
        self.status_code = status_code


def _now():
    return dt.datetime.now(dt.timezone.utc).replace(tzinfo=None)


class ArtifactService:
    def __init__(self, ap):
        self.ap = ap

    @property
    def content(self):
        return self.ap.storage_mgr.content_store

    async def _authorize(self, context, *, write=False):
        if not isinstance(context, RequestContext):
            raise ArtifactError(
                'artifact_principal_not_supported', 'Artifact operations require an account or API key', 403
            )
        principal = context.principal
        owner_id = None
        if principal.principal_type == PrincipalType.ACCOUNT:
            owner_id = principal.account_uuid
        elif principal.principal_type == PrincipalType.API_KEY:
            owner_id = principal.api_key_uuid
        if not owner_id:
            raise ArtifactError(
                'artifact_principal_not_supported', 'Artifact operations require an account or API key', 403
            )
        require_permission(context, Permission.RESOURCE_MANAGE if write else Permission.RESOURCE_VIEW)
        await self.content._validate(context)
        return principal.principal_type.value, owner_id

    @staticmethod
    def _scope(context, artifact_id):
        if not isinstance(artifact_id, str) or not re.fullmatch(r'art_[a-f0-9]{32}', artifact_id):
            raise FileNotFoundError('Resource not found')
        return Artifact.workspace_uuid == context.workspace_uuid, Artifact.id == artifact_id

    async def _row(self, uow, context, artifact_id, owner=None, *, lock=False, live=True):
        conditions = self._scope(context, artifact_id)
        if owner is not None:
            conditions += (Artifact.owner_type == owner[0], Artifact.owner_id == owner[1])
        if lock:
            # Also reserves SQLite's writer before reading; FOR UPDATE alone is ignored there.
            await uow.execute(sa.update(Artifact).where(*conditions).values(id=Artifact.id))
        row = (await uow.execute(sa.select(Artifact.__table__).where(*conditions))).mappings().first()
        if row is None or (live and row['deleted_at'] is not None):
            raise FileNotFoundError('Resource not found')
        if live and row['expires_at'] is not None and row['expires_at'] <= _now():
            raise ArtifactError('artifact_expired', 'Artifact has expired', 410)
        return row

    @staticmethod
    def _public(row):
        def timestamp(value):
            return value.replace(tzinfo=dt.timezone.utc).isoformat() if value is not None else None

        return {
            'id': row['id'],
            'name': row['name'],
            'mime_type': row['mime_type'],
            'size': row['size'],
            'digest': row['digest'],
            'source': 'input_attachment' if row['owner_type'] == 'run' else 'upload',
            'lifecycle': 'persistent' if row['expires_at'] is None else 'temporary',
            'created_at': timestamp(row['created_at']),
            'expires_at': timestamp(row['expires_at']),
        }

    async def create(
        self,
        context,
        filename: str,
        content: bytes,
        mime_type: str = 'application/octet-stream',
        ttl_seconds: int = DEFAULT_TTL_SECONDS,
    ) -> dict:
        owner = await self._authorize(context, write=True)
        return await self._create_owned(context, owner, filename, content, mime_type, ttl_seconds)

    @staticmethod
    def _run_owner(context):
        principal = context.trigger_principal if isinstance(context, ExecutionContext) else None
        if principal is None or principal.principal_type != PrincipalType.PROCESSOR or not principal.run_id:
            raise PermissionError('Input assets require a trusted active run context')
        return 'run', principal.run_id

    async def create_run_input(self, context, filename, content, mime_type):
        owner = self._run_owner(context)
        await self.content._validate(context)
        return await self._create_owned(context, owner, filename, content, mime_type, DEFAULT_TTL_SECONDS)

    async def read_run_input(self, context, artifact_id, *, max_bytes=MAX_ARTIFACT_BYTES):
        owner = self._run_owner(context)
        await self.content._validate(context)
        return await self._read_owned(context, owner, artifact_id, max_bytes)

    async def _create_owned(self, context, owner, filename, content, mime_type, ttl_seconds):
        if (
            not isinstance(filename, str)
            or not filename
            or len(filename) > 255
            or filename in {'.', '..'}
            or any(c in filename for c in '/\\')
            or any(ord(c) < 32 or ord(c) == 127 for c in filename)
        ):
            raise ValueError('Invalid artifact filename')
        if (
            not isinstance(mime_type, str)
            or len(mime_type) > 255
            or not re.fullmatch(r'[A-Za-z0-9!#$&^_.+-]+/[A-Za-z0-9!#$&^_.+-]+', mime_type)
        ):
            raise ValueError('Invalid artifact MIME type')
        if not isinstance(content, bytes):
            raise ValueError('Artifact content must be bytes')
        if len(content) > MAX_ARTIFACT_BYTES:
            raise ArtifactError('artifact_too_large', 'Artifact exceeds the size limit.', 413)
        if type(ttl_seconds) is not int or not 1 <= ttl_seconds <= MAX_TTL_SECONDS:
            raise ValueError('Artifact TTL must be between 1 and 604800 seconds')
        artifact_id = 'art_' + uuid.uuid4().hex
        async with self.ap.persistence_mgr.tenant_uow(context.workspace_uuid) as uow:
            content_ref = await self.content.put(
                context, owner_type='artifact', owner=artifact_id, key=artifact_id, value=content
            )
            await uow.execute(
                sa.insert(Artifact).values(
                    id=artifact_id,
                    workspace_uuid=context.workspace_uuid,
                    owner_type=owner[0],
                    owner_id=owner[1],
                    name=filename,
                    mime_type=mime_type,
                    size=len(content),
                    digest=hashlib.sha256(content).hexdigest(),
                    content_ref=content_ref,
                    expires_at=_now() + dt.timedelta(seconds=ttl_seconds),
                )
            )
            return self._public(await self._row(uow, context, artifact_id, owner))

    async def get(self, context, artifact_id: str) -> dict:
        owner = await self._authorize(context)
        async with self.ap.persistence_mgr.tenant_uow(context.workspace_uuid) as uow:
            return self._public(await self._row(uow, context, artifact_id, owner))

    async def read(self, context, artifact_id: str, max_bytes: int = MAX_ARTIFACT_BYTES) -> dict:
        owner = await self._authorize(context)
        return await self._read_owned(context, owner, artifact_id, max_bytes)

    async def _read_owned(self, context, owner, artifact_id, max_bytes):
        from .content import ContentIntegrityError

        if type(max_bytes) is not int or not 1 <= max_bytes <= MAX_ARTIFACT_BYTES:
            raise ValueError('Artifact read limit must be between 1 and 10485760 bytes')
        async with self.ap.persistence_mgr.tenant_uow(context.workspace_uuid) as uow:
            row = await self._row(uow, context, artifact_id, owner)
            if row['size'] > max_bytes:
                raise ArtifactError('artifact_too_large', 'Artifact exceeds the read size limit', 413)
            content_row = await self.content._row(uow, context.workspace_uuid, row['content_ref'])
        # Authorize an immutable snapshot, then release DB resources before object-store I/O.
        try:
            value = await self.content._read(content_row, max_bytes)
        except ContentIntegrityError as exc:
            raise ArtifactError(
                'artifact_integrity_failed', 'Artifact content failed integrity verification', 422
            ) from exc
        if len(value) != row['size'] or hashlib.sha256(value).hexdigest() != row['digest']:
            raise ArtifactError('artifact_integrity_failed', 'Artifact content failed integrity verification', 422)
        return {'metadata': self._public(row), 'content': value}

    async def read_content(self, context, artifact_id, **options):
        from .artifact_reader import read_artifact_content

        result = await self.read(context, artifact_id)
        return await read_artifact_content(result['content'], result['metadata'], **options)

    async def _has_references(self, uow, context, artifact_id):
        return (
            await uow.execute(
                sa.select(ArtifactReference.artifact_id)
                .where(
                    ArtifactReference.workspace_uuid == context.workspace_uuid,
                    ArtifactReference.artifact_id == artifact_id,
                )
                .limit(1)
            )
        ).first() is not None

    async def retain(self, context, artifact_id: str) -> dict:
        owner = await self._authorize(context, write=True)
        async with self.ap.persistence_mgr.tenant_uow(context.workspace_uuid) as uow:
            await self._row(uow, context, artifact_id, owner, lock=True)
            pin = dict(
                workspace_uuid=context.workspace_uuid,
                artifact_id=artifact_id,
                holder_type='principal',
                holder_id=':'.join(owner),
            )
            exists = (await uow.execute(sa.select(ArtifactReference.artifact_id).filter_by(**pin))).first()
            if exists is None:
                await uow.execute(sa.insert(ArtifactReference).values(**pin))
            await uow.execute(sa.update(Artifact).where(*self._scope(context, artifact_id)).values(expires_at=None))
            return self._public(await self._row(uow, context, artifact_id, owner))

    async def release(self, context, artifact_id: str) -> dict:
        owner = await self._authorize(context, write=True)
        async with self.ap.persistence_mgr.tenant_uow(context.workspace_uuid) as uow:
            await self._row(uow, context, artifact_id, owner, lock=True)
            removed = await uow.execute(
                sa.delete(ArtifactReference).where(
                    ArtifactReference.workspace_uuid == context.workspace_uuid,
                    ArtifactReference.artifact_id == artifact_id,
                    ArtifactReference.holder_type == 'principal',
                    ArtifactReference.holder_id == ':'.join(owner),
                )
            )
            if removed.rowcount and not await self._has_references(uow, context, artifact_id):
                await uow.execute(
                    sa.update(Artifact)
                    .where(*self._scope(context, artifact_id))
                    .values(
                        expires_at=_now() + dt.timedelta(seconds=DEFAULT_TTL_SECONDS),
                    )
                )
            return self._public(await self._row(uow, context, artifact_id, owner))

    async def delete(self, context, artifact_id: str) -> dict:
        owner = await self._authorize(context, write=True)
        async with self.ap.persistence_mgr.tenant_uow(context.workspace_uuid) as uow:
            await self._row(uow, context, artifact_id, owner, lock=True)
            if await self._has_references(uow, context, artifact_id):
                raise ArtifactError('artifact_in_use', 'Artifact is still in use', 409)
            await uow.execute(sa.update(Artifact).where(*self._scope(context, artifact_id)).values(deleted_at=_now()))
        return {'id': artifact_id, 'deleted': True}

    async def collect_expired(self, context: ExecutionContext, *, limit: int = 100) -> int:
        if (
            not isinstance(context, ExecutionContext)
            or context.trigger_principal is None
            or context.trigger_principal.principal_type != PrincipalType.SYSTEM
        ):
            raise PermissionError('Artifact collection requires the maintenance system context')
        if type(limit) is not int or not 1 <= limit <= 1000:
            raise ValueError('Artifact collection limit must be between 1 and 1000')
        await self.content._validate(context)
        # The tombstone must commit before deleting external bytes, even if a later transaction fails.
        if self.ap.persistence_mgr.current_session() is not None:
            raise RuntimeError('Artifact collection must not run inside a transaction')
        async with self.ap.persistence_mgr.tenant_uow(context.workspace_uuid) as uow:
            ids = (
                (
                    await uow.execute(
                        sa.select(Artifact.id)
                        .where(
                            Artifact.workspace_uuid == context.workspace_uuid,
                            sa.or_(Artifact.deleted_at.is_not(None), Artifact.expires_at <= _now()),
                        )
                        .order_by(Artifact.id)
                        .limit(limit)
                    )
                )
                .scalars()
                .all()
            )
        collected = 0
        for artifact_id in ids:
            try:
                if await self._collect_one(context, artifact_id):
                    collected += 1
            except Exception:
                self.ap.logger.exception('Artifact collection failed; its tombstone is retained for retry')
        return collected

    async def _collect_one(self, context, artifact_id):
        async with self.ap.persistence_mgr.tenant_uow(context.workspace_uuid) as uow:
            try:
                row = await self._row(uow, context, artifact_id, lock=True, live=False)
            except FileNotFoundError:
                return False
            if await self._has_references(uow, context, artifact_id):
                return False
            if row['deleted_at'] is None:
                if row['expires_at'] is None or row['expires_at'] > _now():
                    return False
                await uow.execute(
                    sa.update(Artifact).where(*self._scope(context, artifact_id)).values(deleted_at=_now())
                )
        async with self.ap.persistence_mgr.tenant_uow(context.workspace_uuid) as uow:
            try:
                row = await self._row(uow, context, artifact_id, lock=True, live=False)
            except FileNotFoundError:
                return False
            content = await self.content._row(uow, context.workspace_uuid, row['content_ref'])
            if content['owner_type'] != 'artifact' or content['owner'] != artifact_id:
                raise RuntimeError('Artifact cannot collect content owned by another business')
            # Check FK protection before external deletion; rollback restores only the committed tombstone.
            await uow.execute(sa.delete(Artifact).where(*self._scope(context, artifact_id)))
            await uow.execute(
                sa.delete(ContentObject).where(
                    ContentObject.workspace_uuid == context.workspace_uuid,
                    ContentObject.ref == row['content_ref'],
                )
            )
            if content['backend'] != 'database':
                provider, _ = await self.content._s3(content['backend'], content['locator'])
                # Tombstones retain the locator until deletion succeeds; retry is idempotent after a crash.
                await provider.delete(content['locator']['key'])
        return True
