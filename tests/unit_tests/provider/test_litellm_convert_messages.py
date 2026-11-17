"""Unit tests for LiteLLMRequester._convert_messages.

Image parts use OpenAI's image_url shape. Explicit PDF input checks native
model support and uses the file shape; unsupported legacy file parts retain
their existing handling.
"""

import base64

import langbot_plugin.api.entities.builtin.provider.message as provider_message
import pytest

from langbot.pkg.provider.modelmgr import errors
from langbot.pkg.provider.modelmgr.requesters.litellmchat import LiteLLMRequester
from tests.utils.artifact_media import text_pdf


def _make_requester() -> LiteLLMRequester:
    # _convert_messages does not touch instance config, so bypass __init__.
    return LiteLLMRequester.__new__(LiteLLMRequester)


@pytest.fixture
def pdf_data_url():
    return 'data:application/pdf;base64,' + base64.b64encode(text_pdf('Provider conversion fixture')).decode()


def test_explicit_pdf_input_uses_supported_file_payload(monkeypatch, pdf_data_url):
    req = _make_requester()
    probes = []

    def capability(helper, model):
        probes.append((helper, model))
        return True

    monkeypatch.setattr(req, '_safe_litellm_bool_helper', capability)
    message = provider_message.Message(
        role='user',
        content=[
            provider_message.ContentElement.from_file_base64(pdf_data_url, 'report.pdf'),
        ],
    )
    result = req._convert_messages([message], model_name='pdf-model')
    assert result[0]['content'] == [{'type': 'file', 'file': {'file_data': pdf_data_url, 'filename': 'report.pdf'}}]
    assert probes == [('supports_pdf_input', 'pdf-model')]
    assert message.content[0].type == 'file_base64'


def test_explicit_pdf_input_fails_instead_of_being_discarded(monkeypatch, pdf_data_url):
    req = _make_requester()
    monkeypatch.setattr(req, '_safe_litellm_bool_helper', lambda *_args: False)
    message = provider_message.Message(
        role='user',
        content=[
            provider_message.ContentElement.from_file_base64(pdf_data_url, 'report.pdf'),
        ],
    )
    with pytest.raises(errors.RequesterError) as failure:
        req._convert_messages([message], model_name='text-model')
    assert failure.value.code == 'unsupported_pdf_input'


def test_explicit_pdf_ability_supports_verified_gateway_alias_without_guessing_metadata(monkeypatch, pdf_data_url):
    req = _make_requester()

    def unexpected_metadata_probe(*_args):
        raise AssertionError('An explicit PDF declaration must not depend on alias metadata')

    monkeypatch.setattr(req, '_safe_litellm_bool_helper', unexpected_metadata_probe)
    message = provider_message.Message(
        role='user',
        content=[
            provider_message.ContentElement.from_file_base64(pdf_data_url, 'report.pdf'),
        ],
    )
    converted = req._convert_messages([message], model_name='verified-gateway-alias', pdf_input_declared=True)
    assert converted[0]['content'] == [{'type': 'file', 'file': {'file_data': pdf_data_url, 'filename': 'report.pdf'}}]


@pytest.mark.parametrize(
    'legacy_file',
    [
        pytest.param(
            provider_message.ContentElement.from_file_base64('data:audio/wav;base64,AAAA', 'voice.wav'),
            id='inline-audio',
        ),
        pytest.param(
            provider_message.ContentElement.from_file_url('https://example.test/report.xlsx', 'report.xlsx'),
            id='file-url',
        ),
    ],
)
def test_legacy_file_is_not_forwarded_but_surrounding_history_is_preserved(legacy_file):
    history = [
        provider_message.Message(
            role='user', content=[provider_message.ContentElement.from_text('old turn'), legacy_file]
        ),
        provider_message.Message(role='user', content=[provider_message.ContentElement.from_text('current turn')]),
    ]
    snapshot = [message.model_dump() for message in history]

    converted = _make_requester()._convert_messages(history)

    assert [message['content'] for message in converted] == [
        [{'type': 'text', 'text': 'old turn'}],
        [{'type': 'text', 'text': 'current turn'}],
    ]
    assert [message.model_dump() for message in history] == snapshot


def test_convert_messages_keeps_image_and_converts_to_image_url():
    req = _make_requester()
    msg = provider_message.Message(
        role='user',
        content=[
            provider_message.ContentElement.from_text('look'),
            provider_message.ContentElement.from_image_base64('data:image/png;base64,AAAA'),
        ],
    )
    out = req._convert_messages([msg])
    parts = out[0]['content']
    types = [p.get('type') for p in parts]
    # image is preserved and reshaped to the OpenAI image_url form
    assert types == ['text', 'image_url']
    img_part = parts[1]
    assert img_part['image_url'] == {'url': 'data:image/png;base64,AAAA'}
    assert 'image_base64' not in img_part


def test_convert_messages_plain_string_content_untouched():
    req = _make_requester()
    msg = provider_message.Message(role='user', content='just text')
    out = req._convert_messages([msg])
    assert out[0]['content'] == 'just text'


def test_convert_messages_replayed_image_without_base64_does_not_crash():
    """Replayed image parts hollowed out by history trimming must not raise KeyError (#2469).

    SessionManager clears image_base64 on past turns, and URL-less platform
    images never had a URL, so the replayed part serializes as
    {'type': 'image_base64'} with no payload keys. The hollow part should be
    dropped while the sibling text part survives.
    """
    req = _make_requester()
    image = provider_message.ContentElement.from_image_base64('data:image/jpeg;base64,AAAA')
    # Simulate SessionManager.trim_conversation_messages clearing binary payloads.
    image.image_base64 = None
    msg = provider_message.Message(
        role='user',
        content=[
            provider_message.ContentElement.from_text('describe the photo'),
            image,
        ],
    )
    out = req._convert_messages([msg])
    assert [p.get('type') for p in out[0]['content']] == ['text']


def test_convert_messages_replayed_image_with_url_falls_back_to_url():
    """When base64 was trimmed but image_url survived, rebuild the OpenAI image_url part from the URL."""
    req = _make_requester()
    image = provider_message.ContentElement(
        type='image_base64',
        image_base64=None,
        image_url=provider_message.ImageURLContentObject(url='https://example.com/pic.jpg'),
    )
    msg = provider_message.Message(role='user', content=[image])
    out = req._convert_messages([msg])
    parts = out[0]['content']
    assert [p.get('type') for p in parts] == ['image_url']
    assert parts[0]['image_url'] == {'url': 'https://example.com/pic.jpg'}
    assert 'image_base64' not in parts[0]
