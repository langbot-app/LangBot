"""Integration tests for the operation-trace integrity cache.

These drive the real service against an in-memory SQLite engine so the whole
read path -- scan projection, chain linking, cache reuse and invalidation -- is
exercised end to end rather than in isolation. The integrity summary is called
directly so the hashing counts are not diluted by the page serializer, which
re-verifies only the handful of rows it returns.
"""

from __future__ import annotations

import datetime
import logging
from types import SimpleNamespace

import pytest
import sqlalchemy
from sqlalchemy.ext.asyncio import create_async_engine

from langbot.pkg.entity.persistence.base import Base
from langbot.pkg.entity.persistence import operation_log as operation_log_module
from langbot.pkg.operation_trace import service as service_module

pytestmark = pytest.mark.asyncio

WORKSPACE = '00000000-0000-0000-0000-00000000000a'
MODEL = operation_log_module.WorkspaceOperationLog
FILTERS = [MODEL.workspace_uuid == WORKSPACE]


class _PersistenceManager:
    """Minimal execute_async shim backed by one SQLite engine."""

    def __init__(self, engine) -> None:
        self.engine = engine

    async def execute_async(self, *args, **kwargs):
        async with self.engine.connect() as connection:
            result = await connection.execute(*args, **kwargs)
            await connection.commit()
            return result


def _build_row(index: int, prev_hash: str | None, *, created_at: datetime.datetime | None = None) -> dict:
    """Build one append-only chain row, hash linked to ``prev_hash``."""

    row: dict = {
        'workspace_uuid': WORKSPACE,
        'actor_account_uuid': None,
        'actor_name': None,
        'actor_role': None,
        'principal_type': 'account',
        'api_key_uuid': None,
        'auth_type': 'user_token',
        'http_method': 'GET',
        'route': '/api/v1/pipelines',
        'action': 'view',
        'resource_type': 'pipeline',
        'resource_id': None,
        'level': 2,
        'outcome': 'ok',
        'status_code': 200,
        'summary': f'row {index}',
        'changes': None,
        'client_ip': None,
        'prev_hash': prev_hash,
    }
    if created_at is not None:
        row['created_at'] = created_at
    row['record_hash'] = service_module.compute_record_hash(row)
    return row


async def _append(service, engine, count: int, *, prev_hash: str | None = None) -> list[int]:
    """Append ``count`` valid rows and return every row id in insertion order."""

    for _ in range(count):
        row = _build_row(0, prev_hash)
        async with engine.begin() as connection:
            await connection.execute(sqlalchemy.insert(MODEL).values(**row))
        prev_hash = row['record_hash']
    async with engine.begin() as connection:
        result = await connection.execute(sqlalchemy.select(MODEL.id).order_by(MODEL.id.asc()))
    return [row[0] for row in result.all()]


async def _tail_hash(engine) -> str | None:
    async with engine.begin() as connection:
        result = await connection.execute(sqlalchemy.select(MODEL.record_hash).order_by(MODEL.id.desc()).limit(1))
    return result.scalar_one_or_none()


def _cached_views(service) -> list:
    """Return the cache keys currently held for the test Workspace."""

    return [key for key in service._integrity_cache if key[0] == WORKSPACE]


def _counting_verifier(service, monkeypatch):
    """Replace the per-row verifier with one that records the ids it hashes."""

    calls: list[int] = []
    original = service_module.WorkspaceSettingsService._verify_hash_and_chain

    def counting(row, previous_row):
        calls.append(row.id)
        return original(row, previous_row)

    monkeypatch.setattr(service, '_verify_hash_and_chain', counting)
    return calls


@pytest.fixture
async def trace_env(tmp_path):
    engine = create_async_engine(f'sqlite+aiosqlite:///{tmp_path / "trace.db"}')
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    application = SimpleNamespace(
        persistence_mgr=_PersistenceManager(engine),
        logger=logging.getLogger('operation-trace-test'),
    )
    try:
        yield service_module.WorkspaceSettingsService(application), engine
    finally:
        await engine.dispose()


async def test_cached_read_within_ttl_reuses_without_rehashing(trace_env, monkeypatch):
    service, engine = trace_env
    ids = await _append(service, engine, 5)
    calls = _counting_verifier(service, monkeypatch)

    first = await service._integrity_summary(MODEL, FILTERS)
    assert first['summary']['scanned'] == 5
    assert first['summary']['tampered'] == 0
    assert len(calls) == 5
    views = _cached_views(service)
    assert len(views) == 1
    assert set(service._integrity_cache[views[0]]['verified']) == set(ids)

    # A warm read inside the TTL must not re-hash anything at all: this is the
    # shield that makes a burst of panel opens, refreshes and page turns cheap.
    calls.clear()
    second = await service._integrity_summary(MODEL, FILTERS)
    assert second['summary']['scanned'] == 5
    assert calls == []


async def test_cache_miss_reverifies_every_row(trace_env, monkeypatch):
    service, engine = trace_env
    await _append(service, engine, 6)

    # A zero TTL forces every read past the cache short circuit.
    monkeypatch.setattr(service_module, 'INTEGRITY_CACHE_TTL_SECONDS', 0.0)
    await service._integrity_summary(MODEL, FILTERS)

    calls = _counting_verifier(service, monkeypatch)
    await service._integrity_summary(MODEL, FILTERS)

    # Every row is re-verified on each miss. Skipping previously verified ids
    # would make an edit to an older row permanently invisible.
    assert len(calls) == 6


async def test_edit_to_already_verified_row_is_re_detected(trace_env, monkeypatch):
    service, engine = trace_env
    monkeypatch.setattr(service_module, 'INTEGRITY_CACHE_TTL_SECONDS', 0.0)
    ids = await _append(service, engine, 5)

    clean = await service._integrity_summary(MODEL, FILTERS)
    assert clean['summary']['tampered'] == 0

    # Edit a row that was already verified on the previous pass, without
    # re-signing it: the whole point of tamper evidence is to catch this.
    async with engine.begin() as connection:
        await connection.execute(sqlalchemy.update(MODEL).where(MODEL.id == ids[1]).values(summary='EDITED-OLD'))

    after = await service._integrity_summary(MODEL, FILTERS)
    assert after['summary']['integrity_failed'] == 1
    assert after['integrity_failed_ids'] == [ids[1]]


async def test_content_edit_is_flagged_as_hash_mismatch(trace_env, monkeypatch):
    service, engine = trace_env
    monkeypatch.setattr(service_module, 'INTEGRITY_CACHE_TTL_SECONDS', 0.0)
    ids = await _append(service, engine, 4)
    async with engine.begin() as connection:
        await connection.execute(sqlalchemy.update(MODEL).where(MODEL.id == ids[1]).values(summary='silently edited'))

    result = await service.query_logs(WORKSPACE)
    assert result['integrity_failed_count'] == 1
    assert result['chain_failed_count'] == 0
    assert result['tampered_count'] == 1


async def test_resigned_link_is_flagged_as_chain_break(trace_env, monkeypatch):
    service, engine = trace_env
    monkeypatch.setattr(service_module, 'INTEGRITY_CACHE_TTL_SECONDS', 0.0)
    ids = await _append(service, engine, 4)

    # Re-sign the row from its own content with a forged prev_hash, so its own
    # hash still matches and only the link is wrong. The successor's prev_hash
    # no longer points at this row's record_hash either, so both are flagged.
    async with engine.begin() as connection:
        result = await connection.execute(
            sqlalchemy.select(*[getattr(MODEL, field) for field in service_module._HASH_FIELDS]).where(
                MODEL.id == ids[2]
            )
        )
        content = dict(zip(service_module._HASH_FIELDS, result.first()))
    content['prev_hash'] = 'not-the-predecessor-hash'
    forged_hash = service_module.compute_record_hash(content)
    assert service_module.verify_record_hash(content, forged_hash)

    async with engine.begin() as connection:
        await connection.execute(
            sqlalchemy.update(MODEL)
            .where(MODEL.id == ids[2])
            .values(prev_hash=content['prev_hash'], record_hash=forged_hash)
        )

    result = await service._integrity_summary(MODEL, FILTERS)
    assert result['summary']['integrity_failed'] == 0
    assert result['summary']['chain_failed'] == 2  # the row and its successor
    # Ids come back newest-first; compare as a set to stay order-agnostic.
    assert set(result['chain_failed_ids']) == {ids[2], ids[3]}


async def test_age_prune_drops_the_stale_integrity_cache(trace_env):
    service, engine = trace_env
    await _append(service, engine, 2)
    old_row = _build_row(99, await _tail_hash(engine), created_at=datetime.datetime(2020, 1, 1))
    async with engine.begin() as connection:
        await connection.execute(sqlalchemy.insert(MODEL).values(**old_row))

    # Warm the cache: its verified map now records the row retention will drop.
    await service.query_logs(WORKSPACE)
    assert _cached_views(service)

    await service.prune(WORKSPACE, retention_days=1)

    # Deleting the oldest rows invalidated the cached prefix.
    assert _cached_views(service) == []
    assert 'expired' in (await service.prune(WORKSPACE, retention_days=1))


async def test_each_listing_view_is_cached_independently(trace_env, monkeypatch):
    service, engine = trace_env
    await _append(service, engine, 4)

    # Two different listing filters must not collide: each gets its own entry,
    # and a view that was never scanned must still be verified from scratch.
    all_view = [MODEL.workspace_uuid == WORKSPACE]
    mutation_view = [MODEL.workspace_uuid == WORKSPACE, MODEL.level == 1]
    await service._integrity_summary(MODEL, all_view)
    await service._integrity_summary(MODEL, mutation_view)

    views = _cached_views(service)
    assert len(views) == 2
    assert len({key[1] for key in views}) == 2


async def test_invalidation_clears_every_cached_view(trace_env):
    service, engine = trace_env
    await _append(service, engine, 2)
    old_row = _build_row(99, await _tail_hash(engine), created_at=datetime.datetime(2020, 1, 1))
    async with engine.begin() as connection:
        await connection.execute(sqlalchemy.insert(MODEL).values(**old_row))

    await service._integrity_summary(MODEL, [MODEL.workspace_uuid == WORKSPACE])
    await service._integrity_summary(MODEL, [MODEL.workspace_uuid == WORKSPACE, MODEL.level == 1])
    assert len(_cached_views(service)) == 2

    await service.prune(WORKSPACE, retention_days=1)

    # A deletion invalidates *all* views for the Workspace, not just one.
    assert _cached_views(service) == []
