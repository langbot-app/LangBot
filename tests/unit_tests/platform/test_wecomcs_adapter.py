from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

import langbot_plugin.api.definition.abstract.platform.event_logger as abstract_platform_logger
import langbot_plugin.api.entities.builtin.platform.message as platform_message
from langbot.pkg.platform.sources.wecomcs import WecomCSAdapter


class DummyLogger(abstract_platform_logger.AbstractEventLogger):
    async def info(self, *args, **kwargs):
        pass

    async def debug(self, *args, **kwargs):
        pass

    async def warning(self, *args, **kwargs):
        pass

    async def error(self, *args, **kwargs):
        pass


def make_adapter():
    return WecomCSAdapter(
        config={
            'corpid': 'corp-id',
            'secret': 'secret',
            'token': 'token',
            'EncodingAESKey': 'encoding-key',
        },
        logger=DummyLogger(),
    )


@pytest.mark.asyncio
async def test_send_message_sends_text_to_customer_service_user():
    adapter = make_adapter()
    adapter.bot_account_id = 'kf-test'
    adapter.bot = SimpleNamespace(send_text_msg=AsyncMock())

    message = platform_message.MessageChain([platform_message.Plain(text='hello')])

    await adapter.send_message('person', 'uexternal-user', message)

    adapter.bot.send_text_msg.assert_awaited_once()
    kwargs = adapter.bot.send_text_msg.await_args.kwargs
    assert kwargs['open_kfid'] == 'kf-test'
    assert kwargs['external_userid'] == 'external-user'
    assert kwargs['content'] == 'hello'
    assert kwargs['msgid'].startswith('langbot_')


@pytest.mark.asyncio
async def test_send_message_allows_explicit_open_kfid_in_target_id():
    adapter = make_adapter()
    adapter.bot = SimpleNamespace(send_text_msg=AsyncMock())

    message = platform_message.MessageChain([platform_message.Plain(text='hello')])

    await adapter.send_message('person', 'kf-explicit|uexternal-user', message)

    kwargs = adapter.bot.send_text_msg.await_args.kwargs
    assert kwargs['open_kfid'] == 'kf-explicit'
    assert kwargs['external_userid'] == 'external-user'


@pytest.mark.asyncio
async def test_send_message_requires_open_kfid():
    adapter = make_adapter()
    adapter.bot = SimpleNamespace(send_text_msg=AsyncMock())
    message = platform_message.MessageChain([platform_message.Plain(text='hello')])

    with pytest.raises(ValueError, match='open_kfid is required'):
        await adapter.send_message('person', 'uexternal-user', message)

    adapter.bot.send_text_msg.assert_not_called()


@pytest.mark.asyncio
async def test_send_message_rejects_group_targets():
    adapter = make_adapter()
    adapter.bot_account_id = 'kf-test'
    adapter.bot = SimpleNamespace(send_text_msg=AsyncMock())
    message = platform_message.MessageChain([platform_message.Plain(text='hello')])

    with pytest.raises(ValueError, match='only supports sending messages to person'):
        await adapter.send_message('group', 'group-id', message)

    adapter.bot.send_text_msg.assert_not_called()
