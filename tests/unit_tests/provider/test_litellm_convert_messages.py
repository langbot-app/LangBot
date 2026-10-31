"""Unit tests for LiteLLMRequester._convert_messages.

Focus: the content-part normalization that (a) converts image_base64 parts to
the OpenAI image_url shape and (b) drops non-image file parts (file_base64 /
file_url) which OpenAI-compatible chat models reject. The latter is essential
for Voice/File attachments — including ones replayed from conversation history —
since the agent consumes their bytes via the sandbox, not the model payload.
"""

import langbot_plugin.api.entities.builtin.provider.message as provider_message

from langbot.pkg.provider.modelmgr.requesters.litellmchat import LiteLLMRequester


def _make_requester() -> LiteLLMRequester:
    # _convert_messages does not touch instance config, so bypass __init__.
    return LiteLLMRequester.__new__(LiteLLMRequester)


def test_convert_messages_drops_file_base64_part():
    req = _make_requester()
    msg = provider_message.Message(
        role='user',
        content=[
            provider_message.ContentElement.from_text('analyze this audio'),
            provider_message.ContentElement.from_file_base64('data:audio/wav;base64,AAAA', 'voice.wav'),
        ],
    )
    out = req._convert_messages([msg])
    parts = out[0]['content']
    types = [p.get('type') for p in parts]
    assert 'file_base64' not in types
    assert types == ['text']
    assert parts[0]['text'] == 'analyze this audio'


def test_convert_messages_drops_file_url_part():
    req = _make_requester()
    msg = provider_message.Message(
        role='user',
        content=[
            provider_message.ContentElement.from_text('here is a doc'),
            provider_message.ContentElement.from_file_url('http://example.com/report.xlsx', 'report.xlsx'),
        ],
    )
    out = req._convert_messages([msg])
    types = [p.get('type') for p in out[0]['content']]
    assert types == ['text']


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


def test_convert_messages_mixed_history_strips_only_files():
    req = _make_requester()
    # Simulate replayed history: an old voice turn + a current text turn.
    history_voice = provider_message.Message(
        role='user',
        content=[
            provider_message.ContentElement.from_text('old audio turn'),
            provider_message.ContentElement.from_file_base64('data:audio/wav;base64,BBBB', 'voice.wav'),
        ],
    )
    current = provider_message.Message(
        role='user',
        content=[provider_message.ContentElement.from_text('now do the csv')],
    )
    out = req._convert_messages([history_voice, current])
    assert [p.get('type') for p in out[0]['content']] == ['text']
    assert [p.get('type') for p in out[1]['content']] == ['text']


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
