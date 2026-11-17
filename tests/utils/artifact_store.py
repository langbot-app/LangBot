"""Attach a real disposable Artifact database to focused Box test applications."""

from __future__ import annotations

import logging
import datetime as dt
from contextlib import AsyncExitStack
from types import SimpleNamespace

import pytest
import sqlalchemy as sa
from sqlalchemy.ext.asyncio import create_async_engine

from langbot.pkg.entity.persistence.base import Base
from langbot.pkg.entity.persistence.agent_run import AgentRun
from langbot.pkg.utils.execution_lease import OWNER_ID
from langbot.pkg.entity.persistence.workspace import Workspace, WorkspaceExecutionState
from langbot.pkg.persistence.mgr import PersistenceManager
from langbot.pkg.storage.artifacts import ArtifactService
from langbot.pkg.storage.artifact_publication import ArtifactPublicationService
from langbot.pkg.storage.mgr import StorageMgr
from langbot.pkg.workspace.service import WorkspaceService


@pytest.fixture(name='artifact_store')
async def _artifact_store(tmp_path):
    store_count = 0
    cleanup = AsyncExitStack()

    async def attach(ap, context):
        nonlocal store_count
        engine = create_async_engine(f'sqlite+aiosqlite:///{tmp_path / f"artifacts-{store_count}.db"}')
        store_count += 1
        cleanup.push_async_callback(engine.dispose)
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
            await connection.execute(
                sa.insert(Workspace).values(
                    uuid=context.workspace_uuid,
                    instance_uuid=context.instance_uuid,
                    name='Artifact Box test',
                    slug='artifact-box-test',
                    source='cloud_projection',
                )
            )
            await connection.execute(
                sa.insert(WorkspaceExecutionState).values(
                    workspace_uuid=context.workspace_uuid,
                    instance_uuid=context.instance_uuid,
                    active_generation=context.placement_generation,
                    source='cloud',
                )
            )
        if not getattr(ap, 'logger', None):
            ap.logger = logging.getLogger('artifact-box-test')
        if not getattr(ap, 'instance_config', None):
            ap.instance_config = SimpleNamespace(data={})
        ap.instance_config.data['storage'] = {'use': 'persistent', 'content': {'backend': 'database'}}
        ap.persistence_mgr = PersistenceManager(ap)
        ap.persistence_mgr.db = SimpleNamespace(get_engine=lambda: engine)
        if not getattr(ap, 'workspace_service', None):
            ap.workspace_service = WorkspaceService(ap, instance_uuid=context.instance_uuid)
        ap.storage_mgr = StorageMgr(ap)
        cleanup.push_async_callback(ap.storage_mgr.shutdown)
        ap.artifact_service = ArtifactService(ap)
        ap.artifact_publication_service = ArtifactPublicationService(ap)
        return ap

    async with cleanup:
        yield attach


async def seed_run(ap, context, run_id):
    async with ap.persistence_mgr.tenant_uow(context.workspace_uuid) as uow:
        await uow.execute(
            sa.insert(AgentRun).values(
                run_id=run_id,
                runner_id='plugin:test/runner/default',
                workspace_id=context.workspace_uuid,
                status='running',
                execution_owner_id=OWNER_ID,
                execution_lease_expires_at=dt.datetime.now(dt.timezone.utc).replace(tzinfo=None)
                + dt.timedelta(seconds=120),
            )
        )


async def named_key_context(ap, context):
    import uuid
    from langbot.pkg.api.context import PrincipalContext, PrincipalType, RequestContext, WorkspaceContext
    from langbot.pkg.entity.persistence.apikey import ApiKey

    manager_id = str(uuid.uuid4())
    async with ap.persistence_mgr.tenant_uow(context.workspace_uuid) as uow:
        await uow.execute(
            sa.insert(ApiKey).values(
                uuid=manager_id,
                workspace_uuid=context.workspace_uuid,
                name='test-manager',
                key_hash=uuid.uuid4().hex,
                scopes=['resource.view', 'resource.manage'],
            )
        )
    return RequestContext(
        instance_uuid=context.instance_uuid,
        placement_generation=context.placement_generation,
        request_id='artifact-test',
        auth_type='api-key',
        principal=PrincipalContext(PrincipalType.API_KEY, api_key_uuid=manager_id),
        workspace=WorkspaceContext(context.workspace_uuid, None, None, frozenset({'resource.view', 'resource.manage'})),
    )
