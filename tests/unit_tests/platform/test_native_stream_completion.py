"""Exercise terminal runner snapshots against native adapter delivery methods."""

import datetime
import time
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
import telegram

from langbot_plugin.api.entities.builtin.provider.message import Message, MessageChunk
from langbot_plugin.api.entities.builtin.platform.message import MessageChain, Plain
from langbot.pkg.pipeline.process.stream_results import coalesce_stream_results


@pytest.mark.asyncio
@pytest.mark.parametrize('platform', ['lark', 'dingtalk', 'telegram', 'discord', 'qqofficial', 'wecombot'])
async def test_native_stream_receives_one_terminal_snapshot(platform):
    module = __import__(f'tests.unit_tests.platform.test_{platform}_eba_adapter', fromlist=['make_adapter'])
    adapter = module.make_adapter()
    object.__setattr__(adapter, 'reply_message', AsyncMock())
    source = SimpleNamespace()
    if platform == 'lark':
        adapter.card_id_dict['response'] = 'card'
        adapter.card_sequence_dict['card'] = 0
        adapter._replace_streaming_card = AsyncMock()
        source.source_platform_object = None
    elif platform == 'dingtalk':
        adapter.card_instance_id_dict['response'] = ('card', 'id')
    elif platform == 'telegram':
        source.source_platform_object = telegram.Update(
            1,
            message=telegram.Message(
                1,
                datetime.datetime.now(datetime.timezone.utc),
                telegram.Chat(1, 'private'),
                text='hi',
            ),
        )
        adapter.bot = SimpleNamespace(send_message_draft=AsyncMock(), send_message=AsyncMock())
        adapter.msg_stream_id['response'] = ('private', 1, False)
    elif platform == 'discord':
        adapter._stream_buffer['response'] = {
            'channel': SimpleNamespace(send=AsyncMock(return_value=SimpleNamespace(content='hello', edit=AsyncMock()))),
            'sent_message': None,
            'last_content': '',
            'chunk_count': 0,
            'updated_at': time.time(),
        }
        channel = adapter._stream_buffer['response']['channel']
    elif platform == 'qqofficial':
        source = await module.QQOfficialEventConverter().target2yiri(module.qq_event())
        await adapter.create_message_card('response', source)
    else:
        source = await module.WecomBotEventConverter().target2yiri(module.wecombot_event())

    async def runner():
        yield MessageChunk(role='assistant', content='hello', all_content='hello', is_final=True)
        yield Message(role='assistant', content='hello')

    count = 0
    async for result in coalesce_stream_results(runner()):
        chunk = MessageChunk(role='assistant', content=result.content, resp_message_id='response', is_final=True)
        await adapter.reply_message_chunk(source, chunk, MessageChain([Plain(text=result.content)]), is_final=True)
        count += 1
    assert count == 1
    adapter.reply_message.assert_not_awaited()
    if platform == 'lark':
        adapter._replace_streaming_card.assert_awaited_once_with('card', 'hello')
        assert not adapter.card_id_dict
    elif platform == 'dingtalk':
        adapter.bot.send_card_message.assert_awaited_once_with('card', 'id', 'hello', True)
        assert not adapter.card_instance_id_dict
    elif platform == 'telegram':
        adapter.bot.send_message.assert_awaited_once()
        assert not adapter.msg_stream_id
    elif platform == 'discord':
        channel.send.assert_awaited_once_with('hello')
        assert not adapter._stream_buffer
    elif platform == 'qqofficial':
        assert len([call for call in adapter.bot.sent if call[0] == 'stream']) == 1
        assert not adapter._stream_ctx
    else:
        adapter.bot.push_stream_chunk.assert_awaited_once_with('msg-1', 'hello', is_final=True)
        adapter.bot.reply_text.assert_not_awaited()
