import base64

import pytest

import langbot.pkg.core.app  # noqa: F401
import langbot_plugin.api.entities.builtin.platform.message as platform_message
from langbot.libs.wecom_ai_bot_api.ws_client import _UPLOAD_CHUNK_SIZE, WecomBotWsClient
from langbot.pkg.platform.sources.wecombot import WecomBotAdapter, WecomBotMessageConverter


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


class UploadClient(WecomBotWsClient):
    def __init__(self):
        super().__init__(bot_id='bot', secret='secret', logger=Logger())
        self.frames = []

    async def _send_reply(self, req_id: str, body: dict, cmd: str = 'aibot_respond_msg'):
        self.frames.append((cmd, body))
        if cmd == 'aibot_upload_media_init':
            return {'errcode': 0, 'body': {'upload_id': 'upload-1'}}
        if cmd == 'aibot_upload_media_finish':
            return {'errcode': 0, 'body': {'media_id': 'media-1'}}
        return {'errcode': 0}


class Bot:
    def __init__(self):
        self.calls = []

    async def upload_media(self, data, filename='attachment', media_type='file'):
        self.calls.append(('upload_media', media_type, filename, data))
        return {'media_id': 'media-1'}

    async def reply_text(self, req_id, content):
        self.calls.append(('reply_text', req_id, content))

    async def reply_image(self, req_id, media_id):
        self.calls.append(('reply_image', req_id, media_id))

    async def send_message(self, target_id, content):
        self.calls.append(('send_message', target_id, content))


def make_adapter(bot):
    return WecomBotAdapter.model_construct(
        bot=bot,
        config={'enable-webhook': False},
        logger=Logger(),
        message_converter=WecomBotMessageConverter(),
    )


@pytest.mark.asyncio
async def test_ws_client_upload_media_uses_chunk_protocol():
    client = UploadClient()
    data = b'a' * (_UPLOAD_CHUNK_SIZE + 1)

    upload_result = await client.upload_media(data, 'image.png', media_type='image')

    assert upload_result['media_id'] == 'media-1'
    assert [cmd for cmd, _ in client.frames] == [
        'aibot_upload_media_init',
        'aibot_upload_media_chunk',
        'aibot_upload_media_chunk',
        'aibot_upload_media_finish',
    ]
    init_body = client.frames[0][1]
    assert init_body['type'] == 'image'
    assert init_body['filename'] == 'image.png'
    assert init_body['total_size'] == len(data)
    assert init_body['total_chunks'] == 2
    assert client.frames[1][1]['chunk_index'] == 0
    assert base64.b64decode(client.frames[1][1]['base64_data']) == b'a' * _UPLOAD_CHUNK_SIZE
    assert client.frames[2][1]['chunk_index'] == 1
    assert base64.b64decode(client.frames[2][1]['base64_data']) == b'a'


@pytest.mark.asyncio
async def test_reply_message_uploads_and_replies_image_media():
    bot = Bot()
    adapter = make_adapter(bot)
    png_data = b'\x89PNG\r\n\x1a\nimage'
    image_b64 = base64.b64encode(png_data).decode('utf-8')
    chain = platform_message.MessageChain([platform_message.Image(base64=f'data:image/png;base64,{image_b64}')])

    items = await WecomBotMessageConverter.yiri2target(chain)
    await adapter._send_media(bot, 'req-1', items[0])

    assert bot.calls == [
        ('upload_media', 'image', 'attachment.image', png_data),
        ('reply_image', 'req-1', 'media-1'),
    ]


@pytest.mark.asyncio
async def test_send_message_sends_text_and_skips_proactive_image():
    bot = Bot()
    adapter = make_adapter(bot)
    jpg_data = b'\xff\xd8\xffimage'
    image_b64 = base64.b64encode(jpg_data).decode('utf-8')
    chain = platform_message.MessageChain(
        [
            platform_message.Plain(text='before'),
            platform_message.Image(base64=f'data:image/jpeg;base64,{image_b64}'),
            platform_message.Plain(text='after'),
        ]
    )

    await adapter.send_message('group', 'chat-1', chain)

    assert bot.calls == [
        ('send_message', 'chat-1', 'beforeafter'),
    ]
