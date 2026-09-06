from types import SimpleNamespace

import pytest

from langbot.pkg.platform.sources.mattermost import (
    MattermostAdapter,
    MattermostEventConverter,
    MattermostMessageConverter,
    _normalize_server_url,
    _websocket_url,
)
import langbot_plugin.api.entities.builtin.platform.events as platform_events
import langbot_plugin.api.entities.builtin.platform.message as platform_message


class StubLogger:
    async def info(self, *_args, **_kwargs):
        pass

    async def error(self, *_args, **_kwargs):
        pass


def _adapter() -> MattermostAdapter:
    return MattermostAdapter.model_construct(
        config={'enable_stream_reply': True},
        logger=StubLogger(),
        server_url='https://mattermost.example.com',
        access_token='secret',
        bot_account_id='bot-id',
        bot_username='langbot',
        session=None,
        listeners={},
        channel_cache={},
        stream_post_ids={},
        _running=False,
    )


def test_server_and_websocket_urls_preserve_subpath():
    server_url = _normalize_server_url('https://example.com/chat/')
    assert server_url == 'https://example.com/chat'
    assert _websocket_url(server_url) == 'wss://example.com/chat/api/v4/websocket'

    with pytest.raises(ValueError, match='absolute HTTP'):
        _normalize_server_url('mattermost.example.com')


@pytest.mark.asyncio
async def test_converter_marks_and_removes_bot_mention():
    chain = await MattermostMessageConverter.target2yiri(
        {'id': 'post-1', 'create_at': 1_000, 'message': '@langbot hello'},
        'langbot',
    )

    assert any(isinstance(item, platform_message.At) for item in chain)
    assert any(isinstance(item, platform_message.Plain) and item.text == 'hello' for item in chain)


@pytest.mark.asyncio
async def test_event_converter_distinguishes_direct_and_group_channels():
    post = {'id': 'post-1', 'channel_id': 'channel-1', 'user_id': 'user-1', 'message': 'hello', 'create_at': 1_000}
    direct = await MattermostEventConverter.target2yiri(post, {'type': 'D'}, 'alice', 'langbot')
    group = await MattermostEventConverter.target2yiri(
        post,
        {'type': 'O', 'display_name': 'General'},
        'alice',
        'langbot',
    )

    assert isinstance(direct, platform_events.FriendMessage)
    assert isinstance(group, platform_events.GroupMessage)
    assert group.sender.group.name == 'General'


@pytest.mark.asyncio
async def test_send_to_person_creates_or_reuses_direct_channel(monkeypatch):
    adapter = _adapter()
    requests = []
    posted = []

    async def api_request(method, path, *, payload=None):
        requests.append((method, path, payload))
        return {'id': 'direct-channel', 'type': 'D'}

    async def post_message(channel_id, text, root_id=''):
        posted.append((channel_id, text, root_id))
        return {'id': 'post-1'}

    monkeypatch.setattr(adapter, '_api_request', api_request)
    monkeypatch.setattr(adapter, '_post_message', post_message)

    await adapter.send_message('person', 'user-1', platform_message.MessageChain([platform_message.Plain(text='hello')]))

    assert requests == [('POST', '/channels/direct', {'user_ids': ['bot-id', 'user-1']})]
    assert posted == [('direct-channel', 'hello', '')]


@pytest.mark.asyncio
async def test_reply_keeps_existing_thread(monkeypatch):
    adapter = _adapter()
    posted = []

    async def post_message(channel_id, text, root_id=''):
        posted.append((channel_id, text, root_id))
        return {'id': 'reply'}

    monkeypatch.setattr(adapter, '_post_message', post_message)
    event = platform_events.GroupMessage.model_construct(
        source_platform_object={
            'post': {'id': 'post-1', 'channel_id': 'channel-1', 'root_id': 'thread-root'},
            'channel': {'type': 'O'},
        }
    )

    await adapter.reply_message(event, platform_message.MessageChain([platform_message.Plain(text='reply')]))

    assert posted == [('channel-1', 'reply', 'thread-root')]


@pytest.mark.asyncio
async def test_stream_reply_updates_existing_post(monkeypatch):
    adapter = _adapter()
    adapter.stream_post_ids['response-1'] = 'post-1'
    requests = []

    async def api_request(method, path, *, payload=None):
        requests.append((method, path, payload))
        return {'id': 'post-1'}

    monkeypatch.setattr(adapter, '_api_request', api_request)
    message = SimpleNamespace(resp_message_id='response-1', tool_calls=None)

    await adapter.reply_message_chunk(
        SimpleNamespace(),
        message,
        platform_message.MessageChain([platform_message.Plain(text='complete')]),
        is_final=True,
    )

    assert requests == [('PUT', '/posts/post-1', {'id': 'post-1', 'message': 'complete'})]
    assert 'response-1' not in adapter.stream_post_ids


@pytest.mark.asyncio
async def test_posted_event_dispatches_listener(monkeypatch):
    adapter = _adapter()
    received = []

    async def get_channel(_channel_id):
        return {'type': 'D'}

    async def listener(event, _adapter):
        received.append(event)

    monkeypatch.setattr(adapter, '_get_channel', get_channel)
    adapter.register_listener(platform_events.FriendMessage, listener)

    await adapter._dispatch_post(
        {
            'data': {
                'sender_name': 'alice',
                'post': '{"id":"post-1","channel_id":"channel-1","user_id":"user-1","message":"hello","create_at":1000}',
            }
        }
    )

    assert len(received) == 1
    assert received[0].sender.nickname == 'alice'
