import pytest

import langbot_plugin.api.entities.builtin.platform.message as platform_message
from src.langbot.pkg.platform.sources.aiocqhttp import AiocqhttpAdapter, AiocqhttpMessageConverter


async def _convert_single(component: platform_message.MessageComponent):
    chain = platform_message.MessageChain([component])
    message, _, _ = await AiocqhttpMessageConverter.yiri2target(chain)
    return message[0]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ('payload', 'expected'),
    [
        ('data:image/jpeg;base64,raw-image', 'base64://raw-image'),
        ('raw-image', 'base64://raw-image'),
        ('base64://raw-image', 'base64://raw-image'),
    ],
)
async def test_image_base64_payload_is_normalized(payload, expected):
    segment = await _convert_single(platform_message.Image(base64=payload))

    assert segment.type == 'image'
    assert segment.data['file'] == expected


@pytest.mark.asyncio
async def test_voice_data_uri_base64_payload_is_normalized():
    segment = await _convert_single(platform_message.Voice(base64='data:audio/wav;base64,raw-voice'))

    assert segment.type == 'record'
    assert segment.data['file'] == 'base64://raw-voice'


@pytest.mark.asyncio
async def test_forward_image_base64_payload_is_normalized():
    forward = platform_message.Forward(
        node_list=[
            platform_message.ForwardMessageNode(
                sender_id='10001',
                sender_name='Tester',
                message_chain=platform_message.MessageChain(
                    [platform_message.Image(base64='data:image/png;base64,raw-forward-image')]
                ),
            )
        ]
    )
    messages = []

    class Logger:
        async def info(self, _message):
            return None

        async def error(self, _message):
            return None

    class Bot:
        async def call_action(self, action, **kwargs):
            assert action == 'send_forward_msg'
            messages.append(kwargs)

    platform = AiocqhttpAdapter.model_construct(
        bot_account_id='10000',
        config={},
        logger=Logger(),
        bot=Bot(),
    )

    await platform._send_forward_message(1000, forward)

    assert messages[0]['messages'][0]['data']['content'][0] == {
        'type': 'image',
        'data': {'file': 'base64://raw-forward-image'},
    }
