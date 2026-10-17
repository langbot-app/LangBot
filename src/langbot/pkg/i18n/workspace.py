"""Workspace-owned message language, stored in the existing tenant metadata."""

from __future__ import annotations

import time
from collections import OrderedDict

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from ..entity.persistence.metadata import WorkspaceMetadata
from . import DEFAULT_LANGUAGE, SUPPORTED_LANGUAGES, normalize_language

LANGUAGE_KEY = 'message_language'
_CACHE_TTL = 30
_CACHE_SIZE = 256


def _cache(ap) -> OrderedDict:
    cache = getattr(ap, '_message_language_cache', None)
    if cache is None:
        cache = OrderedDict()
        ap._message_language_cache = cache
    return cache


async def get_workspace_language(ap, workspace_uuid: str, *, refresh: bool = False) -> str:
    if not workspace_uuid:
        return DEFAULT_LANGUAGE
    cache = _cache(ap)
    cached = cache.get(workspace_uuid)
    if not refresh and cached and cached[1] > time.monotonic():
        return cached[0]
    manager = getattr(ap, 'persistence_mgr', None)
    if manager is None or not callable(getattr(manager, 'tenant_uow', None)):
        return DEFAULT_LANGUAGE
    async with manager.tenant_uow(workspace_uuid) as uow:
        result = await uow.execute(
            sa.select(WorkspaceMetadata.value).where(
                WorkspaceMetadata.workspace_uuid == workspace_uuid,
                WorkspaceMetadata.key == LANGUAGE_KEY,
            )
        )
        locale = normalize_language(result.scalar_one_or_none())
    cache[workspace_uuid] = (locale, time.monotonic() + _CACHE_TTL)
    cache.move_to_end(workspace_uuid)
    while len(cache) > _CACHE_SIZE:
        cache.popitem(last=False)
    return locale


async def set_workspace_language(ap, workspace_uuid: str, locale: str) -> str:
    if locale not in SUPPORTED_LANGUAGES:
        raise ValueError('Unsupported Workspace language')
    async with ap.persistence_mgr.tenant_uow(workspace_uuid) as uow:
        dialect = ap.persistence_mgr.get_db_engine().dialect.name
        insert = pg_insert if dialect == 'postgresql' else sqlite_insert
        statement = insert(WorkspaceMetadata).values(workspace_uuid=workspace_uuid, key=LANGUAGE_KEY, value=locale)
        await uow.execute(
            statement.on_conflict_do_update(
                index_elements=['workspace_uuid', 'key'],
                set_={'value': locale},
            )
        )
    # Synchronous platform callbacks may run in SDK threads. Publish the new
    # value only after commit, so they see changes without restarting a bot.
    _cache(ap)[workspace_uuid] = (locale, time.monotonic() + _CACHE_TTL)
    while len(_cache(ap)) > _CACHE_SIZE:
        _cache(ap).popitem(last=False)
    return locale
