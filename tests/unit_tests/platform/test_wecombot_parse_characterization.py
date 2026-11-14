"""Behaviour contract for ``parse_wecom_bot_message`` (see #2633).

The parser feeds the WeCom adapter from an already-decrypted payload, so its
output shape is the adapter's input contract. These cases pin the observable
result of every branch, including the ordering-sensitive mixin and quote paths,
so the split into per-type parsers can be proven behaviour-preserving.
"""

from __future__ import annotations

import base64

import pytest

import langbot.pkg.core.app  # noqa: F401
from langbot.libs.wecom_ai_bot_api import api


class Logger:
    def __init__(self):
        self.warnings: list[str] = []
        self.errors: list[str] = []

    async def warning(self, message):
        self.warnings.append(message)

    async def error(self, message):
        self.errors.append(message)

    async def info(self, message):
        return None


BIG = 5 * 1024 * 1024 + 1
SMALL = 1024
AESKEY = 'platform-key'


@pytest.fixture
def downloaded(monkeypatch):
    """Record every encrypted download and serve deterministic plaintext."""
    calls: list[tuple[str, str]] = []

    async def fake_download(url, key, logger):
        calls.append((url, key))
        return f'bytes:{url}'.encode(), 'remote-name.bin'

    monkeypatch.setattr(api, 'download_encrypted_file', fake_download)
    return calls


def base(msgtype: str, **extra) -> dict:
    payload = {
        'msgtype': msgtype,
        'chattype': 'group',
        'msgid': 'msg-1',
        'from': {'userid': 'u1', 'alias': 'Alias', 'name': 'Name'},
        'chatid': 'c1',
        'chatname': 'Chat',
        'aibotid': 'bot-1',
    }
    payload.update(extra)
    return payload


def _data_uri(url: str) -> str:
    return 'data:application/octet-stream;base64,' + base64.b64encode(f'bytes:{url}'.encode()).decode()


@pytest.mark.asyncio
async def test_text_sets_content_and_envelope(downloaded):
    result = await api.parse_wecom_bot_message(base('text', text={'content': 'hello'}), AESKEY, Logger())
    assert result['content'] == 'hello'
    assert result['msgtype'] == 'text'
    assert result['type'] == 'group'
    assert result['userid'] == 'u1'
    assert result['username'] == 'Alias'
    assert result['chatid'] == 'c1'
    assert result['chatname'] == 'Chat'
    assert result['msgid'] == 'msg-1'
    assert result['aibotid'] == 'bot-1'
    assert downloaded == []


@pytest.mark.asyncio
async def test_username_falls_back_through_name_and_userid(downloaded):
    payload = base('text', text={'content': ''})
    payload['from'] = {'userid': 'u1', 'name': 'Name'}
    assert (await api.parse_wecom_bot_message(payload, AESKEY, Logger()))['username'] == 'Name'
    payload['from'] = {'userid': 'u1'}
    assert (await api.parse_wecom_bot_message(payload, AESKEY, Logger()))['username'] == 'u1'


@pytest.mark.asyncio
async def test_single_chat_has_no_chat_fields(downloaded):
    payload = base('text', text={'content': 'hi'}, chattype='single')
    result = await api.parse_wecom_bot_message(payload, AESKEY, Logger())
    assert result['type'] == 'single'
    assert 'chatid' not in result
    assert 'chatname' not in result


@pytest.mark.asyncio
async def test_markdown_prefers_markdown_then_text(downloaded):
    result = await api.parse_wecom_bot_message(base('markdown', markdown={'content': 'md'}), AESKEY, Logger())
    assert result['content'] == 'md'
    result = await api.parse_wecom_bot_message(base('markdown', text={'content': 'fallback'}), AESKEY, Logger())
    assert result['content'] == 'fallback'


@pytest.mark.asyncio
async def test_image_is_downloaded_and_exposed_as_data_uri(downloaded):
    result = await api.parse_wecom_bot_message(
        base('image', image={'url': 'https://x/i.png', 'aeskey': 'per-msg'}), AESKEY, Logger()
    )
    assert downloaded == [('https://x/i.png', 'per-msg')]
    assert result['picurl'] == _data_uri('https://x/i.png')
    assert result['images'] == [result['picurl']]


@pytest.mark.asyncio
async def test_small_voice_is_transcoded_with_length(downloaded):
    result = await api.parse_wecom_bot_message(
        base('voice', voice={'url': 'https://x/v.amr', 'filesize': SMALL, 'content': 'spoken'}),
        AESKEY,
        Logger(),
    )
    assert result['content'] == 'spoken'
    assert result['voice']['base64'].startswith('data:audio/')
    # Unknown formats cannot report a duration.
    assert result['voice'].get('length') is None
    assert result['voice']['url'] == 'https://x/v.amr'
    assert result['voice']['filesize'] == SMALL


@pytest.mark.asyncio
async def test_large_voice_is_not_downloaded(downloaded):
    result = await api.parse_wecom_bot_message(
        base('voice', voice={'url': 'https://x/v.amr', 'filesize': BIG}), AESKEY, Logger()
    )
    assert 'base64' not in result['voice']
    assert downloaded == []


@pytest.mark.asyncio
async def test_video_always_appends_aeskey_to_the_download_url(downloaded):
    result = await api.parse_wecom_bot_message(
        base('video', video={'url': 'https://x/v.mp4', 'aeskey': 'per-msg', 'filename': 'v.mp4'}),
        AESKEY,
        Logger(),
    )
    assert result['video']['download_url'] == 'https://x/v.mp4?aeskey=per-msg'
    assert result['video']['filename'] == 'v.mp4'
    assert downloaded == []


@pytest.mark.asyncio
async def test_file_exposes_encrypted_url_and_keeps_raw_payload(downloaded):
    raw = {'url': 'https://x/f.pdf', 'aeskey': 'per-msg', 'filename': 'f.pdf', 'filesize': SMALL}
    result = await api.parse_wecom_bot_message(base('file', file=raw), AESKEY, Logger())
    assert result['file']['download_url'] == 'https://x/f.pdf?aeskey=per-msg'
    assert result['file']['filename'] == 'f.pdf'
    assert result['file']['extra'] == raw
    assert downloaded == []


@pytest.mark.asyncio
async def test_link_joins_title_and_description_into_content(downloaded):
    result = await api.parse_wecom_bot_message(base('link', link={'title': 'T', 'digest': 'D'}), AESKEY, Logger())
    assert result['content'] == 'T\nD'
    assert result['link'] == {'title': 'T', 'digest': 'D'}


@pytest.mark.asyncio
async def test_mixed_keeps_per_kind_lists_and_attachments_in_order(downloaded):
    items = [
        {'msgtype': 'text', 'text': {'content': 'one'}},
        {'msgtype': 'image', 'image': {'url': 'https://x/i.png', 'aeskey': 'k'}},
        {'msgtype': 'file', 'file': {'url': 'https://x/f', 'aeskey': 'k', 'filename': 'f', 'filesize': SMALL}},
        {'msgtype': 'link', 'link': {'title': 'T', 'description': 'D'}},
        {'msgtype': 'text', 'text': {'content': 'two'}},
    ]
    result = await api.parse_wecom_bot_message(base('mixed', mixed={'msg_item': items}), AESKEY, Logger())

    assert result['content'] == 'one two'
    assert result['images'] == [_data_uri('https://x/i.png')]
    assert result['picurl'] == result['images'][0]
    assert result['file']['filename'] == 'f'
    assert result['files'][0] is result['file']
    assert result['link'] == {'title': 'T', 'description': 'D'}
    assert result['attachments'] == items


@pytest.mark.asyncio
async def test_mixed_omits_empty_kind_keys(downloaded):
    result = await api.parse_wecom_bot_message(
        base('mixed', mixed={'msg_item': [{'msgtype': 'text', 'text': {'content': 'only'}}]}),
        AESKEY,
        Logger(),
    )
    for key in ('images', 'picurl', 'files', 'file', 'voices', 'voice', 'videos', 'video', 'link'):
        assert key not in result


@pytest.mark.asyncio
async def test_quote_file_requires_both_url_and_aeskey_to_append(downloaded):
    payload = base('text', text={'content': 'x'}, quote={'msgtype': 'file', 'file': {'url': 'https://x/f'}})
    result = await api.parse_wecom_bot_message(payload, AESKEY, Logger())
    assert result['quote']['file']['download_url'] == 'https://x/f'

    payload['quote']['file'] = {'url': 'https://x/f', 'aeskey': 'per-msg'}
    result = await api.parse_wecom_bot_message(payload, AESKEY, Logger())
    assert result['quote']['file']['download_url'] == 'https://x/f?aeskey=per-msg'


@pytest.mark.asyncio
async def test_quote_link_derives_content_from_title_and_description(downloaded):
    payload = base('text', text={'content': 'x'}, quote={'msgtype': 'link', 'link': {'title': 'T', 'digest': 'D'}})
    result = await api.parse_wecom_bot_message(payload, AESKEY, Logger())
    assert result['quote']['content'] == 'T\nD'


@pytest.mark.asyncio
async def test_quote_mixed_only_keeps_text_images_and_files(downloaded):
    quote = {
        'msgtype': 'mixed',
        'mixed': {
            'msg_item': [
                {'msgtype': 'text', 'text': {'content': 'a'}},
                {'msgtype': 'file', 'file': {'url': 'https://x/f', 'filename': 'f'}},
                {'msgtype': 'voice', 'voice': {'url': 'https://x/v', 'filesize': SMALL}},
            ]
        },
    }
    result = await api.parse_wecom_bot_message(base('text', text={'content': 'x'}, quote=quote), AESKEY, Logger())
    assert result['quote']['content'] == 'a'
    assert result['quote']['file']['filename'] == 'f'
    # Quote-mixed handles only text/image/file: voice is silently dropped.
    assert 'voice' not in result['quote']
    assert 'voices' not in result['quote']


@pytest.mark.asyncio
async def test_unknown_type_falls_back_to_raw_msg(downloaded):
    result = await api.parse_wecom_bot_message(base('event'), AESKEY, Logger())
    assert result['raw_msg'] == base('event')
    assert 'content' not in result


@pytest.mark.asyncio
async def test_missing_aes_key_skips_download_and_warns(downloaded):
    logger = Logger()
    result = await api.parse_wecom_bot_message(base('image', image={'url': 'https://x/i.png'}), '', logger)
    assert 'images' not in result
    assert downloaded == []
    assert logger.warnings


@pytest.mark.asyncio
async def test_failed_decrypt_leaves_the_message_without_payload(downloaded, monkeypatch):
    async def failing(url, key, logger):
        return None, None

    monkeypatch.setattr(api, 'download_encrypted_file', failing)
    result = await api.parse_wecom_bot_message(base('image', image={'url': 'https://x/i.png'}), AESKEY, Logger())
    assert 'images' not in result
    assert 'picurl' not in result


# --- regressions found by differential review: per-message aeskey and signing ---


@pytest.mark.asyncio
async def test_mixed_voice_downloads_with_the_message_aeskey_not_the_platform_key(downloaded):
    """A voice inside a mixed message must use its own aeskey. (#2633 review)"""
    items = [{'msgtype': 'voice', 'voice': {'url': 'https://x/v.amr', 'aeskey': 'per-msg', 'filesize': SMALL}}]
    result = await api.parse_wecom_bot_message(base('mixed', mixed={'msg_item': items}), AESKEY, Logger())

    assert downloaded == [('https://x/v.amr', 'per-msg')]
    assert result['voice']['base64'].startswith('data:audio/')


@pytest.mark.asyncio
async def test_quote_voice_downloads_with_the_message_aeskey_not_the_platform_key(downloaded):
    quote = {'msgtype': 'voice', 'voice': {'url': 'https://x/v.amr', 'aeskey': 'per-msg', 'filesize': SMALL}}
    result = await api.parse_wecom_bot_message(base('text', text={'content': 'x'}, quote=quote), AESKEY, Logger())

    assert downloaded == [('https://x/v.amr', 'per-msg')]
    assert result['quote']['voice']['base64'].startswith('data:audio/')


@pytest.mark.asyncio
async def test_mixed_file_url_is_never_signed(downloaded):
    """A mixed file keeps its plain URL, matching the single/quote asymmetry."""
    items = [{'msgtype': 'file', 'file': {'url': 'https://x/f', 'aeskey': 'per-msg', 'filename': 'f'}}]
    result = await api.parse_wecom_bot_message(base('mixed', mixed={'msg_item': items}), AESKEY, Logger())

    assert result['file']['download_url'] == 'https://x/f'


@pytest.mark.asyncio
async def test_quote_file_url_is_unsigned_without_an_aeskey(downloaded):
    """No dangling ?aeskey= when the quoted file has no aeskey."""
    quote = {'msgtype': 'file', 'file': {'url': 'https://x/f'}}
    result = await api.parse_wecom_bot_message(base('text', text={'content': 'x'}, quote=quote), AESKEY, Logger())

    assert result['quote']['file']['download_url'] == 'https://x/f'


@pytest.mark.asyncio
async def test_mixed_video_payload_has_no_download_url(downloaded):
    """A mixed video carries the same keys as master: no download_url."""
    items = [{'msgtype': 'video', 'video': {'url': 'https://x/v.mp4', 'aeskey': 'per-msg'}}]
    result = await api.parse_wecom_bot_message(base('mixed', mixed={'msg_item': items}), AESKEY, Logger())

    # Small videos additionally get an inline payload, as on master.
    assert set(result['video']) == {'url', 'filesize', 'sdkfileid', 'md5sum', 'filename', 'base64'}
    assert 'download_url' not in result['video']


@pytest.mark.asyncio
async def test_mixed_file_has_no_inline_payload_above_the_size_limit(downloaded):
    items = [{'msgtype': 'file', 'file': {'url': 'https://x/f', 'aeskey': 'k', 'filesize': BIG}}]
    result = await api.parse_wecom_bot_message(base('mixed', mixed={'msg_item': items}), AESKEY, Logger())

    assert 'base64' not in result['file']
    assert downloaded == []


@pytest.mark.asyncio
async def test_single_voice_payload_has_no_aeskey_key(downloaded):
    """The aeskey is a download input, not part of the published payload."""
    result = await api.parse_wecom_bot_message(
        base('voice', voice={'url': 'https://x/v.amr', 'aeskey': 'per-msg', 'filesize': SMALL}), AESKEY, Logger()
    )

    assert 'aeskey' not in result['voice']
    assert downloaded == [('https://x/v.amr', 'per-msg')]


@pytest.mark.asyncio
async def test_file_type_without_a_file_payload_does_not_crash(downloaded):
    """master raised TypeError here; the split returns a null-filled payload."""
    result = await api.parse_wecom_bot_message(base('file', files=[{'url': 'https://x/f'}]), AESKEY, Logger())

    assert result['file']['download_url'] is None
    assert result['file']['filename'] is None
