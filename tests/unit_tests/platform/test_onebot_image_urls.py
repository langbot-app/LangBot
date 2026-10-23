"""OneBot image refresh contracts without vendor accounts or image downloads."""

import asyncio
import copy
import datetime
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock
from urllib.parse import parse_qs, urlsplit

import pytest
import sqlalchemy as sa
from sqlalchemy.ext.asyncio import create_async_engine

from langbot.pkg.entity.persistence.resource_url import ResourceURL
from langbot.pkg.platform.adapters.aiocqhttp.image_urls import OneBotImageURLs, nt_image_type
from langbot.pkg.platform.image_urls import refresh_image_payload, refresh_model_images, refresh_history_items
from langbot_plugin.api.entities.builtin.provider.message import Message


def url(appid='1407', key='expired', fileid='resource'):
    return f'https://multimedia.nt.qq.com.cn/download?appid={appid}&fileid={fileid}&rkey={key}&spec=0'


def payload(*urls, message_id=42):
    return [{'type': 'Source', 'id': message_id}] + [
        {'type': 'Image', 'image_id': f'{index}.jpg', 'url': value} for index, value in enumerate(urls)
    ]


def connection(action):
    peer = SimpleNamespace(closed=False, call_action=AsyncMock(side_effect=action))
    peer.image_urls = OneBotImageURLs(peer)
    return peer


@pytest.mark.asyncio
async def test_napcat_ttl_concurrency_types_and_parameters(monkeypatch):
    now = [1000]
    monkeypatch.setattr('langbot.pkg.platform.adapters.aiocqhttp.image_urls.time.time', lambda: now[0])

    async def action(name, **params):
        await asyncio.sleep(0)
        if name == 'get_version_info':
            return {'app_name': 'NapCat.Onebot'}
        assert name == 'nc_get_rkey' and not params
        # Order is deliberately reversed; TTL may be serialized as a string.
        return [
            {'type': 20, 'time': now[0], 'ttl': '100', 'rkey': '&rkey=group+/='},
            {'type': 10, 'time': now[0], 'ttl': 200, 'rkey': 'private'},
        ]

    peer = connection(action)
    batches = [payload(url(), url('1406')) for _ in range(10)]
    await asyncio.gather(*(peer.image_urls.refresh(batch) for batch in batches))
    assert peer.call_action.await_count == 2
    for batch in batches:
        assert parse_qs(urlsplit(batch[1]['url']).query) == {
            'appid': ['1407'],
            'fileid': ['resource'],
            'rkey': ['group+/='],
            'spec': ['0'],
        }
        assert parse_qs(urlsplit(batch[2]['url']).query)['rkey'] == ['private']
    now[0] = 1100
    escaped = payload(url('1406') + '&other=a%2fb+z&empty=')
    await peer.image_urls.refresh(escaped)
    assert '&other=a%2fb+z&empty=' in escaped[1]['url']
    await peer.image_urls.refresh(payload(url('1406')))
    assert peer.call_action.await_count == 2
    await peer.image_urls.refresh(payload(url()))
    assert peer.call_action.await_count == 3


@pytest.mark.parametrize(
    'value',
    [
        url('9999'),
        url().replace('fileid=resource&', ''),
        url() + '&appid=1407',
        url().replace('multimedia.nt.qq.com.cn', 'multimedia.nt.qq.com.cn.evil.test'),
        url().replace('https://', 'https://user@'),
        'data:image/png;base64,AA==',
    ],
)
def test_only_supported_qq_resources_are_rewritten(value):
    assert nt_image_type(value) is None


@pytest.mark.asyncio
async def test_other_implementation_uses_original_id_and_caches_messages():
    async def action(name, **params):
        if name == 'get_version_info':
            return {'app_name': 'another-onebot'}
        assert name == 'get_msg' and params == {'message_id': 42}
        return {
            'message': [
                {'type': 'image', 'data': {'file': '1.jpg', 'url': 'https://example.test/new-1'}},
                {'type': 'image', 'data': {'file': '0.jpg', 'url': 'https://example.test/new-0'}},
            ]
        }

    peer = connection(action)
    batch = payload('https://example.test/old-0', 'https://example.test/old-1')
    await peer.image_urls.refresh(batch)
    assert [node['url'] for node in batch[1:]] == ['https://example.test/new-0', 'https://example.test/new-1']
    # Provider contents have no source identity; the connection remembers the association.
    model_input = [{'type': 'image_url', 'image_url': {'url': batch[1]['url']}}]
    await peer.image_urls.refresh(model_input)
    assert peer.call_action.await_count == 2
    peer.image_urls.messages.clear()
    peer.image_urls.urls.clear()
    await peer.image_urls.refresh(model_input)
    assert peer.call_action.await_count == 3


@pytest.mark.asyncio
async def test_aggregated_messages_keep_each_original_source():
    async def action(name, **params):
        if name == 'get_version_info':
            return {'app_name': 'another-onebot'}
        assert name == 'get_msg'
        message_id = params['message_id']
        return {'message': f'[CQ:image,file=0.jpg,url=https://example.test/new-{message_id}]'}

    peer = connection(action)
    batch = payload('https://example.test/old-42', message_id=42) + payload(
        'https://example.test/old-43', message_id=43
    )
    await peer.image_urls.refresh(batch)
    assert batch[1]['url'] == 'https://example.test/new-42'
    assert batch[3]['url'] == 'https://example.test/new-43'
    assert peer.call_action.await_count == 3


@pytest.fixture
async def catalog():
    engine = create_async_engine('sqlite+aiosqlite:///:memory:')
    async with engine.begin() as db:
        await db.run_sync(ResourceURL.__table__.create)
    yield engine
    await engine.dispose()


def application(peer, engine, workspace='workspace'):
    bot = SimpleNamespace(
        workspace_uuid=workspace,
        enable=True,
        bot_entity=SimpleNamespace(adapter='onebot-v11'),
        adapter=SimpleNamespace(bot=SimpleNamespace(connection=peer)),
    )
    ap = SimpleNamespace(
        platform_mgr=SimpleNamespace(resolve_public_bot=AsyncMock(return_value=bot)),
        persistence_mgr=SimpleNamespace(get_db_engine=lambda: engine),
        logger=Mock(),
    )
    return ap, bot


@pytest.mark.asyncio
async def test_scope_failure_backoff_preserves_current_url(catalog):
    peer = connection(lambda *_args, **_kwargs: {'app_name': 'NapCat.Onebot'})
    ap, bot = application(peer, catalog)
    original = payload(url())
    saved = copy.deepcopy(original)
    assert await refresh_image_payload(ap, 'foreign', 'bot', original) is original
    peer.call_action.assert_not_awaited()
    peer.call_action.side_effect = RuntimeError('private credentials must not be logged')
    assert await refresh_image_payload(ap, 'workspace', 'bot', original) is original
    assert await refresh_image_payload(ap, 'workspace', 'bot', original) == original
    assert peer.call_action.await_count == 1
    assert original == saved
    assert 'private credentials' not in str(ap.logger.warning.call_args)
    bot.adapter.bot.connection = None
    assert await refresh_image_payload(ap, 'workspace', 'bot', original) is original


@pytest.mark.asyncio
async def test_model_reuse_refreshes_with_current_keys_without_mutating_messages(catalog):
    async def action(name, **_params):
        if name == 'get_version_info':
            return {'app_name': 'NapCat.Onebot'}
        return [{'type': 20, 'time': 1, 'ttl': 10**12, 'rkey': '&rkey=current'}]

    peer = connection(action)
    ap, _ = application(peer, catalog)
    messages = [Message(role='user', content=[{'type': 'image_url', 'image_url': {'url': url()}}])]
    context = SimpleNamespace(workspace_uuid='workspace')
    query = SimpleNamespace(bot_uuid='bot')
    refreshed = await refresh_model_images(ap, context, query, messages)
    assert 'rkey=current' in refreshed[0].content[0].image_url.url
    assert 'rkey=expired' in messages[0].content[0].image_url.url
    await refresh_model_images(ap, context, query, messages)
    assert peer.call_action.await_count == 2
    # A new connection starts with no identity or credentials.
    replacement = connection(action)
    assert replacement.image_urls.app_name is None and replacement.image_urls.keys == {}


@pytest.mark.asyncio
async def test_disconnected_peer_cannot_return_refreshed_result(catalog):
    async def action(name, **_params):
        if name == 'get_version_info':
            return {'app_name': 'NapCat.Onebot'}
        bot.adapter.bot.connection = None
        return [{'type': 20, 'time': 1, 'ttl': 10**12, 'rkey': 'new'}]

    peer = connection(action)
    ap, bot = application(peer, catalog)
    original = payload(url())
    assert await refresh_image_payload(ap, 'workspace', 'bot', original) is original
    async with catalog.connect() as db:
        assert await db.scalar(sa.select(ResourceURL.url)) == url()


@pytest.mark.asyncio
async def test_history_recovers_scoped_origins_and_updates_shared_url(catalog):
    from langbot.pkg.entity.persistence.event_log import EventLog

    engine = catalog
    original = payload('https://example.test/old')
    metadata = json.dumps({'input_event': {'message_chain': original}})
    async with engine.begin() as db:
        await db.run_sync(EventLog.__table__.create)
        await db.execute(
            sa.insert(EventLog).values(
                event_id='event',
                event_type='message.received',
                source='platform',
                bot_id='bot',
                workspace_id='workspace',
                metadata_json=metadata,
            )
        )
        await db.execute(sa.update(ResourceURL).values(created_at=datetime.datetime(2000, 1, 1)))

    async def execute(statement):
        async with engine.connect() as db:
            return await db.execute(statement)

    async def action(name, **params):
        if name == 'get_version_info':
            return {'app_name': 'standard-peer'}
        assert params == {'message_id': 42}
        return {'message': [{'type': 'image', 'data': {'file': '0.jpg', 'url': 'https://example.test/new'}}]}

    peer = connection(action)
    ap, _ = application(peer, catalog)
    ap.persistence_mgr.execute_async = execute
    item = {
        'bot_id': 'bot',
        'workspace_id': 'workspace',
        'event_id': 'event',
        'content_json': {'content': [{'type': 'image_url', 'image_url': {'url': 'https://example.test/old'}}]},
    }
    try:
        await refresh_history_items(ap, 'foreign', 'bot', [item])
        peer.call_action.assert_not_awaited()
        await refresh_history_items(ap, 'workspace', 'bot', [item])
        assert item['content_json']['content'][0]['image_url']['url'] == 'https://example.test/new'
        result = await execute(sa.select(EventLog.metadata_json))
        assert 'https://example.test/new' in result.scalar_one()
        async with engine.connect() as db:
            assert 'langbot-resource://' in await db.scalar(sa.text('SELECT metadata_json FROM event_log'))
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_inline_and_local_media_do_not_call_peer():
    peer = connection(None)
    for value in ('/api/v1/files/media/image.png', 'data:image/png;base64,AA=='):
        await peer.image_urls.refresh(payload(value))
    peer.call_action.assert_not_awaited()
