"""Attach a real disposable Artifact database to focused Box test applications."""

from __future__ import annotations

import logging
from types import SimpleNamespace

import pytest
import sqlalchemy as sa
from sqlalchemy.ext.asyncio import create_async_engine

from langbot.pkg.entity.persistence.base import Base
from langbot.pkg.entity.persistence.workspace import Workspace, WorkspaceExecutionState
from langbot.pkg.persistence.mgr import PersistenceManager
from langbot.pkg.storage.artifacts import ArtifactService
from langbot.pkg.storage.mgr import StorageMgr
from langbot.pkg.workspace.service import WorkspaceService


@pytest.fixture(name='artifact_store')
async def _artifact_store(tmp_path):
    stores = []

    async def attach(ap, context):
        engine = create_async_engine(f'sqlite+aiosqlite:///{tmp_path / ("artifacts-" + str(len(stores)) + ".db")}')
        stores.append((ap, engine))
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
        ap.artifact_service = ArtifactService(ap)
        return ap

    try:
        yield attach
    finally:
        for ap, engine in reversed(stores):
            await ap.storage_mgr.shutdown()
            await engine.dispose()
