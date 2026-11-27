"""Explicit producer publication grants, never sourced from Runner configuration."""

from __future__ import annotations

import uuid

import sqlalchemy as sa

from ..api.authz import Permission, PermissionDeniedError, require_permission
from ..api.context import ExecutionContext, PrincipalContext, PrincipalType, RequestContext, WorkspaceContext
from ..entity.persistence.agent import Agent
from ..entity.persistence.artifact_publication import ArtifactPublication
from ..entity.persistence.pipeline import LegacyPipeline


class ArtifactPublicationService:
    def __init__(self, ap):
        self.ap = ap

    @staticmethod
    def _principal(context):
        if not isinstance(context, RequestContext):
            raise PermissionDeniedError('Permission denied')
        principal = context.principal
        if principal.principal_type == PrincipalType.ACCOUNT:
            identity = principal.account_uuid
        elif principal.principal_type == PrincipalType.API_KEY:
            identity = principal.api_key_uuid
        else:
            raise PermissionDeniedError('Permission denied')
        try:
            if str(uuid.UUID(identity)) != identity:
                raise ValueError
        except (ValueError, TypeError, AttributeError):
            raise PermissionDeniedError('Permission denied') from None
        return principal.principal_type.value, identity

    @staticmethod
    def _scope(context, producer_type, producer_id):
        if producer_type not in {'agent', 'pipeline', 'event_processor'}:
            raise ValueError('Invalid output publication producer type')
        if not isinstance(producer_id, str) or not 1 <= len(producer_id) <= 255:
            raise ValueError('Invalid output publication producer ID')
        return (
            ArtifactPublication.workspace_uuid == context.workspace_uuid,
            ArtifactPublication.producer_type == producer_type,
            ArtifactPublication.producer_id == producer_id,
        )

    async def _producer(self, uow, context, producer_type, producer_id):
        self._scope(context, producer_type, producer_id)
        model = LegacyPipeline if producer_type == 'pipeline' else Agent
        statement = sa.select(model.uuid).where(
            model.workspace_uuid == context.workspace_uuid, model.uuid == producer_id
        )
        if model is Agent:
            statement = statement.where(Agent.kind == producer_type)
        if (await uow.execute(statement)).first() is None:
            raise FileNotFoundError('Resource not found')

    @staticmethod
    def _public(row):
        return {
            key: row[key]
            for key in ('producer_type', 'producer_id', 'manager_type', 'manager_id', 'revision', 'enabled')
        }

    async def get(self, context, producer_type, producer_id):
        owner = self._principal(context)
        require_permission(context, Permission.RESOURCE_VIEW)
        await self.ap.storage_mgr.content_store._validate(context)
        async with self.ap.persistence_mgr.tenant_uow(context.workspace_uuid) as uow:
            await self._producer(uow, context, producer_type, producer_id)
            row = (
                (
                    await uow.execute(
                        sa.select(ArtifactPublication.__table__).where(
                            *self._scope(context, producer_type, producer_id)
                        )
                    )
                )
                .mappings()
                .first()
            )
            if row is None:
                return {'producer_type': producer_type, 'producer_id': producer_id, 'enabled': False, 'revision': None}
            if (row['manager_type'], row['manager_id']) != owner:
                raise FileNotFoundError('Resource not found')
            return self._public(row)

    async def set(self, context, producer_type, producer_id, enabled):
        owner = self._principal(context)
        require_permission(context, Permission.RESOURCE_MANAGE)
        if type(enabled) is not bool:
            raise ValueError('enabled must be a boolean')
        await self.ap.artifact_service.resolve_manager_context(ExecutionContext.from_request(context), context)
        async with self.ap.persistence_mgr.tenant_uow(context.workspace_uuid) as uow:
            await self._producer(uow, context, producer_type, producer_id)
            dialect = self.ap.persistence_mgr.get_db_engine().dialect.name
            if dialect == 'postgresql':
                from sqlalchemy.dialects.postgresql import insert
            elif dialect == 'sqlite':
                from sqlalchemy.dialects.sqlite import insert
            else:
                raise ValueError('Output publication requires PostgreSQL or SQLite')
            revision = str(uuid.uuid4())
            await uow.execute(
                insert(ArtifactPublication)
                .values(
                    workspace_uuid=context.workspace_uuid,
                    producer_type=producer_type,
                    producer_id=producer_id,
                    manager_type=owner[0],
                    manager_id=owner[1],
                    enabled=enabled,
                    revision=revision,
                )
                .on_conflict_do_nothing(index_elements=['workspace_uuid', 'producer_type', 'producer_id'])
            )
            row = (
                (
                    await uow.execute(
                        sa.select(ArtifactPublication.__table__).where(
                            *self._scope(context, producer_type, producer_id)
                        )
                    )
                )
                .mappings()
                .one()
            )
            if (row['manager_type'], row['manager_id']) != owner:
                raise FileNotFoundError('Resource not found')
            await uow.execute(
                sa.update(ArtifactPublication)
                .where(*self._scope(context, producer_type, producer_id))
                .values(enabled=enabled, revision=revision)
            )
            return {**self._public(row), 'enabled': enabled, 'revision': revision}

    async def disable(self, context, producer_type, producer_id):
        return await self.set(context, producer_type, producer_id, False)

    async def snapshot_for_run(self, context, producer_type, producer_id):
        if not producer_id or producer_type not in {'agent', 'pipeline', 'event_processor'}:
            return None
        await self.ap.storage_mgr.content_store._validate(context)
        async with self.ap.persistence_mgr.tenant_uow(context.workspace_uuid) as uow:
            await self._producer(uow, context, producer_type, producer_id)
            row = (
                (
                    await uow.execute(
                        sa.select(ArtifactPublication.__table__).where(
                            *self._scope(context, producer_type, producer_id), ArtifactPublication.enabled.is_(True)
                        )
                    )
                )
                .mappings()
                .first()
            )
            return self._public(row) if row is not None else None

    async def manager_for_commit(self, context, snapshot):
        if not isinstance(snapshot, dict):
            raise PermissionDeniedError('Permission denied')
        producer_type, producer_id = snapshot.get('producer_type'), snapshot.get('producer_id')
        await self.ap.storage_mgr.content_store._validate(context)
        async with self.ap.persistence_mgr.tenant_uow(context.workspace_uuid) as uow:
            scope = self._scope(context, producer_type, producer_id)
            # Serialize revocation with the caller's enclosing output-commit transaction.
            await uow.execute(
                sa.update(ArtifactPublication).where(*scope).values(revision=ArtifactPublication.revision)
            )
            row = (await uow.execute(sa.select(ArtifactPublication.__table__).where(*scope))).mappings().first()
            if (
                row is None
                or not row['enabled']
                or any(row[key] != snapshot.get(key) for key in ('revision', 'manager_type', 'manager_id'))
            ):
                raise PermissionDeniedError('Permission denied')
            await self._producer(uow, context, producer_type, producer_id)
            principal = PrincipalContext(
                PrincipalType(row['manager_type']),
                account_uuid=row['manager_id'] if row['manager_type'] == 'account' else None,
                api_key_uuid=row['manager_id'] if row['manager_type'] == 'api_key' else None,
            )
            manager = RequestContext(
                instance_uuid=context.instance_uuid,
                placement_generation=context.placement_generation,
                request_id=str(uuid.uuid4()),
                auth_type='output_publication',
                principal=principal,
                workspace=WorkspaceContext(context.workspace_uuid, None, None, frozenset()),
            )
            return await self.ap.artifact_service.resolve_manager_context(context, manager)

    async def remove_producer(self, context, producer_type, producer_id):
        async with self.ap.persistence_mgr.tenant_uow(context.workspace_uuid) as uow:
            await uow.execute(sa.delete(ArtifactPublication).where(*self._scope(context, producer_type, producer_id)))
