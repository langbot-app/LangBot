"""URL catalog storage, transactional refresh and migration contracts."""

import asyncio
import datetime as dt
import importlib
import json
import os
import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from langbot.pkg.entity.persistence.resource_url import ResourceURL
from langbot.pkg.entity.persistence.event_log import EventLog
from langbot.pkg.entity.persistence.monitoring import MonitoringLLMCall
from langbot.pkg.persistence.media import MediaReferenceText, MediaReferenceJSON
from langbot.pkg.persistence.resource_urls import digest, refresh_images
from langbot.pkg.platform.adapters.aiocqhttp.image_urls import OneBotImageURLs


OLD = 'https://multimedia.nt.qq.com.cn/download?appid=1407&fileid=one&rkey=old'
NEW = OLD.replace('rkey=old', 'rkey=new')


def chain(url=OLD, message_id=42):
    return [{'type': 'Source', 'id': message_id}, {'type': 'Image', 'image_id': 'one.jpg', 'url': url}]


@pytest.fixture(params=['sqlite', 'postgresql'])
async def database(tmp_path, request):
    admin = None
    schema = None
    if request.param == 'postgresql':
        url = os.environ.get('TEST_POSTGRES_URL')
        if not url:
            pytest.skip('TEST_POSTGRES_URL not set')
        admin = create_async_engine(url)
        schema = 'resource_' + uuid.uuid4().hex
        async with admin.begin() as db:
            await db.execute(sa.schema.CreateSchema(schema))
        engine = create_async_engine(url, connect_args={'server_settings': {'search_path': schema}})
    else:
        engine = create_async_engine(f'sqlite+aiosqlite:///{tmp_path / "catalog.db"}')
    try:
        async with engine.begin() as db:
            await db.run_sync(ResourceURL.__table__.create)
            await db.run_sync(EventLog.__table__.create)
        yield engine
    finally:
        await engine.dispose()
        if admin is not None:
            async with admin.begin() as db:
                await db.execute(sa.schema.DropSchema(schema, cascade=True))
            await admin.dispose()


async def append(db, identity, url=OLD):
    await db.execute(
        sa.insert(EventLog).values(
            event_id=identity,
            event_type='message.received',
            source='platform',
            workspace_id='workspace',
            bot_id='bot',
            input_json=json.dumps(chain(url)),
        )
    )


@pytest.mark.asyncio
async def test_dedup_expansion_and_rollback(database):
    async with database.begin() as db:
        await append(db, 'a')
        await append(db, 'b')
    async with database.connect() as db:
        assert (await db.scalar(sa.select(sa.func.count()).select_from(ResourceURL))) == 1
        stored = (await db.execute(sa.text('SELECT input_json FROM event_log'))).scalars().all()
        assert stored[0] == stored[1] and OLD not in stored[0]
        assert OLD in await db.scalar(sa.select(EventLog.input_json).where(EventLog.event_id == 'a'))
        # The original string remains usable for compare-and-swap updates.
        value = await db.scalar(sa.select(EventLog.input_json).where(EventLog.event_id == 'a'))
        result = await db.execute(
            sa.update(EventLog)
            .where(EventLog.event_id == 'a', EventLog.input_json == value)
            .values(input_json=json.dumps(chain(NEW)))
        )
        assert result.rowcount == 1
        await db.rollback()
    async with database.connect() as db:
        assert await db.scalar(sa.select(sa.func.count()).select_from(ResourceURL)) == 1


@pytest.mark.asyncio
async def test_untrusted_content_cannot_inject_catalog_ids(database):
    async with database.begin() as db:
        await append(db, 'a')
        identity = await db.scalar(sa.select(ResourceURL.id))
    with pytest.raises(sa.exc.StatementError, match='Internal resource references'):
        async with database.begin() as db:
            await append(db, 'b', 'langbot-resource://' + identity)


@pytest.mark.asyncio
async def test_orm_update_keeps_loaded_payload_synchronized(database):
    async with database.begin() as db:
        await append(db, 'a')
    async with AsyncSession(database, expire_on_commit=False) as session:
        record = await session.scalar(sa.select(EventLog))
        changed = json.dumps(chain(NEW))
        await session.execute(sa.update(EventLog).where(EventLog.event_id == 'a').values(input_json=changed))
        await session.commit()
        assert record.input_json == changed
        await session.refresh(record)
        assert NEW in record.input_json


@pytest.mark.asyncio
async def test_bulk_and_native_json_preserve_api_shapes(database):
    meta = sa.MetaData()
    sample = sa.Table(
        'sample',
        meta,
        sa.Column('id', sa.Integer, primary_key=True),
        sa.Column('body', MediaReferenceText),
        sa.Column('detail', MediaReferenceJSON),
    )
    async with database.begin() as db:
        await db.run_sync(meta.create_all)
        await db.execute(
            sample.insert(),
            [dict(id=i, body=json.dumps(chain()), detail={'url': OLD, 'flag': False, 'number': 0}) for i in range(3)],
        )
        rows = (await db.execute(sa.select(sample))).mappings().all()
        assert all(OLD in row['body'] and row['detail'] == {'url': OLD, 'flag': False, 'number': 0} for row in rows), (
            rows
        )
        assert await db.scalar(sa.select(sa.func.count()).select_from(ResourceURL)) == 1
        assert (
            len(
                (
                    await db.execute(
                        sample.insert().returning(sample.c.id),
                        [dict(id=i, body=json.dumps(chain()), detail={'url': OLD}) for i in range(3, 6)],
                    )
                ).all()
            )
            == 3
        )
        assert all(OLD in value for value in (await db.execute(sa.select(sample.c.body))).scalars())


@pytest.mark.asyncio
@pytest.mark.parametrize('catalog_url', [OLD, NEW])
async def test_fresh_image_remembers_origin_for_later_model_history(database, catalog_url):
    async with database.begin() as db:
        await append(db, 'a')
        await db.execute(sa.update(ResourceURL).values(url=catalog_url, url_hash=digest(catalog_url)))

    renewed = NEW + '&renewed=1'

    async def action(name, **params):
        if name == 'get_version_info':
            return {'app_name': 'standard'}
        assert name == 'get_msg' and params == {'message_id': 42}
        return {'message': [{'type': 'image', 'data': {'file': 'one.jpg', 'url': renewed}}]}

    peer = SimpleNamespace(closed=False, call_action=AsyncMock(side_effect=action))
    peer.image_urls = OneBotImageURLs(peer)
    initial = chain()
    await refresh_images(database, peer, initial)
    assert initial[1]['url'] == catalog_url
    assert peer.image_urls.references[catalog_url] == (42, 'one.jpg')
    assert not any(call.args[0] == 'get_msg' for call in peer.call_action.call_args_list)

    async with database.begin() as db:
        assert await db.scalar(sa.select(ResourceURL.last_checked_at)) is None
        await db.execute(sa.update(ResourceURL).values(created_at=dt.datetime(2000, 1, 1)))
    history = [{'type': 'image_url', 'image_url': {'url': catalog_url}}]
    await refresh_images(database, peer, history)
    assert history[0]['image_url']['url'] == renewed
    assert sum(call.args[0] == 'get_msg' for call in peer.call_action.call_args_list) == 1
    async with database.connect() as db:
        assert renewed in await db.scalar(sa.select(EventLog.input_json))
        assert await db.scalar(sa.select(ResourceURL.last_checked_at)) is not None


@pytest.mark.asyncio
@pytest.mark.parametrize('converge', [False, True])
async def test_refresh_shared_identity_concurrency_and_half_hour(database, converge):
    async with database.begin() as db:
        await append(db, 'a')
        if converge:
            await append(db, 'b', NEW)
        await db.execute(sa.update(ResourceURL).values(created_at=dt.datetime(2000, 1, 1)))

    async def action(name, **params):
        await asyncio.sleep(0)
        if name == 'get_version_info':
            return {'app_name': 'other'}
        assert name == 'get_msg'
        return {'message': [{'type': 'image', 'data': {'file': 'one.jpg', 'url': NEW}}]}

    def peer():
        result = SimpleNamespace(closed=False, call_action=AsyncMock(side_effect=action))
        result.image_urls = OneBotImageURLs(result)
        return result

    peers = [peer(), peer()]
    batches = [chain(message_id=42), chain(message_id=43)]
    await asyncio.gather(*(refresh_images(database, p, batch) for p, batch in zip(peers, batches)))
    assert all(batch[1]['url'] == NEW for batch in batches)
    assert sum(call.args[0] == 'get_msg' for p in peers for call in p.call_action.call_args_list) == 1
    async with database.connect() as db:
        assert NEW in await db.scalar(sa.select(EventLog.input_json).where(EventLog.event_id == 'a'))
        assert (
            await db.scalar(sa.select(sa.func.count()).select_from(ResourceURL).where(ResourceURL.url.is_not(None)))
            == 1
        )
        assert OLD not in str((await db.execute(sa.select(ResourceURL.url))).scalars().all())
    # A fresh connection still reuses the persisted last-check time.
    replacement = peer()
    await refresh_images(database, replacement, chain(NEW))
    assert not any(call.args[0] == 'get_msg' for call in replacement.call_action.call_args_list)
    async with database.begin() as db:
        await db.execute(sa.update(ResourceURL).values(last_checked_at=dt.datetime(2000, 1, 1)))
    await refresh_images(database, replacement, chain(NEW))
    assert any(call.args[0] == 'get_msg' for call in replacement.call_action.call_args_list)


@pytest.mark.asyncio
async def test_distinct_urls_can_converge_concurrently(database):
    old_urls = [OLD, OLD + '&variant=two']
    async with database.begin() as db:
        for index, url in enumerate(old_urls):
            await append(db, str(index), url)
        await db.execute(sa.update(ResourceURL).values(created_at=dt.datetime(2000, 1, 1)))
    ready = asyncio.Event()
    entered = 0

    async def action(name, **params):
        nonlocal entered
        if name == 'get_version_info':
            return {'app_name': 'standard'}
        entered += 1
        if database.dialect.name == 'postgresql':
            if entered == 2:
                ready.set()
            await asyncio.wait_for(ready.wait(), 5)
        return {'message': [{'type': 'image', 'data': {'file': 'one.jpg', 'url': NEW}}]}

    peers = [SimpleNamespace(closed=False, call_action=AsyncMock(side_effect=action)) for _ in old_urls]
    for peer in peers:
        peer.image_urls = OneBotImageURLs(peer)
    await asyncio.gather(*(refresh_images(database, peer, chain(url)) for peer, url in zip(peers, old_urls)))
    async with database.connect() as db:
        assert all(NEW in value for value in (await db.execute(sa.select(EventLog.input_json))).scalars())
        assert (await db.execute(sa.select(ResourceURL.url).where(ResourceURL.url.is_not(None)))).scalars().all() == [
            NEW
        ]


@pytest.mark.asyncio
@pytest.mark.parametrize('outcome', ['unchanged', 'missing_origin', 'failure'])
async def test_only_successful_checks_advance_the_persisted_interval(database, outcome):
    async with database.begin() as db:
        await append(db, 'a')
        await db.execute(sa.update(ResourceURL).values(created_at=dt.datetime(2000, 1, 1)))

    async def action(name, **params):
        if name == 'get_version_info':
            return {'app_name': 'standard'}
        if outcome == 'failure':
            raise RuntimeError('upstream unavailable')
        return {'message': [{'type': 'image', 'data': {'file': 'one.jpg', 'url': OLD}}]}

    peer = SimpleNamespace(closed=False, call_action=AsyncMock(side_effect=action))
    peer.image_urls = OneBotImageURLs(peer)
    payload = chain() if outcome != 'missing_origin' else [{'type': 'image_url', 'image_url': {'url': OLD}}]
    if outcome == 'failure':
        with pytest.raises(RuntimeError, match='upstream unavailable'):
            await refresh_images(database, peer, payload)
    else:
        await refresh_images(database, peer, payload)
    async with database.connect() as db:
        assert (await db.scalar(sa.select(ResourceURL.last_checked_at)) is not None) == (outcome == 'unchanged')


@pytest.mark.asyncio
async def test_napcat_uses_key_ttl_instead_of_the_standard_interval(database):
    async with database.begin() as db:
        await append(db, 'a')
    generation = 0

    async def action(name, **params):
        nonlocal generation
        if name == 'get_version_info':
            return {'app_name': 'NapCat.Onebot'}
        assert name == 'nc_get_rkey'
        generation += 1
        return [{'type': 20, 'time': 1, 'ttl': 10**12, 'rkey': f'key{generation}'}]

    peer = SimpleNamespace(closed=False, call_action=AsyncMock(side_effect=action))
    peer.image_urls = OneBotImageURLs(peer)
    await refresh_images(database, peer, chain())
    async with database.connect() as db:
        checked = await db.scalar(sa.select(ResourceURL.last_checked_at))
        assert 'rkey=key1' in await db.scalar(sa.select(EventLog.input_json))
    await refresh_images(database, peer, chain())
    assert generation == 1
    async with database.connect() as db:
        assert await db.scalar(sa.select(ResourceURL.last_checked_at)) == checked
    peer.image_urls.keys[20] = ('key1', 0)
    await refresh_images(database, peer, chain())
    assert generation == 2
    async with database.connect() as db:
        assert 'rkey=key2' in await db.scalar(sa.select(EventLog.input_json))


@pytest.mark.asyncio
async def test_index_migration_preserves_primary_key_unique_hash_and_payload(database):
    migration = importlib.import_module('langbot.pkg.persistence.alembic.versions.0041_resource_urls')
    removed = {'ix_resource_urls_canonical_id', 'ix_resource_urls_last_checked'}

    def indexes(sync):
        return {index['name'] for index in sa.inspect(sync).get_indexes('resource_urls')}

    def upgrade(sync):
        with Operations.context(MigrationContext.configure(sync)):
            migration.upgrade()

    def create_legacy_indexes(sync):
        operations = Operations(MigrationContext.configure(sync))
        operations.create_index('ix_resource_urls_canonical_id', 'resource_urls', ['canonical_id'])
        operations.create_index('ix_resource_urls_last_checked', 'resource_urls', ['last_checked_at'])

    async with database.begin() as db:
        await append(db, 'a')
        assert removed.isdisjoint(await db.run_sync(indexes))
        # Recreate the schema deployed before the indexes were removed.
        await db.run_sync(create_legacy_indexes)
        assert removed <= await db.run_sync(indexes)
        await db.run_sync(upgrade)
        await db.run_sync(upgrade)
        assert removed.isdisjoint(await db.run_sync(indexes))
        primary_key = await db.run_sync(lambda sync: sa.inspect(sync).get_pk_constraint('resource_urls'))
        assert primary_key['constrained_columns'] == ['id']
        constraints = await db.run_sync(lambda sync: sa.inspect(sync).get_unique_constraints('resource_urls'))
        assert any(constraint['column_names'] == ['url_hash'] for constraint in constraints)
        assert OLD in await db.scalar(sa.select(EventLog.input_json))


@pytest.mark.asyncio
async def test_migration_preserves_source_creation_and_downgrade(database):
    migration = importlib.import_module('langbot.pkg.persistence.alembic.versions.0041_resource_urls')
    async with database.begin() as db:
        await append(db, 'newer')
        historical = sa.Table(
            'monitoring_llm_calls',
            sa.MetaData(),
            sa.Column('id', sa.String, primary_key=True),
            sa.Column('details', sa.JSON),
        )
        await db.run_sync(historical.create)
        await db.execute(historical.insert().values(id='old', details={'url': OLD, 'flag': False}))
        # Simulate a historical write before catalog normalization existed.
        await db.execute(
            sa.text(
                'INSERT INTO event_log (event_id,event_type,source,input_json,created_at) '
                "VALUES ('old','message.received','platform',:payload,'2000-01-01 00:00:00')"
            ),
            {'payload': json.dumps(chain())},
        )

        def upgrade(sync):
            with Operations.context(MigrationContext.configure(sync)):
                migration.upgrade()
                migration.upgrade()

        await db.run_sync(upgrade)
        assert OLD in await db.scalar(sa.select(EventLog.input_json))
        assert (await db.scalar(sa.select(ResourceURL.created_at))).year == 2000
        assert OLD not in await db.scalar(sa.text('SELECT input_json FROM event_log'))
        assert await db.scalar(sa.select(MonitoringLLMCall.details)) == {'url': OLD, 'flag': False}
        assert 'langbot-resource://' in str(await db.scalar(sa.select(historical.c.details)))

        def downgrade(sync):
            with Operations.context(MigrationContext.configure(sync)):
                migration.downgrade()

        await db.run_sync(downgrade)
        assert OLD in await db.scalar(sa.text('SELECT input_json FROM event_log'))
        assert await db.scalar(sa.select(historical.c.details)) == {'url': OLD, 'flag': False}
        # The same engine can write and read literal payloads after downgrade.
        await append(db, 'after', NEW)
        assert NEW in await db.scalar(sa.select(EventLog.input_json).where(EventLog.event_id == 'after'))
