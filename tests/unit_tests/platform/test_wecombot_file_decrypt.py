"""Single-file WeCom AI Bot messages must reach the Runner as plaintext.

#2835: the `file` branch handed upstream a `?aeskey=` URL pointing at
AES-256-CBC ciphertext, while the `mixed` branch already downloaded and
decrypted. Document extractors therefore rejected the (encrypted) upload.
"""

from __future__ import annotations

import base64

import pytest

import langbot.pkg.core.app  # noqa: F401
from langbot.libs.wecom_ai_bot_api import api as wecombot_api


class Logger:
    def __init__(self):
        self.warnings = []
        self.errors = []

    async def warning(self, message):
        self.warnings.append(message)

    async def error(self, message):
        self.errors.append(message)

    async def info(self, message):
        return None


def _file_message(aeskey: str = 'per-message-key', filesize: int = 12) -> dict:
    return {
        'msgid': 'msg-1',
        'msgtype': 'file',
        'chattype': 'single',
        'from': {'userid': 'user-1'},
        'file': {
            'url': 'https://example.test/encrypted.bin',
            'aeskey': aeskey,
            'filename': 'report.pdf',
            'filesize': filesize,
        },
    }


@pytest.mark.asyncio
async def test_single_file_message_is_downloaded_and_decrypted(monkeypatch):
    calls: list[tuple[str, str]] = []

    async def fake_download(url: str, key: str, logger):
        calls.append((url, key))
        return b'%PDF-1.4 plaintext', None

    monkeypatch.setattr(wecombot_api, 'download_encrypted_file', fake_download)

    parsed = await wecombot_api.parse_wecom_bot_message(_file_message(), 'fallback-key', Logger())

    assert calls == [('https://example.test/encrypted.bin', 'per-message-key')]
    # The data URI type is sniffed from the decrypted bytes, so extractors see a PDF.
    assert parsed['file']['base64'] == 'data:application/pdf;base64,' + base64.b64encode(
        b'%PDF-1.4 plaintext'
    ).decode()
    assert parsed['file']['filename'] == 'report.pdf'


@pytest.mark.asyncio
async def test_single_file_over_the_inline_limit_keeps_only_the_url(monkeypatch):
    async def fake_download(url: str, key: str, logger):
        raise AssertionError('oversized files must not be downloaded inline')

    monkeypatch.setattr(wecombot_api, 'download_encrypted_file', fake_download)

    parsed = await wecombot_api.parse_wecom_bot_message(
        _file_message(filesize=6 * 1024 * 1024),
        'fallback-key',
        Logger(),
    )

    assert 'base64' not in parsed['file']
    assert parsed['file']['download_url'].endswith('?aeskey=per-message-key')


@pytest.mark.asyncio
async def test_single_file_without_aeskey_still_yields_the_url(monkeypatch):
    async def fake_download(url: str, key: str, logger):
        raise AssertionError('no key -> no download')

    monkeypatch.setattr(wecombot_api, 'download_encrypted_file', fake_download)

    parsed = await wecombot_api.parse_wecom_bot_message(_file_message(aeskey=''), '', Logger())

    assert 'base64' not in parsed['file']
    assert parsed['file']['download_url'].startswith('https://example.test/encrypted.bin')
