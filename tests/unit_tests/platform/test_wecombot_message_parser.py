from types import SimpleNamespace
from unittest.mock import ANY, AsyncMock

import pytest

import langbot.pkg.core.app  # noqa: F401
from langbot.libs.wecom_ai_bot_api import api


pytestmark = pytest.mark.asyncio


@pytest.fixture
def downloads(monkeypatch):
    download = AsyncMock(return_value=(b'hello', 'downloaded.txt'))
    monkeypatch.setattr(api, 'download_encrypted_file', download)
    return download


def logger():
    return SimpleNamespace(warning=AsyncMock())


@pytest.mark.parametrize('size', [5 * 1024 * 1024 - 1, 5 * 1024 * 1024, 5 * 1024 * 1024 + 1])
@pytest.mark.parametrize('kind', ['file', 'voice', 'video'])
async def test_mixed_media_download_limit_and_aliases(downloads, kind, size):
    info = {'url': 'https://media.test/item', 'aeskey': 'item-key', 'size': size, 'fileid': 'f1', 'md5': 'm1'}
    message = {'msgtype': 'mixed', 'mixed': {'msg_item': [{'msgtype': kind, kind: info}]}}

    result = await api.parse_wecom_bot_message(message, 'platform-key', logger())

    media = result[kind]
    assert media['filesize'] == size
    assert media['sdkfileid'] == 'f1'
    assert media['md5sum'] == 'm1'
    assert result[kind + 's'] == [media]
    assert result['attachments'] == message['mixed']['msg_item']
    if size <= 5 * 1024 * 1024:
        downloads.assert_awaited_once_with('https://media.test/item', 'item-key', ANY)
        assert media['base64'] == 'data:application/octet-stream;base64,aGVsbG8='
        if kind == 'file':
            assert media['filename'] == 'downloaded.txt'
    else:
        downloads.assert_not_awaited()
        assert 'base64' not in media


@pytest.mark.parametrize('kind', ['file', 'voice', 'video'])
async def test_main_and_quote_media_keep_distinct_url_policy(downloads, kind):
    info = {'url': 'https://media.test/item', 'aeskey': 'item-key', 'name': 'named', 'content': 'speech'}
    result = await api.parse_wecom_bot_message(
        {'msgtype': kind, kind: info, 'quote': {'msgtype': kind, kind: info}},
        'platform-key',
        logger(),
    )

    downloads.assert_not_awaited()
    if kind == 'voice':
        assert result['voice']['url'] == 'https://media.test/item'
        assert result['quote']['voice']['url'] == 'https://media.test/item?aeskey=item-key'
        assert result['content'] == result['quote']['content'] == 'speech'
    else:
        assert result[kind]['download_url'] == 'https://media.test/item?aeskey=item-key'
        assert result['quote'][kind]['download_url'] == 'https://media.test/item?aeskey=item-key'
        assert result[kind]['filename'] == 'named'


async def test_mixed_order_sender_metadata_and_quoted_mixed_policy(downloads):
    items = [
        {'msgtype': 'text', 'text': {'content': 'first'}},
        {'msgtype': 'voice', 'voice': {'url': 'https://media.test/voice', 'content': 'second'}},
        {'msgtype': 'image', 'image': {'url': 'https://media.test/image'}},
        {'msgtype': 'image', 'image': {'url': 'https://media.test/image-two'}},
        {'msgtype': 'file', 'file': {'fileurl': 'https://media.test/file', 'name': 'kept.txt'}},
        {'msgtype': 'file', 'file': {'url': 'https://media.test/file-two', 'name': 'second.txt'}},
        {'msgtype': 'video', 'video': {'url': 'https://media.test/video'}},
        {'msgtype': 'link', 'link': {'title': 'link'}},
    ]
    result = await api.parse_wecom_bot_message(
        {
            'msgtype': 'mixed',
            'mixed': {'msg_item': items},
            'quote': {'msgtype': 'mixed', 'mixed': {'msg_item': items}},
            'from': {'userid': 'user', 'alias': 'alias'},
            'chattype': 'group',
            'chatid': 'group',
            'chatname': 'named group',
            'msgid': 'm1',
            'aibotid': 'b1',
        },
        'platform-key',
        logger(),
    )

    assert result['content'] == 'first second'
    assert result['quote']['content'] == 'first'
    assert result['images'] == result['quote']['images'] == ['data:application/octet-stream;base64,aGVsbG8='] * 2
    assert result['picurl'] == result['images'][0]
    assert result['file'] == result['files'][0]
    assert [file['filename'] for file in result['files']] == ['kept.txt', 'second.txt']
    assert [file['filename'] for file in result['quote']['files']] == ['kept.txt', 'second.txt']
    assert result['quote']['file']['download_url'] == 'https://media.test/file'
    assert 'base64' not in result['quote']['file']
    assert 'voice' not in result['quote'] and 'video' not in result['quote'] and 'link' not in result['quote']
    assert {key: result[key] for key in ['userid', 'username', 'chatid', 'chatname', 'msgid', 'aibotid']} == {
        'userid': 'user',
        'username': 'alias',
        'chatid': 'group',
        'chatname': 'named group',
        'msgid': 'm1',
        'aibotid': 'b1',
    }
    assert [call.args[:2] for call in downloads.await_args_list] == [
        ('https://media.test/voice', 'platform-key'),
        ('https://media.test/image', 'platform-key'),
        ('https://media.test/image-two', 'platform-key'),
        ('https://media.test/file', 'platform-key'),
        ('https://media.test/file-two', 'platform-key'),
        ('https://media.test/video', 'platform-key'),
        ('https://media.test/image', 'platform-key'),
        ('https://media.test/image-two', 'platform-key'),
    ]


@pytest.mark.parametrize('missing_key', [True, False])
async def test_unavailable_image_is_not_fabricated(downloads, missing_key):
    downloads.return_value = (None, None)
    log = logger()
    result = await api.parse_wecom_bot_message(
        {'msgtype': 'image', 'image': {'url': 'https://media.test/image'}},
        '' if missing_key else 'platform-key',
        log,
    )
    assert 'images' not in result and 'picurl' not in result
    if missing_key:
        downloads.assert_not_awaited()
        log.warning.assert_awaited_once()
    else:
        downloads.assert_awaited_once()


async def test_unknown_type_preserves_raw_message(downloads):
    message = {'msgtype': 'future', 'payload': {'unchanged': True}}
    result = await api.parse_wecom_bot_message(message, 'platform-key', logger())
    assert result['raw_msg'] is message
    downloads.assert_not_awaited()
