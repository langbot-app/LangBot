"""Thin WorkspaceMetadata key-value persistence helpers."""

from __future__ import annotations

import collections.abc
import typing

import sqlalchemy as sa

from ..entity.persistence.metadata import WorkspaceMetadata
from .dialect import upsert_insert


async def _execute(executor: typing.Any, statement: typing.Any):
    execute_async = getattr(executor, 'execute_async', None)
    if callable(execute_async):
        return await execute_async(statement)
    return await executor.execute(statement)


async def get_workspace_metadata(
    executor: typing.Any,
    workspace_uuid: str,
    key: str,
) -> str | None:
    """Read one ``WorkspaceMetadata`` string value for ``workspace_uuid``."""

    result = await _execute(
        executor,
        sa.select(WorkspaceMetadata.value).where(
            WorkspaceMetadata.workspace_uuid == workspace_uuid,
            WorkspaceMetadata.key == key,
        ),
    )
    return result.scalar_one_or_none()


async def get_workspace_metadata_map(
    executor: typing.Any,
    workspace_uuid: str,
    keys: collections.abc.Iterable[str],
) -> dict[str, str]:
    """Read multiple ``WorkspaceMetadata`` values for ``workspace_uuid``."""

    key_list = list(keys)
    if not key_list:
        return {}
    result = await _execute(
        executor,
        sa.select(WorkspaceMetadata.key, WorkspaceMetadata.value).where(
            WorkspaceMetadata.workspace_uuid == workspace_uuid,
            WorkspaceMetadata.key.in_(key_list),
        ),
    )
    return dict(result.all())


async def upsert_workspace_metadata(
    executor: typing.Any,
    workspace_uuid: str,
    key: str,
    value: str,
    *,
    target: typing.Any = None,
) -> None:
    """Insert or replace one ``WorkspaceMetadata`` entry atomically."""

    dialect_target = executor if target is None else target
    statement = (
        upsert_insert(dialect_target, WorkspaceMetadata)
        .values(workspace_uuid=workspace_uuid, key=key, value=value)
        .on_conflict_do_update(
            index_elements=['workspace_uuid', 'key'],
            set_={'value': value},
        )
    )
    await _execute(executor, statement)


async def delete_workspace_metadata(
    executor: typing.Any,
    workspace_uuid: str,
    keys: collections.abc.Iterable[str],
) -> None:
    """Delete one or more ``WorkspaceMetadata`` keys for ``workspace_uuid``."""

    key_list = list(keys)
    if not key_list:
        return
    await _execute(
        executor,
        sa.delete(WorkspaceMetadata).where(
            WorkspaceMetadata.workspace_uuid == workspace_uuid,
            WorkspaceMetadata.key.in_(key_list),
        ),
    )
