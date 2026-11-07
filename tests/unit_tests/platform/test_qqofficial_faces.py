"""QQ Official faces remain structured while the model sees readable text."""

from types import SimpleNamespace

import pytest

from langbot.libs.qq_official_api.qqofficialevent import QQOfficialEvent
from langbot.pkg.agent.runner.query_entry_adapter import QueryEntryAdapter
from langbot.pkg.platform.qqofficial_faces import parse_qqofficial_face_components
from langbot.pkg.platform.adapters.qqofficial.message_converter import QQOfficialMessageConverter as EBAConverter
from langbot.pkg.platform.sources.qqofficial import QQOfficialMessageConverter as LegacyConverter
from langbot_plugin.api.entities.builtin.platform import message as platform_message


FACE = '<faceType=1,faceId="300",ext="eyJ0ZXh0Ijoi6IOW5LiJ5pakIn0=">'


def test_structured_face_preserves_order_and_readable_model_text():
    components = parse_qqofficial_face_components('你好' + FACE + '！')
    assert [type(item) for item in components] == [
        platform_message.Plain,
        platform_message.Face,
        platform_message.Plain,
    ]
    assert components[1].face_id == 300
    assert components[1].face_name == '胖三斤'
    assert str(platform_message.MessageChain(components)) == '你好[表情]胖三斤！'


@pytest.mark.parametrize(
    'raw',
    [
        '<faceType=4,faceId="",ext="not-base64">',
        '<faceType=1,faceId="123",ext="e30=">',
        '<faceType=1,faceId="123",ext="' + 'A' * 2049 + '">',
        '<faceType=1,faceId="123",ext="">',
        'not a face <faceType=1',
    ],
)
def test_unknown_or_invalid_face_markers_are_kept_verbatim(raw):
    components = parse_qqofficial_face_components('before ' + raw + ' after')
    assert components == [platform_message.Plain(text='before ' + raw + ' after')]


@pytest.mark.parametrize('converter', ['legacy', 'eba'])
@pytest.mark.asyncio
async def test_both_qqofficial_converters_keep_source_and_face(converter):
    message = '先' + FACE + '后'
    if converter == 'legacy':
        chain = await LegacyConverter.target2yiri(message, 'msg-1', None, None)
    else:
        event = QQOfficialEvent({'t': 'GROUP_MESSAGE_CREATE', 'content': message, 'd_id': 'msg-1'})
        chain = await EBAConverter.target2yiri(event)
        assert event.content == message

    assert [type(item) for item in chain] == [
        platform_message.Source,
        platform_message.Plain,
        platform_message.Face,
        platform_message.Plain,
    ]


def test_direct_runner_fallback_exposes_face_label_as_text():
    message_chain = platform_message.MessageChain(
        [platform_message.Plain(text='收到'), platform_message.Face(face_id=300, face_name='胖三斤')]
    )
    event = SimpleNamespace(message_chain=message_chain, user_message=None, variables={})
    model_input = QueryEntryAdapter._build_input(event)

    assert model_input.text == '收到[表情]胖三斤'
    assert model_input.attachments == []
