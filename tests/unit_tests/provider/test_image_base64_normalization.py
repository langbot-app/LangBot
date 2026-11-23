import base64
import io

import pytest
from PIL import Image
import langbot_plugin.api.entities.builtin.provider.message as provider_message

from langbot.pkg.provider.modelmgr.requesters.litellmchat import LiteLLMRequester
from langbot.pkg.utils import image


@pytest.mark.parametrize(
    'format,mime', [('PNG', 'image/png'), ('JPEG', 'image/jpeg'), ('WEBP', 'image/webp'), ('GIF', 'image/gif')]
)
def test_raw_image_becomes_data_url_without_mutating_input(format, mime):
    buffer = io.BytesIO()
    Image.new('RGB', (4, 4), 'red').save(buffer, format=format)
    raw = base64.b64encode(buffer.getvalue()).decode()
    msg = provider_message.Message(role='user', content=[provider_message.ContentElement.from_image_base64(raw)])
    requester = LiteLLMRequester.__new__(LiteLLMRequester)
    result = requester._convert_messages([msg])
    assert result[0]['content'][0]['image_url']['url'] == f'data:{mime};base64,{raw}'
    assert msg.content[0].image_base64 == raw
    assert requester._convert_messages([msg]) == result


@pytest.mark.parametrize('value', ['!invalid!', 'aGVsbG8=', ''])
def test_invalid_raw_image_is_rejected(value):
    with pytest.raises(ValueError, match='Invalid base64 image'):
        image.normalize_image_data_url(value)


def test_existing_data_url_is_preserved():
    value = 'data:image/jpeg;base64,existing-payload'
    assert image.normalize_image_data_url(value) == value


def test_oversized_raw_input_rejected_before_decode(monkeypatch):
    monkeypatch.setattr(image, 'DEFAULT_BASE64_MEDIA_LIMIT', 3)
    with pytest.raises(ValueError, match='size limit'):
        image.normalize_image_data_url('A' * 8)
