"""Workspace-owned sandbox selection and server-only E2B credentials."""

from __future__ import annotations

import json
import uuid

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from langbot_plugin.box.errors import BoxValidationError

from ..entity.persistence.metadata import WorkspaceMetadata

BACKEND_KEY = 'sandbox_backend'
E2B_KEY = 'sandbox_e2b'
SELECTABLE_BACKENDS = ('docker', 'e2b', 'nsjail')


async def get_settings(ap, workspace_uuid: str) -> dict:
    if getattr(ap, 'persistence_mgr', None) is None:
        return {'backend': None, 'e2b': None}
    async with ap.persistence_mgr.tenant_uow(workspace_uuid) as uow:
        result = await uow.execute(
            sa.select(WorkspaceMetadata.key, WorkspaceMetadata.value).where(
                WorkspaceMetadata.workspace_uuid == workspace_uuid, WorkspaceMetadata.key.in_([BACKEND_KEY, E2B_KEY])
            )
        )
        values = dict(result.all())
    return {'backend': values.get(BACKEND_KEY), 'e2b': json.loads(values[E2B_KEY]) if values.get(E2B_KEY) else None}


async def get_backend(ap, workspace_uuid: str) -> str | None:
    return (await get_settings(ap, workspace_uuid))['backend']


async def set_backend(ap, workspace_uuid: str, backend: str, *, e2b_config: dict | None = None) -> None:
    values = {BACKEND_KEY: backend}
    if e2b_config is not None:
        current = (await get_settings(ap, workspace_uuid))['e2b']
        entry = (
            current
            if current and current['config'] == e2b_config
            else {'config': e2b_config, 'revision': uuid.uuid4().hex}
        )
        values[E2B_KEY] = json.dumps(entry)
    try:
        async with ap.persistence_mgr.tenant_uow(workspace_uuid) as uow:
            insert = pg_insert if ap.persistence_mgr.get_db_engine().dialect.name == 'postgresql' else sqlite_insert
            for key, value in values.items():
                statement = insert(WorkspaceMetadata).values(workspace_uuid=workspace_uuid, key=key, value=value)
                await uow.execute(
                    statement.on_conflict_do_update(index_elements=['workspace_uuid', 'key'], set_={'value': value})
                )
    except Exception:
        # Database errors can include the private credential payload in SQL parameters.
        raise BoxValidationError('Sandbox settings could not be stored') from None
