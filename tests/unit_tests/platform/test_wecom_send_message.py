"""Tests for WecomAdapter.send_message content-key handling."""

import pytest

import langbot_plugin.api.entities.builtin.platform.message as platform_message
from langbot.pkg.platform.sources.wecom import WecomAdapter


class StubWecomClient:
    def __init__(self):
        self.calls = []

    async def get_media_id(self, msg):
        return 'MEDIA_ID_123'

    async def send_private_msg(self, user_id, agent_id, text):
        self.calls.append(('text', user_id, agent_id, text))

    async def send_image(self, user_id, agent_id, media_id):
        self.calls.append(('image', user_id, agent_id, media_id))

    async def send_voice(self, user_id, agent_id, media_id):
        self.calls.append(('voice', user_id, agent_id, media_id))

    async def send_file(self, user_id, agent_id, media_id):
        self.calls.append(('file', user_id, agent_id, media_id))


def _make_adapter():
    adapter = WecomAdapter.model_construct(bot=StubWecomClient())
    return adapter


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ('part', 'expected_type'),
    [
        (platform_message.Image(url='https://example.com/x.jpg'), 'image'),
        (platform_message.Voice(url='https://example.com/x.amr'), 'voice'),
        (platform_message.File(url='https://example.com/x.pdf', name='x.pdf'), 'file'),
    ],
)
async def test_send_message_dispatches_media_by_id(part, expected_type):
    adapter = _make_adapter()
    chain = platform_message.MessageChain([part])

    await adapter.send_message('person', 'USER1|1000001', chain)

    assert adapter.bot.calls == [(expected_type, 'USER1', 1000001, 'MEDIA_ID_123')]


@pytest.mark.asyncio
async def test_send_message_text_still_works():
    adapter = _make_adapter()
    chain = platform_message.MessageChain([platform_message.Plain(text='hello')])

    await adapter.send_message('person', 'USER1|1000001', chain)

    assert adapter.bot.calls == [('text', 'USER1', 1000001, 'hello')]
