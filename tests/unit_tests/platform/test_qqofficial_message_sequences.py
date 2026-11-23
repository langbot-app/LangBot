import asyncio
import json
import time
from types import SimpleNamespace
from unittest.mock import AsyncMock

import httpx
import pytest
import pytest_asyncio

import langbot.pkg.core.app  # noqa: F401
from langbot.libs.qq_official_api.api import QQOfficialClient
from langbot.libs.qq_official_api.qqofficialevent import QQOfficialEvent
from langbot.pkg.platform.adapters.qqofficial.adapter import QQOfficialAdapter
from langbot.pkg.platform.adapters.qqofficial.event_converter import QQOfficialEventConverter
from langbot.pkg.platform.adapters.qqofficial.message_converter import QQOfficialMessageConverter
from langbot.pkg.platform.sources.qqofficial import QQOfficialAdapter as LegacyQQOfficialAdapter
from langbot_plugin.api.entities.builtin.platform import message


@pytest_asyncio.fixture
async def captured_client():
    requests = []

    async def respond(request):
        await asyncio.sleep(0)
        requests.append((request.url.path, json.loads(request.content)))
        return httpx.Response(200, json={'id': 'reply', 'file_info': 'uploaded-media'})

    client = QQOfficialClient('fixture-secret', '', 'fixture-app', AsyncMock())
    client.access_token = 'fixture-token'
    client.access_token_expiry_time = time.time() + 3600
    for timeout in (None, 30, 120):
        client._http_clients[timeout] = httpx.AsyncClient(transport=httpx.MockTransport(respond))
    try:
        yield client, requests
    finally:
        await client.close()


@pytest.mark.asyncio
@pytest.mark.parametrize('adapter_class', [QQOfficialAdapter, LegacyQQOfficialAdapter])
@pytest.mark.parametrize('markdown', [False, True])
@pytest.mark.parametrize('event_type', ['C2C_MESSAGE_CREATE', 'GROUP_AT_MESSAGE_CREATE', 'GROUP_MESSAGE_CREATE'])
async def test_segmented_replies_share_sequences(captured_client, adapter_class, markdown, event_type):
    client, requests = captured_client
    adapter = adapter_class.model_construct(
        bot=client, config={'enable-markdown-rendering': markdown}, logger=AsyncMock()
    )
    source = SimpleNamespace(
        source_platform_object=QQOfficialEvent(
            {'t': event_type, 'd_id': 'source-one', 'user_openid': 'user-one', 'group_openid': 'group-one'}
        )
    )
    await adapter.reply_message(
        source,
        message.MessageChain(
            [message.At(target='user-one'), message.Plain(text='first'), message.Plain(text='second')]
        ),
    )
    await adapter.reply_message(source, message.MessageChain([message.Plain(text='follow-up')]))

    payloads = [body for _, body in requests]
    expected_sequences = [1, 2] if adapter_class is QQOfficialAdapter else [1, 2, 3]
    assert [body['msg_seq'] for body in payloads] == expected_sequences
    assert all(body['msg_id'] == 'source-one' for body in payloads)
    assert all(body['msg_type'] == (2 if markdown else 0) for body in payloads)
    expected_path = (
        '/v2/users/user-one/messages' if event_type == 'C2C_MESSAGE_CREATE' else '/v2/groups/group-one/messages'
    )
    assert all(path == expected_path for path, _ in requests)
    texts = [body['markdown']['content'] if markdown else body['content'] for body in payloads]
    if adapter_class is QQOfficialAdapter:
        mention = '@user-one' if event_type == 'C2C_MESSAGE_CREATE' else '<qqbot-at-user id="user-one" />'
        if event_type != 'C2C_MESSAGE_CREATE' and not markdown:
            mention = ''
        assert texts == [f'{mention}firstsecond', 'follow-up']
    else:
        assert texts == ['first', 'second', 'follow-up']


@pytest.mark.asyncio
@pytest.mark.parametrize('markdown', [False, True])
@pytest.mark.parametrize('event_type', ['GROUP_AT_MESSAGE_CREATE', 'GROUP_MESSAGE_CREATE'])
async def test_group_reply_mentions_follow_render_mode_in_one_message(captured_client, markdown, event_type):
    client, requests = captured_client
    adapter = QQOfficialAdapter.model_construct(
        bot=client, config={'enable-markdown-rendering': markdown}, logger=AsyncMock()
    )
    source = await QQOfficialEventConverter().target2yiri(
        QQOfficialEvent(
            {
                't': event_type,
                'd_id': 'source-one',
                'member_openid': 'sender-openid',
                'group_openid': 'group-one',
                'content': 'hello',
                'timestamp': '2026-10-28T10:00:00+0000',
            }
        )
    )
    await adapter.reply_message(
        source,
        message.MessageChain(
            [
                message.At(target=source.sender.id, display='Alice'),
                message.Plain(text=' hello'),
                message.Plain(text='!'),
            ]
        ),
    )

    assert len(requests) == 1
    path, payload = requests[0]
    assert path == '/v2/groups/group-one/messages'
    assert payload['msg_id'] == 'source-one'
    assert payload['msg_seq'] == 1
    content = payload['markdown']['content'] if markdown else payload['content']
    assert content == ('<qqbot-at-user id="sender-openid" /> hello!' if markdown else ' hello!')
    assert payload['msg_type'] == (2 if markdown else 0)


@pytest.mark.asyncio
async def test_merged_text_preserves_media_order_and_sequences(captured_client):
    client, requests = captured_client
    adapter = QQOfficialAdapter.model_construct(bot=client, config={}, logger=AsyncMock())
    source = SimpleNamespace(
        source_platform_object=QQOfficialEvent(
            {'t': 'GROUP_MESSAGE_CREATE', 'd_id': 'source-one', 'group_openid': 'group-one'}
        )
    )
    await adapter.reply_message(
        source,
        message.MessageChain(
            [
                message.At(target='sender'),
                message.Plain(text=' image:'),
                message.Image(url='https://example.test/image.png'),
                message.Plain(text='after'),
                message.Plain(text=' image'),
            ]
        ),
    )
    payloads = [body for path, body in requests if path.endswith('/messages')]
    assert [body['msg_seq'] for body in payloads] == [1, 2, 3]
    assert [body['msg_type'] for body in payloads] == [0, 7, 0]
    assert payloads[0]['content'] == ' image:'
    assert payloads[2]['content'] == 'after image'


@pytest.mark.asyncio
@pytest.mark.parametrize('markdown', [False, True])
async def test_group_send_mentions_follow_render_mode(captured_client, markdown):
    client, requests = captured_client
    adapter = QQOfficialAdapter.model_construct(
        bot=client, config={'enable-markdown-rendering': markdown}, logger=AsyncMock()
    )
    await adapter.send_message(
        'group',
        'group-one',
        message.MessageChain([message.At(target='sender'), message.Plain(text='hello')]),
    )
    assert len(requests) == 1
    payload = requests[0][1]
    assert payload['msg_type'] == (2 if markdown else 0)
    content = payload['markdown']['content'] if markdown else payload['content']
    assert content == ('<qqbot-at-user id="sender" />hello' if markdown else 'hello')


@pytest.mark.asyncio
async def test_plain_group_mention_only_does_not_send_empty_message(captured_client):
    client, requests = captured_client
    adapter = QQOfficialAdapter.model_construct(bot=client, config={}, logger=AsyncMock())
    await adapter.send_message('group', 'group-one', message.MessageChain([message.At(target='sender')]))
    assert requests == []


@pytest.mark.asyncio
@pytest.mark.parametrize('markdown', [False, True])
@pytest.mark.parametrize('wrapper', ['quote', 'forward'])
async def test_nested_mentions_preserve_render_mode(markdown, wrapper):
    nested = message.MessageChain([message.At(target='sender'), message.Plain(text='hello')])
    component = (
        message.Quote(origin=nested)
        if wrapper == 'quote'
        else message.Forward(node_list=[message.ForwardMessageNode(message_chain=nested)])
    )
    payloads = await QQOfficialMessageConverter.yiri2target(
        message.MessageChain([component]), 'group', use_markdown=markdown
    )
    assert payloads == [{'type': 'text', 'content': '<qqbot-at-user id="sender" />hello' if markdown else 'hello'}]


@pytest.mark.asyncio
async def test_mentions_escape_ids_without_using_display_names():
    payloads = await QQOfficialMessageConverter.yiri2target(
        message.MessageChain([message.At(target='bad"/><qqbot-at-everyone', display='Alice')]),
        'group',
        use_markdown=True,
    )
    assert payloads == [{'type': 'text', 'content': '<qqbot-at-user id="bad&quot;/&gt;&lt;qqbot-at-everyone" />'}]


@pytest.mark.asyncio
async def test_empty_text_does_not_emit_an_empty_message(captured_client):
    client, requests = captured_client
    adapter = QQOfficialAdapter.model_construct(bot=client, config={}, logger=AsyncMock())
    await adapter.send_message('group', 'group-one', message.MessageChain([message.Plain(text='')]))
    assert requests == []


@pytest.mark.asyncio
@pytest.mark.parametrize('target_type', ['channel', 'guild'])
async def test_channel_mentions_are_native_and_not_split(captured_client, target_type):
    client, requests = captured_client
    adapter = QQOfficialAdapter.model_construct(bot=client, config={}, logger=AsyncMock())
    await adapter.send_message(
        target_type,
        'channel-one',
        message.MessageChain([message.At(target='member'), message.AtAll(), message.Plain(text=' hello')]),
    )
    assert len(requests) == 1
    assert requests[0][1]['content'] == '<qqbot-at-user id="member" /><qqbot-at-everyone /> hello'


@pytest.mark.asyncio
@pytest.mark.parametrize('target_type', ['c2c', 'group'])
async def test_text_media_markdown_and_keyboard_share_sequences(captured_client, target_type):
    client, requests = captured_client
    text_sender = client.send_private_text_msg if target_type == 'c2c' else client.send_group_text_msg
    markdown_sender = client.send_private_markdown_msg if target_type == 'c2c' else client.send_group_markdown_msg
    await text_sender('target', 'first', msg_id='source')
    await client.send_image_msg(target_type, 'target', file_url='https://example.test/image.png', msg_id='source')
    await markdown_sender('target', '**second**', msg_id='source')
    await client.send_markdown_keyboard(target_type, 'target', 'third', {}, msg_id='source')
    await text_sender('target', 'fourth', msg_id='source')

    payloads = [body for path, body in requests if path.endswith('/messages')]
    assert [body['msg_seq'] for body in payloads] == [1, 2, 3, 4, 5]
    assert [body['msg_type'] for body in payloads] == [0, 7, 2, 2, 0]
    assert all(body['msg_id'] == 'source' for body in payloads)


@pytest.mark.asyncio
async def test_concurrent_replies_do_not_reuse_sequences(captured_client):
    client, requests = captured_client
    await asyncio.gather(*(client.send_group_text_msg('group', str(index), msg_id='source') for index in range(20)))
    assert sorted(body['msg_seq'] for _, body in requests) == list(range(1, 21))


@pytest.mark.asyncio
async def test_explicit_stream_sequence_is_preserved_and_reserved(captured_client):
    client, requests = captured_client
    await client.send_stream_msg('user', 'first', event_id='source', msg_id='source', msg_seq=7)
    await client.send_stream_msg(
        'user', 'final', event_id='source', msg_id='source', msg_seq=7, stream_msg_id='reply', input_state=10
    )
    await client.send_private_text_msg('user', 'follow-up', msg_id='source')
    await client.send_private_markdown_msg('user', '**explicit**', msg_id='source', msg_seq=10)
    await client.send_private_text_msg('user', 'automatic', msg_id='source')
    assert [body['msg_seq'] for _, body in requests] == [7, 7, 8, 10, 11]


@pytest.mark.asyncio
async def test_failed_send_does_not_reuse_sequence(captured_client):
    client, requests = captured_client
    client._http_clients[None].post = AsyncMock(side_effect=httpx.ReadTimeout('response lost'))
    with pytest.raises(httpx.ReadTimeout):
        await client.send_group_text_msg('group', 'first', msg_id='source')
    await client.send_markdown_keyboard('group', 'group', 'retry', {}, msg_id='source')
    assert requests[0][1]['msg_seq'] == 2
