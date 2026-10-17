import base64
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from slack_sdk.web.async_slack_response import AsyncSlackResponse

from langbot.libs.slack_api.api import SlackClient
from langbot.libs.slack_api.media import attachment_bytes, download_media, send_chain
from langbot.libs.slack_api.slackevent import SlackEvent
from langbot.pkg.platform.adapters.slack.message_converter import SlackMessageConverter
from langbot_plugin.api.entities.builtin.platform import message as pm


def sdk_response(data):
    return AsyncSlackResponse(
        client=None,
        http_verb='POST',
        api_url='https://slack.com/api/test',
        req_args={},
        data=data,
        headers={},
        status_code=200,
    )


@pytest.mark.asyncio
@pytest.mark.parametrize('target_type,target_id', [('person', 'U123'), ('channel', 'C123')])
async def test_real_sdk_responses_for_text_and_attachment(target_type, target_id):
    client = SlackClient('test-token', '', SimpleNamespace(error=AsyncMock()), unified_mode=True)
    text_data = {'ok': True, 'channel': 'C123', 'message': {'ts': '1.2', 'bot_id': 'B123'}}
    file_data = {'ok': True, 'files': [{'id': 'F123'}]}
    client.client = SimpleNamespace(
        chat_postMessage=AsyncMock(return_value=sdk_response(text_data)),
        conversations_open=AsyncMock(return_value=sdk_response({'ok': True, 'channel': {'id': 'D123'}})),
        files_upload_v2=AsyncMock(return_value=sdk_response(file_data)),
    )
    result = await send_chain(
        client,
        target_type,
        target_id,
        pm.MessageChain(
            [
                pm.Plain(text='picture'),
                pm.File(name='image.png', base64='dGVzdA=='),
            ]
        ),
    )
    assert result['responses'] == [text_data, file_data]
    assert client.client.chat_postMessage.await_count == 1
    assert client.client.files_upload_v2.await_count == 1


def bot():
    return SimpleNamespace(
        bot_token='test-token',
        client=SimpleNamespace(
            conversations_open=AsyncMock(return_value={'ok': True, 'channel': {'id': 'D123'}}),
            files_upload_v2=AsyncMock(return_value={'ok': True, 'files': [{'id': 'F123'}]}),
        ),
        send_message_to_one=AsyncMock(return_value={'ok': True}),
        send_message_to_channel=AsyncMock(return_value={'ok': True}),
    )


@pytest.mark.asyncio
async def test_svg_base64_is_uploaded_to_dm_not_sent_as_filename():
    client = bot()
    svg = b'<svg xmlns="http://www.w3.org/2000/svg"/>'
    await send_chain(
        client,
        'person',
        'U123',
        pm.MessageChain(
            [
                pm.Plain(text='Here is the picture'),
                pm.File(name='moon.svg', base64=base64.b64encode(svg).decode()),
            ]
        ),
    )
    client.send_message_to_one.assert_awaited_once_with('Here is the picture', 'U123')
    client.client.conversations_open.assert_awaited_once_with(users=['U123'])
    client.client.files_upload_v2.assert_awaited_once_with(
        channel='D123', file=svg, filename='moon.svg', title='moon.svg'
    )


@pytest.mark.asyncio
async def test_multiple_attachments_to_channel_preserve_bytes_and_text_order(tmp_path):
    client = bot()
    path = tmp_path / 'notes.txt'
    path.write_bytes(b'hello')
    await send_chain(
        client,
        'channel',
        'C123',
        pm.MessageChain(
            [
                pm.Image(base64='data:image/png;base64,' + base64.b64encode(b'png bytes').decode()),
                pm.File(path=str(path)),
                pm.Plain(text='done'),
            ]
        ),
    )
    calls = client.client.files_upload_v2.await_args_list
    assert [c.kwargs['file'] for c in calls] == [b'png bytes', b'hello']
    assert [c.kwargs['filename'] for c in calls] == ['attachment.png', 'notes.txt']
    client.client.conversations_open.assert_not_awaited()
    client.send_message_to_channel.assert_awaited_once_with('done', 'C123')


@pytest.mark.asyncio
async def test_upload_failure_is_not_reported_as_success():
    client = bot()
    client.client.files_upload_v2.return_value = {'ok': False, 'error': 'missing_scope'}
    with pytest.raises(RuntimeError, match='missing_scope'):
        await send_chain(
            client,
            'channel',
            'C123',
            pm.MessageChain(
                [
                    pm.File(name='test.txt', base64='dGVzdA=='),
                ]
            ),
        )


@pytest.mark.asyncio
async def test_missing_attachment_data_fails_instead_of_faking_delivery():
    with pytest.raises(ValueError, match='no base64'):
        await attachment_bytes(pm.File(name='missing.txt'))


@pytest.mark.asyncio
async def test_local_bytes_take_priority_over_private_url():
    data, name = await attachment_bytes(
        pm.File(name='file.txt', url='https://files.slack.com/private', base64='dGVzdA==')
    )
    assert (data, name) == (b'test', 'file.txt')


@pytest.mark.asyncio
async def test_received_multiple_files_keep_type_and_authenticated_bytes():
    event = SlackEvent(
        {
            'event': {
                'channel_type': 'im',
                'text': 'attachments',
                'files': [
                    {'id': 'F1', 'name': 'a.png', 'mimetype': 'image/png', 'url_private': 'https://files.slack.com/a'},
                    {
                        'id': 'F2',
                        'name': 'b.pdf',
                        'mimetype': 'application/pdf',
                        'url_private': 'https://files.slack.com/b',
                    },
                ],
            }
        }
    )
    with patch(
        'langbot.pkg.platform.adapters.slack.message_converter.download_media',
        new=AsyncMock(return_value=(b'data', 'application/octet-stream')),
    ) as download:
        chain = await SlackMessageConverter.target2yiri(event, 'test-token')
    assert isinstance(chain[1], pm.Image)
    assert chain[1].base64 == 'data:image/png;base64,ZGF0YQ=='
    assert isinstance(chain[2], pm.File) and chain[2].name == 'b.pdf'
    assert chain[2].base64 == 'ZGF0YQ=='
    assert chain[3].text == 'attachments'
    assert download.await_count == 2


@pytest.mark.asyncio
@pytest.mark.parametrize(
    'url,authenticated',
    [
        ('https://files.slack.com/file', True),
        ('https://example.com/file', False),
        ('https://files.slack.com.evil.test/file', False),
    ],
)
async def test_download_credentials_are_scoped_to_slack(url, authenticated):
    response = SimpleNamespace(status=200, headers={'Content-Type': 'image/png'})
    context = AsyncMock()
    context.__aenter__.return_value = response
    with (
        patch('langbot.libs.slack_api.media.httpclient.get_session') as session,
        patch('langbot.libs.slack_api.media.httpclient.read_limited', new=AsyncMock(return_value=b'png')),
    ):
        session.return_value.get.return_value = context
        assert await download_media(url, 'test-token') == (b'png', 'image/png')
        kwargs = session.return_value.get.call_args.kwargs
        assert bool(kwargs['headers']) == authenticated
        if authenticated:
            assert kwargs['allow_redirects'] is False


@pytest.mark.asyncio
async def test_download_http_failure_is_visible():
    context = AsyncMock()
    context.__aenter__.return_value = SimpleNamespace(status=403)
    with patch('langbot.libs.slack_api.media.httpclient.get_session') as session:
        session.return_value.get.return_value = context
        with pytest.raises(ValueError, match='HTTP 403'):
            await download_media('https://files.slack.com/file', 'test-token')
