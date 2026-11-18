"""Authorized assets over ContentStore, independent of execution caches."""

from __future__ import annotations

import datetime as dt
import asyncio
from dataclasses import replace
import hashlib
import json
import posixpath
import re
import uuid

import sqlalchemy as sa

from ..api.authz import Permission, PermissionDeniedError, permissions_for_role, require_permission
from ..api.context import ExecutionContext, PrincipalType, RequestContext
from ..entity.persistence.artifact import Artifact, ArtifactReference
from ..entity.persistence.content import ContentAlias, ContentObject
from ..entity.persistence.skill import SkillVersion
from ..entity.persistence.plugin import PluginSetting
from ..entity.persistence.agent_run import AgentRun
from ..entity.persistence.apikey import ApiKey

MAX_ARTIFACT_BYTES = 10 * 1024 * 1024
MAX_PLUGIN_ARTIFACT_BYTES = 256 * 1024
# Leave transport envelope and authenticated routing metadata room below the 1 MiB frame limit.
MAX_PLUGIN_CONTENT_RESPONSE_BYTES = 768 * 1024
DEFAULT_TTL_SECONDS = 86400
MAX_TTL_SECONDS = 7 * DEFAULT_TTL_SECONDS
READ_LEASE_SECONDS = 120
READ_TIMEOUT_SECONDS = 60


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

    async def _authorize(self, context, *, write=False, operation=None):
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
        elif principal.principal_type == PrincipalType.PLUGIN:
            from ..api.application.plugin_permissions import load_installation, effective_grants

            owner_id = principal.installation_uuid
            if not owner_id or not operation or operation not in (context.allowed_operation_ids or ()):
                raise PermissionDeniedError('Permission denied')
            installation = await load_installation(self.ap, context.workspace_uuid, owner_id)
            if (
                not installation.enabled
                or operation not in effective_grants(self.ap, installation)['workspace_operations']
            ):
                raise PermissionDeniedError('Permission denied')
        if not owner_id:
            raise ArtifactError(
                'artifact_principal_not_supported', 'Artifact operations require an account or API key', 403
            )
        require_permission(context, Permission.RESOURCE_MANAGE if write else Permission.RESOURCE_VIEW)
        await self.content._validate(context)
        if principal.principal_type == PrincipalType.PLUGIN and principal.run_id:
            async with self.ap.persistence_mgr.tenant_uow(context.workspace_uuid) as uow:
                await self._require_run_lease(uow, context, principal.run_id)
        return principal.principal_type.value, owner_id

    async def resolve_manager_context(self, execution_context, manager_context: RequestContext) -> RequestContext:
        if (
            not isinstance(execution_context, (ExecutionContext, RequestContext))
            or not isinstance(manager_context, RequestContext)
            or (manager_context.instance_uuid, manager_context.workspace_uuid, manager_context.placement_generation)
            != (
                execution_context.instance_uuid,
                execution_context.workspace_uuid,
                execution_context.placement_generation,
            )
        ):
            raise ArtifactError('artifact_publish_not_authorized', 'Artifact publication is not authorized', 403)
        await self.content._validate(execution_context)
        principal = manager_context.principal
        if principal.principal_type == PrincipalType.ACCOUNT and principal.account_uuid:
            account = await self.ap.user_service.get_user_by_uuid(principal.account_uuid)
            if account is None or account.status != 'active':
                raise ArtifactError('artifact_publish_not_authorized', 'Artifact publication is not authorized', 403)
            access = await self.ap.workspace_collaboration_service.resolve_account_workspace(
                principal.account_uuid,
                manager_context.workspace_uuid,
            )
            workspace = replace(
                manager_context.workspace,
                membership_uuid=access.membership.uuid,
                role=access.membership.role,
                membership_revision=access.membership.projection_revision,
                permissions=permissions_for_role(access.membership.role),
            )
        elif principal.principal_type == PrincipalType.API_KEY and principal.api_key_uuid:
            try:
                if str(uuid.UUID(principal.api_key_uuid)) != principal.api_key_uuid:
                    raise ValueError('Not a named API key')
            except (ValueError, AttributeError):
                raise ArtifactError('artifact_publish_not_authorized', 'Artifact publication is not authorized', 403)
            async with self.ap.persistence_mgr.tenant_uow(manager_context.workspace_uuid) as uow:
                key = (
                    (
                        await uow.execute(
                            sa.select(ApiKey.__table__).where(
                                ApiKey.workspace_uuid == manager_context.workspace_uuid,
                                ApiKey.uuid == principal.api_key_uuid,
                            )
                        )
                    )
                    .mappings()
                    .first()
                )
            if (
                key is None
                or key['status'] != 'active'
                or (key['expires_at'] is not None and key['expires_at'] <= _now())
            ):
                raise ArtifactError('artifact_publish_not_authorized', 'Artifact publication is not authorized', 403)
            workspace = replace(
                manager_context.workspace, permissions=frozenset(key['scopes']), role=None, membership_uuid=None
            )
        else:
            raise ArtifactError('artifact_publish_not_authorized', 'Artifact publication is not authorized', 403)
        resolved = replace(manager_context, workspace=workspace)
        require_permission(resolved, Permission.RESOURCE_VIEW)
        require_permission(resolved, Permission.RESOURCE_MANAGE)
        return resolved

    @staticmethod
    def _scope(context, artifact_id):
        if not isinstance(artifact_id, str) or not re.fullmatch(r'art_[a-f0-9]{32}', artifact_id):
            raise FileNotFoundError('Resource not found')
        return Artifact.workspace_uuid == context.workspace_uuid, Artifact.id == artifact_id

    @staticmethod
    def _live_run(workspace, run_id):
        return sa.exists(
            sa.select(AgentRun.run_id).where(
                AgentRun.workspace_id == workspace,
                AgentRun.run_id == run_id,
                sa.or_(
                    sa.and_(
                        AgentRun.status == 'running',
                        AgentRun.execution_owner_id.is_not(None),
                        AgentRun.execution_lease_expires_at > _now(),
                    ),
                    sa.and_(
                        AgentRun.status.in_(['running', 'claimed']),
                        AgentRun.claimed_by_runtime_id.is_not(None),
                        AgentRun.claim_token.is_not(None),
                        AgentRun.claim_lease_expires_at > _now(),
                    ),
                ),
            )
        )

    async def _origin_is_active(self, uow, row):
        return row['owner_type'] in {'run_output', 'run_skill'} and bool(
            await uow.session.scalar(
                sa.select(self._live_run(row['workspace_uuid'], row['owner_id'])),
            )
        )

    async def _row(
        self,
        uow,
        context,
        artifact_id,
        owner=None,
        *,
        lock=False,
        live=True,
        public=False,
        run_read=False,
        bound_run=None,
        business_holder=None,
    ):
        conditions = self._scope(context, artifact_id)
        if owner is not None:
            if public:
                conditions += (
                    sa.or_(
                        sa.and_(Artifact.owner_type == owner[0], Artifact.owner_id == owner[1]),
                        sa.and_(
                            Artifact.owner_type == 'run_output',
                            Artifact.manager_type == owner[0],
                            Artifact.manager_id == owner[1],
                        ),
                    ),
                )
            else:
                conditions += (Artifact.owner_type == owner[0], Artifact.owner_id == owner[1])
        if bound_run is not None:
            conditions += (
                sa.exists(
                    sa.select(ArtifactReference.artifact_id).where(
                        ArtifactReference.workspace_uuid == context.workspace_uuid,
                        ArtifactReference.artifact_id == artifact_id,
                        ArtifactReference.holder_type == 'run_input',
                        ArtifactReference.holder_id == bound_run,
                        self._live_run(context.workspace_uuid, bound_run),
                    )
                ),
            )
        if business_holder is not None:
            holder_type, holder_id = business_holder
            conditions += (
                sa.exists(
                    sa.select(ArtifactReference.artifact_id).where(
                        ArtifactReference.workspace_uuid == context.workspace_uuid,
                        ArtifactReference.artifact_id == artifact_id,
                        ArtifactReference.holder_type == holder_type,
                        ArtifactReference.holder_id == holder_id,
                        ArtifactReference.expires_at.is_(None),
                    )
                ),
            )
        if lock:
            # Also reserves SQLite's writer before reading; FOR UPDATE alone is ignored there.
            await uow.execute(sa.update(Artifact).where(*conditions).values(id=Artifact.id))
        row = (await uow.execute(sa.select(Artifact.__table__).where(*conditions))).mappings().first()
        if row is None or (live and row['deleted_at'] is not None):
            raise FileNotFoundError('Resource not found')
        if live and row['owner_type'] == 'run_skill':
            version = (
                await uow.execute(
                    sa.select(SkillVersion.name).where(
                        SkillVersion.uuid == row['source_version_id'],
                        SkillVersion.workspace_uuid == context.workspace_uuid,
                    )
                )
            ).first()
            if version is None:
                raise FileNotFoundError('Resource not found')
            await self._require_skill_run(uow, context, version.name, row['source_revision'])
        run_active = run_read and await self._origin_is_active(uow, row)
        if live and run_read and not run_active:
            raise ArtifactError('artifact_run_not_active', 'Artifact access requires an active run lease', 403)
        if (
            live
            and row['expires_at'] is not None
            and row['expires_at'] <= _now()
            and bound_run is None
            and not run_active
        ):
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
            'source': (
                'skill_resource'
                if row['source_version_id']
                else {'run': 'input_attachment', 'run_output': 'tool_output'}.get(row['owner_type'], 'upload')
            ),
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
        owner = await self._authorize(context, write=True, operation='artifact.create')
        if owner[0] == 'plugin' and isinstance(content, bytes) and len(content) > MAX_PLUGIN_ARTIFACT_BYTES:
            raise ArtifactError('artifact_too_large', 'Artifact exceeds the size limit.', 413)
        return await self._create_owned(context, owner, filename, content, mime_type, ttl_seconds)

    async def create_legacy_upload(
        self,
        context,
        *,
        owner_type,
        owner,
        key,
        value,
        filename=None,
        mime_type='application/octet-stream',
    ):
        """Keep legacy scoped handles while persistent uploads share the Artifact byte owner."""
        principal = await self._authorize(context, write=True)
        expected_owner = ('account:' if principal[0] == 'account' else 'api-key:') + principal[1]
        if owner_type not in {'upload_image', 'upload_document'} or owner != expected_owner:
            raise PermissionDeniedError('Permission denied')
        storage = self.ap.storage_mgr
        if not storage.persistent_content:
            file_key = await storage.save_scoped(
                context,
                owner_type=owner_type,
                owner=owner,
                key=key,
                value=value,
            )
            return {'artifact': None, 'file_key': file_key}
        # Legacy aliases are still read through StorageMgr's configured bound. Never persist
        # a successful upload that its compatibility handle cannot subsequently read.
        if isinstance(value, bytes) and len(value) > min(storage._object_read_limit(), MAX_ARTIFACT_BYTES):
            raise ArtifactError('artifact_too_large', 'Artifact exceeds the size limit.', 413)
        metadata_name = filename or key
        if isinstance(metadata_name, str) and len(metadata_name) > 255:
            # Legacy routes stored UUID keys and did not constrain display-name length.
            # Preserve valid extensions/MIME without weakening ordinary Artifact validation.
            if any(c in metadata_name for c in '/\\') or any(ord(c) < 32 or ord(c) == 127 for c in metadata_name):
                raise ValueError('Invalid artifact filename')
            # Routes already supply an opaque UUID key with the original extension.
            metadata_name = key
            if isinstance(metadata_name, str) and len(metadata_name) > 255:
                # Legacy document extensions were unbounded too; MIME is stored separately.
                metadata_name = 'upload-' + hashlib.sha256(metadata_name.encode('utf-8')).hexdigest()
        file_key = storage.scoped_object_key(context, owner_type=owner_type, owner=owner, key=key)
        if len(file_key) > 255:
            raise ValueError('Invalid artifact reference')
        async with self.ap.persistence_mgr.tenant_uow(context.workspace_uuid) as uow:
            metadata = await self._create_owned(
                context,
                principal,
                metadata_name,
                value,
                mime_type,
                DEFAULT_TTL_SECONDS,
            )
            row = await self._row(uow, context, metadata['id'], principal, lock=True)
            await uow.execute(
                sa.insert(ContentAlias).values(
                    workspace_uuid=context.workspace_uuid,
                    key=file_key,
                    content_ref=row['content_ref'],
                )
            )
            await uow.execute(
                sa.insert(ArtifactReference).values(
                    workspace_uuid=context.workspace_uuid,
                    artifact_id=row['id'],
                    holder_type='legacy_alias',
                    holder_id=file_key,
                )
            )
            await uow.execute(sa.update(Artifact).where(*self._scope(context, row['id'])).values(expires_at=None))
            return {'artifact': self._public(await self._row(uow, context, row['id'], principal)), 'file_key': file_key}

    async def create_skill_resource(
        self,
        context,
        skill_name: str,
        revision: str,
        path: str,
        ttl_seconds: int = DEFAULT_TTL_SECONDS,
    ) -> dict:
        """Register a caller-private reference, never upload or copy package bytes."""
        owner = await self._authorize(context, write=True)
        require_permission(context, Permission.RESOURCE_VIEW)
        if type(ttl_seconds) is not int or not 1 <= ttl_seconds <= MAX_TTL_SECONDS:
            raise ValueError('Artifact TTL must be between 1 and 604800 seconds')
        source = await self.ap.skill_repository.resolve_artifact_resource(
            context,
            skill_name,
            path,
            expected_revision=revision,
        )
        return await self._create_skill_resource_owned(context, owner, source, ttl_seconds)

    @staticmethod
    def _skill_source(row):
        return {
            'version_id': row['source_version_id'],
            'revision': row['source_revision'],
            'path': row['source_path'],
            'content_ref': row['content_ref'],
            'digest': row['digest'],
            'size': row['size'],
            'mime_type': row['mime_type'],
            'name': row['name'],
        }

    async def _create_skill_resource_owned(self, context, owner, source, ttl_seconds=DEFAULT_TTL_SECONDS):
        identity = '\0'.join((context.workspace_uuid, *owner, source['version_id'], source['path']))
        artifact_id = 'art_' + hashlib.sha256(identity.encode()).hexdigest()[:32]
        async with self.ap.persistence_mgr.tenant_uow(context.workspace_uuid) as uow:
            # Serialize registration against version deletion before creating the FK pin.
            scope = (
                SkillVersion.uuid == source['version_id'],
                SkillVersion.workspace_uuid == context.workspace_uuid,
                SkillVersion.instance_uuid == context.instance_uuid,
                SkillVersion.content_ref == source['content_ref'],
                SkillVersion.revision == source['revision'],
            )
            changed = await uow.execute(sa.update(SkillVersion).where(*scope).values(uuid=SkillVersion.uuid))
            if not changed.rowcount:
                raise FileNotFoundError('Resource not found')
            if owner[0] == 'run_skill':
                await self._require_skill_run(uow, context, source['name'], source['revision'])
            existing = (await uow.execute(sa.select(Artifact.id).where(*self._scope(context, artifact_id)))).first()
            if existing is None:
                await uow.execute(
                    sa.insert(Artifact).values(
                        id=artifact_id,
                        workspace_uuid=context.workspace_uuid,
                        owner_type=owner[0],
                        owner_id=owner[1],
                        name=posixpath.basename(source['path']),
                        mime_type=source['mime_type'],
                        size=source['size'],
                        digest=source['digest'],
                        content_ref=source['content_ref'],
                        source_version_id=source['version_id'],
                        source_revision=source['revision'],
                        source_path=source['path'],
                        expires_at=_now() + dt.timedelta(seconds=ttl_seconds),
                    )
                )
            return self._public(await self._row(uow, context, artifact_id, owner))

    async def _require_skill_run(self, uow, context, skill_name, revision):
        run_id = self._run_owner(context)[1]
        await self._require_run_lease(uow, context, run_id)
        raw = (
            await uow.execute(
                sa.select(AgentRun.metadata_json).where(
                    AgentRun.workspace_id == context.workspace_uuid,
                    AgentRun.run_id == run_id,
                )
            )
        ).scalar_one()
        try:
            pinned = json.loads(raw or '{}').get('activated_skills', {}).get(skill_name)
        except (ValueError, AttributeError, TypeError):
            pinned = None
        if not revision or pinned != revision:
            raise PermissionDeniedError('Permission denied')
        return run_id

    async def create_run_skill_resource(
        self,
        context,
        skill_name: str,
        revision: str,
        path: str,
        *,
        max_bytes=1024 * 1024,
    ):
        run_id = await self._authorize_run(context)
        async with self.ap.persistence_mgr.tenant_uow(context.workspace_uuid) as uow:
            await self._require_skill_run(uow, context, skill_name, revision)
        source = await self.ap.skill_repository.resolve_artifact_resource(
            context,
            skill_name,
            path,
            expected_revision=revision,
            max_bytes=max_bytes,
        )
        return await self._create_skill_resource_owned(context, ('run_skill', run_id), source)

    async def read_run_skill_resource(self, context, artifact_id, *, max_bytes=MAX_ARTIFACT_BYTES):
        run_id = await self._authorize_run(context)
        return await self._read_owned(context, ('run_skill', run_id), artifact_id, max_bytes, run_read=True)

    @staticmethod
    def _run_owner(context):
        principal = context.trigger_principal if isinstance(context, ExecutionContext) else None
        if principal is None or principal.principal_type != PrincipalType.PROCESSOR or not principal.run_id:
            raise PermissionError('Run assets require a trusted active run context')
        return 'run', principal.run_id

    async def create_run_input(self, context, filename, content, mime_type):
        owner = self._run_owner(context)
        await self.content._validate(context)
        return await self._create_owned(context, owner, filename, content, mime_type, DEFAULT_TTL_SECONDS)

    async def read_run_input(self, context, artifact_id, *, max_bytes=MAX_ARTIFACT_BYTES):
        owner = self._run_owner(context)
        await self.content._validate(context)
        return await self._read_owned(context, owner, artifact_id, max_bytes)

    async def bind_run_inputs(self, request_context: RequestContext, run_context: ExecutionContext, artifact_ids):
        principal = await self._authorize(request_context)
        run_id = self._run_owner(run_context)[1]
        if (request_context.instance_uuid, request_context.workspace_uuid, request_context.placement_generation) != (
            run_context.instance_uuid,
            run_context.workspace_uuid,
            run_context.placement_generation,
        ):
            raise PermissionError('Input binding requires the same execution scope')
        if (
            not isinstance(artifact_ids, list)
            or len(artifact_ids) > 20
            or any(not isinstance(value, str) for value in artifact_ids)
            or len(set(artifact_ids)) != len(artifact_ids)
        ):
            raise ValueError('Input binding requires at most 20 unique asset IDs')
        async with self.ap.persistence_mgr.tenant_uow(run_context.workspace_uuid) as uow:
            rows = [
                await self._row(uow, request_context, asset_id, principal, lock=True, public=True)
                for asset_id in sorted(artifact_ids)
            ]
            if not (await uow.execute(sa.select(self._live_run(run_context.workspace_uuid, run_id)))).scalar_one():
                raise PermissionError('Input binding requires an active run lease')
            for row in rows:
                if row['source_version_id'] is not None:
                    raise PermissionDeniedError('Permission denied')
                pin = dict(
                    workspace_uuid=run_context.workspace_uuid,
                    artifact_id=row['id'],
                    holder_type='run_input',
                    holder_id=run_id,
                )
                if (await uow.execute(sa.select(ArtifactReference.artifact_id).filter_by(**pin))).first() is None:
                    await uow.execute(sa.insert(ArtifactReference).values(**pin))

    async def read_bound_run_input(self, context, artifact_id, *, max_bytes=MAX_ARTIFACT_BYTES):
        run_id = self._run_owner(context)[1]
        await self.content._validate(context)
        return await self._read_owned(context, None, artifact_id, max_bytes, bound_run=run_id)

    async def release_run_inputs(self, context):
        run_id = self._run_owner(context)[1]
        await self.content._validate(context)
        async with self.ap.persistence_mgr.tenant_uow(context.workspace_uuid) as uow:
            ids = (
                (
                    await uow.execute(
                        sa.select(ArtifactReference.artifact_id)
                        .where(
                            ArtifactReference.workspace_uuid == context.workspace_uuid,
                            ArtifactReference.holder_type == 'run_input',
                            ArtifactReference.holder_id == run_id,
                        )
                        .order_by(ArtifactReference.artifact_id)
                    )
                )
                .scalars()
                .all()
            )
        async with self.ap.persistence_mgr.tenant_uow(context.workspace_uuid) as uow:
            for artifact_id in ids:
                try:
                    await self._row(uow, context, artifact_id, lock=True, live=False)
                except FileNotFoundError:
                    continue
                await uow.execute(
                    sa.delete(ArtifactReference).where(
                        ArtifactReference.workspace_uuid == context.workspace_uuid,
                        ArtifactReference.artifact_id == artifact_id,
                        ArtifactReference.holder_type == 'run_input',
                        ArtifactReference.holder_id == run_id,
                    )
                )

    async def create_run_output(self, context, filename, content, mime_type):
        owner = 'run_output', await self._authorize_run(context)
        return await self._create_owned(context, owner, filename, content, mime_type, DEFAULT_TTL_SECONDS)

    async def read_run_output(self, context, artifact_id, *, max_bytes=MAX_ARTIFACT_BYTES):
        owner = 'run_output', await self._authorize_run(context)
        return await self._read_owned(context, owner, artifact_id, max_bytes, run_read=True)

    async def commit_run_outputs(
        self, context, artifact_ids, *, manager_context: RequestContext | None = None, publication=None
    ):
        if (
            not isinstance(artifact_ids, list)
            or not 1 <= len(artifact_ids) <= 100
            or any(not isinstance(artifact_id, str) for artifact_id in artifact_ids)
            or len(set(artifact_ids)) != len(artifact_ids)
        ):
            raise ValueError('Commit requires 1 to 100 unique output asset IDs')
        async with self.ap.persistence_mgr.tenant_write_uow(context.workspace_uuid) as uow:
            # Keep policy revocation and output publication in the same transaction.
            if manager_context is None:
                manager_context = await self.ap.artifact_publication_service.manager_for_commit(context, publication)
            else:
                manager_context = await self.resolve_manager_context(context, manager_context)
            manager = await self._authorize(manager_context, write=True)
            owner = 'run_output', await self._authorize_run(context)
            # Authorize the whole batch before pinning; lock order prevents reversed-batch deadlocks.
            rows = {
                artifact_id: await self._row(uow, context, artifact_id, owner, lock=True, run_read=True)
                for artifact_id in sorted(artifact_ids)
            }
            await self._require_run_lease(uow, context, owner[1])
            for artifact_id, row in rows.items():
                if row['manager_type'] is not None and (row['manager_type'], row['manager_id']) != manager:
                    raise ArtifactError('artifact_manager_conflict', 'Artifact has a different manager', 409)
            pending = [key for key, row in rows.items() if row['manager_type'] is None]
            if pending:
                reference = ArtifactReference
                holder_id = ':'.join(manager)
                existing = (
                    await uow.execute(
                        sa.select(reference.artifact_id, reference.holder_type).where(
                            reference.workspace_uuid == context.workspace_uuid,
                            reference.artifact_id.in_(pending),
                            sa.or_(
                                reference.holder_type == 'run_output_commit',
                                sa.and_(reference.holder_type == 'principal', reference.holder_id == holder_id),
                            ),
                        )
                    )
                ).all()
                if any(kind == 'run_output_commit' for _, kind in existing):
                    raise ArtifactError(
                        'artifact_legacy_commit_unmanaged', 'Legacy output requires explicit manager assignment', 409
                    )
                pinned = {key for key, _ in existing}
                pins = [
                    dict(
                        workspace_uuid=context.workspace_uuid,
                        artifact_id=key,
                        holder_type='principal',
                        holder_id=holder_id,
                    )
                    for key in pending
                    if key not in pinned
                ]
                if pins:
                    await uow.execute(sa.insert(reference).values(pins))
                await uow.execute(
                    sa.update(Artifact)
                    .where(Artifact.workspace_uuid == context.workspace_uuid, Artifact.id.in_(pending))
                    .values(manager_type=manager[0], manager_id=manager[1], expires_at=None)
                )
            # The locked rows supply the response; a released publication must not be pinned again.
            await self._require_run_lease(uow, context, owner[1])
            return [
                self._public(dict(rows[key], expires_at=None) if rows[key]['manager_type'] is None else rows[key])
                for key in artifact_ids
            ]

    async def _authorize_run(self, context):
        run_id = self._run_owner(context)[1]
        await self.content._validate(context)
        async with self.ap.persistence_mgr.tenant_uow(context.workspace_uuid) as uow:
            await self._require_run_lease(uow, context, run_id)
        return run_id

    async def _require_run_lease(self, uow, context, run_id):
        if not (await uow.execute(sa.select(self._live_run(context.workspace_uuid, run_id)))).scalar_one():
            raise ArtifactError('artifact_run_not_active', 'Artifact access requires an active run lease', 403)

    async def expire_run_outputs(self, context):
        owner = 'run_output', self._run_owner(context)[1]
        await self.content._validate(context)
        now = _now()
        async with self.ap.persistence_mgr.tenant_uow(context.workspace_uuid) as uow:
            ids = (
                (
                    await uow.execute(
                        sa.select(Artifact.id)
                        .where(
                            Artifact.workspace_uuid == context.workspace_uuid,
                            Artifact.owner_type == owner[0],
                            Artifact.owner_id == owner[1],
                            Artifact.manager_type.is_(None),
                            Artifact.deleted_at.is_(None),
                            Artifact.expires_at.is_not(None),
                            Artifact.expires_at > now,
                        )
                        .order_by(Artifact.id)
                    )
                )
                .scalars()
                .all()
            )
        # Discovery must release SQLite's read snapshot before the first write reservation.
        async with self.ap.persistence_mgr.tenant_uow(context.workspace_uuid) as uow:
            expired = 0
            for artifact_id in ids:
                try:
                    row = await self._row(uow, context, artifact_id, owner, lock=True, live=False)
                except FileNotFoundError:
                    continue
                if (
                    row['deleted_at'] is None
                    and row['manager_type'] is None
                    and row['expires_at'] is not None
                    and row['expires_at'] > now
                ):
                    await uow.execute(
                        sa.update(Artifact).where(*self._scope(context, artifact_id)).values(expires_at=now)
                    )
                    expired += 1
            return expired

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
            if owner[0] == 'run_output':
                await self._require_run_lease(uow, context, owner[1])
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
        owner = await self._authorize(context, operation='artifact.get')
        async with self.ap.persistence_mgr.tenant_uow(context.workspace_uuid) as uow:
            return self._public(await self._row(uow, context, artifact_id, owner, public=True))

    async def read(self, context, artifact_id: str, max_bytes: int = MAX_ARTIFACT_BYTES) -> dict:
        owner = await self._authorize(context, operation='artifact.read')
        if owner[0] == 'plugin' and type(max_bytes) is int:
            max_bytes = min(max_bytes, MAX_PLUGIN_ARTIFACT_BYTES)
        result = await self._read_owned(context, owner, artifact_id, max_bytes, public=True)
        if owner[0] == 'plugin':
            await self._authorize(context, operation='artifact.read')
        return result

    async def _read_owned(
        self,
        context,
        owner,
        artifact_id,
        max_bytes,
        *,
        public=False,
        run_read=False,
        bound_run=None,
        business_holder=None,
    ):
        from .content import ContentIntegrityError

        if type(max_bytes) is not int or not 1 <= max_bytes <= MAX_ARTIFACT_BYTES:
            raise ValueError('Artifact read limit must be between 1 and 10485760 bytes')
        if self.ap.persistence_mgr.current_session() is not None:
            raise RuntimeError('Artifact reads must not run inside a transaction')
        deadline = asyncio.get_running_loop().time() + READ_TIMEOUT_SECONDS
        lease_id = uuid.uuid4().hex
        async with self.ap.persistence_mgr.tenant_uow(context.workspace_uuid) as uow:
            row = await self._row(
                uow,
                context,
                artifact_id,
                owner,
                lock=True,
                public=public,
                run_read=run_read,
                bound_run=bound_run,
                business_holder=business_holder,
            )
            if business_holder is not None:
                await self._require_business_file(uow, context, artifact_id, business_holder[1])
            if row['size'] > max_bytes:
                raise ArtifactError('artifact_too_large', 'Artifact exceeds the read size limit', 413)
            content_row = await self.content._row(uow, context.workspace_uuid, row['content_ref'])
            await uow.execute(
                sa.insert(ArtifactReference).values(
                    workspace_uuid=context.workspace_uuid,
                    artifact_id=artifact_id,
                    holder_type='read_lease',
                    holder_id=lease_id,
                    expires_at=_now() + dt.timedelta(seconds=READ_LEASE_SECONDS),
                )
            )
        # A committed, bounded lease protects bytes without holding a DB writer during object-store I/O.
        try:
            async with asyncio.timeout_at(deadline):
                if row['source_version_id'] is not None:
                    value = await self.ap.skill_repository.read_artifact_resource(
                        context,
                        self._skill_source(row),
                        max_bytes=max_bytes,
                    )
                else:
                    value = await self.content._read(content_row, max_bytes)
            if len(value) != row['size'] or hashlib.sha256(value).hexdigest() != row['digest']:
                raise ArtifactError('artifact_integrity_failed', 'Artifact content failed integrity verification', 422)
            return {'metadata': self._public(row), 'content': value}
        except TimeoutError as exc:
            raise ArtifactError('artifact_read_timeout', 'Artifact read timed out', 504) from exc
        except ContentIntegrityError as exc:
            raise ArtifactError(
                'artifact_integrity_failed', 'Artifact content failed integrity verification', 422
            ) from exc
        finally:
            try:
                async with self.ap.persistence_mgr.tenant_uow(context.workspace_uuid) as uow:
                    await self._row(uow, context, artifact_id, lock=True, live=False)
                    await uow.execute(
                        sa.delete(ArtifactReference).where(
                            ArtifactReference.workspace_uuid == context.workspace_uuid,
                            ArtifactReference.artifact_id == artifact_id,
                            ArtifactReference.holder_type == 'read_lease',
                            ArtifactReference.holder_id == lease_id,
                        )
                    )
            except Exception:
                self.ap.logger.exception('Artifact read lease cleanup failed; the lease will expire')

    async def read_content(self, context, artifact_id, **options):
        from .artifact_reader import read_artifact_content

        owner = await self._authorize(context, operation='artifact.read_content')
        limit = MAX_PLUGIN_ARTIFACT_BYTES if owner[0] == 'plugin' else MAX_ARTIFACT_BYTES
        result = await self._read_owned(context, owner, artifact_id, limit, public=True)
        blocks = await read_artifact_content(result['content'], result['metadata'], **options)
        if owner[0] == 'plugin' and len(json.dumps(blocks).encode('utf-8')) > MAX_PLUGIN_CONTENT_RESPONSE_BYTES:
            raise ArtifactError('artifact_too_large', 'Artifact exceeds the read size limit', 413)
        if owner[0] == 'plugin':
            await self._authorize(context, operation='artifact.read_content')
        return blocks

    @staticmethod
    def _business_holder(holder_type, holder_id):
        # Internal KB adapter only; arbitrary caller-selected reference kinds are never accepted.
        if holder_type != 'knowledge_file' or not isinstance(holder_id, str) or not 1 <= len(holder_id) <= 255:
            raise ValueError('Invalid artifact reference')
        return holder_type, holder_id

    async def _require_business_file(self, uow, context, artifact_id, holder_id):
        from ..entity.persistence.rag import File, KnowledgeBase

        row = (
            await uow.execute(
                sa.select(File.uuid)
                .join(
                    KnowledgeBase,
                    sa.and_(KnowledgeBase.uuid == File.kb_id, KnowledgeBase.workspace_uuid == File.workspace_uuid),
                )
                .where(
                    File.workspace_uuid == context.workspace_uuid,
                    File.uuid == holder_id,
                    File.artifact_id == artifact_id,
                )
            )
        ).first()
        if row is None:
            raise FileNotFoundError('Resource not found')

    async def bind_business(self, context, artifact_id, *, holder_type='knowledge_file', holder_id):
        """Pin an explicitly authorized source inside the KB file-creation transaction.

        The KB service authorizes the destination before calling this internal seam.
        A pin protects lifetime; only the KB read adapter can delegate access to its consumers.
        """
        self._business_holder(holder_type, holder_id)
        owner = await self._authorize(context, write=True)
        require_permission(context, Permission.RESOURCE_VIEW)
        async with self.ap.persistence_mgr.tenant_uow(context.workspace_uuid) as uow:
            row = await self._row(uow, context, artifact_id, owner, lock=True, public=True)
            if row['source_version_id'] is not None or row['owner_type'] not in {'account', 'api_key'}:
                raise PermissionDeniedError('Permission denied')
            await self._require_business_file(uow, context, artifact_id, holder_id)
            pin = dict(
                workspace_uuid=context.workspace_uuid,
                artifact_id=artifact_id,
                holder_type=holder_type,
                holder_id=holder_id,
            )
            if (await uow.execute(sa.select(ArtifactReference.artifact_id).filter_by(**pin))).first() is None:
                await uow.execute(sa.insert(ArtifactReference).values(**pin))
            await uow.execute(sa.update(Artifact).where(*self._scope(context, artifact_id)).values(expires_at=None))
            return self._public(await self._row(uow, context, artifact_id, owner, public=True))

    async def release_business(self, context, artifact_id, *, holder_type='knowledge_file', holder_id):
        """Detach exactly one authorized KB holder in its deletion transaction, never delete bytes.

        Only the trusted KB service may call this after destination authorization. File deletion
        may already have happened in the same UoW, so the former File row is not required here.
        """
        self._business_holder(holder_type, holder_id)
        await self.content._validate(context)
        async with self.ap.persistence_mgr.tenant_uow(context.workspace_uuid) as uow:
            await self._row(uow, context, artifact_id, lock=True, live=False)
            removed = await uow.execute(
                sa.delete(ArtifactReference).where(
                    ArtifactReference.workspace_uuid == context.workspace_uuid,
                    ArtifactReference.artifact_id == artifact_id,
                    ArtifactReference.holder_type == holder_type,
                    ArtifactReference.holder_id == holder_id,
                )
            )
            if removed.rowcount and not await self._has_references(uow, context, artifact_id, durable_only=True):
                await uow.execute(
                    sa.update(Artifact)
                    .where(*self._scope(context, artifact_id))
                    .values(
                        expires_at=_now() + dt.timedelta(seconds=DEFAULT_TTL_SECONDS),
                    )
                )

    async def read_business(
        self, context, artifact_id, *, holder_type='knowledge_file', holder_id, max_bytes=MAX_ARTIFACT_BYTES
    ):
        """Read after the KB service verifies its caller/engine ACL, not from an external ID alone."""
        holder = self._business_holder(holder_type, holder_id)
        await self.content._validate(context)
        result = await self._read_owned(context, None, artifact_id, max_bytes, business_holder=holder)
        # Deleting a KB membership while object-store IO is in flight revokes delivery too.
        await self.content._validate(context)
        async with self.ap.persistence_mgr.tenant_uow(context.workspace_uuid) as uow:
            await self._row(uow, context, artifact_id, business_holder=holder)
            await self._require_business_file(uow, context, artifact_id, holder_id)
        return result

    def _references(self, context, artifact_id, *, durable_only=False):
        return sa.select(ArtifactReference.artifact_id).where(
            ArtifactReference.workspace_uuid == context.workspace_uuid,
            ArtifactReference.artifact_id == artifact_id,
            sa.or_(ArtifactReference.expires_at.is_(None), ArtifactReference.expires_at > _now()),
            sa.or_(
                ArtifactReference.holder_type != 'run_input',
                self._live_run(context.workspace_uuid, ArtifactReference.holder_id),
            ),
            ArtifactReference.holder_type.not_in(['read_lease', 'run_input']) if durable_only else sa.true(),
        )

    async def _has_references(self, uow, context, artifact_id, *, durable_only=False):
        return (
            await uow.execute(self._references(context, artifact_id, durable_only=durable_only).limit(1))
        ).first() is not None

    async def _prune_references(self, uow, context, artifact_id):
        await uow.execute(
            sa.delete(ArtifactReference).where(
                ArtifactReference.workspace_uuid == context.workspace_uuid,
                ArtifactReference.artifact_id == artifact_id,
                sa.or_(
                    sa.and_(ArtifactReference.holder_type == 'read_lease', ArtifactReference.expires_at <= _now()),
                    sa.and_(
                        ArtifactReference.holder_type == 'run_input',
                        sa.not_(self._live_run(context.workspace_uuid, ArtifactReference.holder_id)),
                    ),
                ),
            )
        )

    async def retain(self, context, artifact_id: str) -> dict:
        owner = await self._authorize(context, write=True, operation='artifact.retain')
        async with self.ap.persistence_mgr.tenant_uow(context.workspace_uuid) as uow:
            await self._row(uow, context, artifact_id, owner, lock=True, public=True)
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
            return self._public(await self._row(uow, context, artifact_id, owner, public=True))

    async def release(self, context, artifact_id: str) -> dict:
        owner = await self._authorize(context, write=True, operation='artifact.release')
        async with self.ap.persistence_mgr.tenant_uow(context.workspace_uuid) as uow:
            await self._row(uow, context, artifact_id, owner, lock=True, public=True)
            removed = await uow.execute(
                sa.delete(ArtifactReference).where(
                    ArtifactReference.workspace_uuid == context.workspace_uuid,
                    ArtifactReference.artifact_id == artifact_id,
                    ArtifactReference.holder_type == 'principal',
                    ArtifactReference.holder_id == ':'.join(owner),
                )
            )
            if removed.rowcount and not await self._has_references(uow, context, artifact_id, durable_only=True):
                await uow.execute(
                    sa.update(Artifact)
                    .where(*self._scope(context, artifact_id))
                    .values(
                        expires_at=_now() + dt.timedelta(seconds=DEFAULT_TTL_SECONDS),
                    )
                )
            return self._public(await self._row(uow, context, artifact_id, owner, public=True))

    async def delete(self, context, artifact_id: str) -> dict:
        owner = await self._authorize(context, write=True, operation='artifact.delete')
        async with self.ap.persistence_mgr.tenant_uow(context.workspace_uuid) as uow:
            row = await self._row(uow, context, artifact_id, owner, lock=True, public=True)
            if await self._origin_is_active(uow, row) or await self._has_references(uow, context, artifact_id):
                raise ArtifactError('artifact_in_use', 'Artifact is still in use', 409)
            await uow.execute(sa.update(Artifact).where(*self._scope(context, artifact_id)).values(deleted_at=_now()))
        return {'id': artifact_id, 'deleted': True}

    async def _release_uninstalled_plugin_pins(self, context, limit):
        """Bounded maintenance for principals that can never release their own pins again."""
        installation_exists = sa.exists(
            sa.select(PluginSetting.installation_uuid).where(
                PluginSetting.workspace_uuid == context.workspace_uuid,
                PluginSetting.installation_uuid == Artifact.owner_id,
            )
        )
        own_pin = sa.exists(
            sa.select(ArtifactReference.artifact_id).where(
                ArtifactReference.workspace_uuid == context.workspace_uuid,
                ArtifactReference.artifact_id == Artifact.id,
                ArtifactReference.holder_type == 'principal',
                ArtifactReference.holder_id == sa.literal('plugin:') + Artifact.owner_id,
            )
        )
        async with self.ap.persistence_mgr.tenant_uow(context.workspace_uuid) as uow:
            ids = (
                (
                    await uow.execute(
                        sa.select(Artifact.id)
                        .where(
                            Artifact.workspace_uuid == context.workspace_uuid,
                            Artifact.owner_type == 'plugin',
                            sa.not_(installation_exists),
                            own_pin,
                        )
                        .order_by(Artifact.id)
                        .limit(limit)
                    )
                )
                .scalars()
                .all()
            )
        async with self.ap.persistence_mgr.tenant_uow(context.workspace_uuid) as uow:
            for artifact_id in ids:
                try:
                    row = await self._row(uow, context, artifact_id, lock=True, live=False)
                except FileNotFoundError:
                    continue
                # Disable/revoke is reversible and intentionally does not make assets collectible.
                if (
                    await uow.execute(
                        sa.select(PluginSetting.installation_uuid).where(
                            PluginSetting.workspace_uuid == context.workspace_uuid,
                            PluginSetting.installation_uuid == row['owner_id'],
                        )
                    )
                ).first() is not None:
                    continue
                await uow.execute(
                    sa.delete(ArtifactReference).where(
                        ArtifactReference.workspace_uuid == context.workspace_uuid,
                        ArtifactReference.artifact_id == artifact_id,
                        ArtifactReference.holder_type == 'principal',
                        ArtifactReference.holder_id == 'plugin:' + row['owner_id'],
                    )
                )
                if not await self._has_references(uow, context, artifact_id, durable_only=True):
                    await uow.execute(
                        sa.update(Artifact)
                        .where(*self._scope(context, artifact_id))
                        .values(
                            expires_at=_now() + dt.timedelta(seconds=DEFAULT_TTL_SECONDS),
                        )
                    )

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
        await self._release_uninstalled_plugin_pins(context, limit)
        async with self.ap.persistence_mgr.tenant_uow(context.workspace_uuid) as uow:
            ids = (
                (
                    await uow.execute(
                        sa.select(Artifact.id)
                        .where(
                            Artifact.workspace_uuid == context.workspace_uuid,
                            sa.or_(Artifact.deleted_at.is_not(None), Artifact.expires_at <= _now()),
                            sa.not_(
                                sa.and_(
                                    Artifact.owner_type.in_(['run_output', 'run_skill']),
                                    self._live_run(Artifact.workspace_uuid, Artifact.owner_id),
                                )
                            ),
                            sa.not_(self._references(context, Artifact.id).exists()),
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
            if await self._origin_is_active(uow, row) or await self._has_references(uow, context, artifact_id):
                return False
            await self._prune_references(uow, context, artifact_id)
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
            if row['source_version_id'] is not None:
                # The package belongs to SkillVersion. Dropping our FK pin must never delete it.
                await uow.execute(sa.delete(Artifact).where(*self._scope(context, artifact_id)))
                return True
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
