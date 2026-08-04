from __future__ import annotations

import pytest
from unittest.mock import MagicMock

from linebot.v3.webhooks import TextMessageContent

from langbot.pkg.platform import botmgr as _botmgr  # noqa: F401
from langbot.pkg.platform.sources import line


def _make_event(*, source_type: str, user_id, group_id=None, room_id=None, message_id: str, text: str = 'hi'):
    event = MagicMock()
    event.timestamp = 1700000000000
    event.message = MagicMock(spec=TextMessageContent)
    event.message.id = message_id
    event.message.text = text
    event.message.webhook_event_id = f'webhook-{message_id}'
    event.message.timestamp = event.timestamp

    source = MagicMock()
    source.type = source_type
    source.user_id = user_id
    if group_id is not None:
        source.group_id = group_id
    if room_id is not None:
        source.room_id = room_id
    event.source = source

    return event


@pytest.mark.asyncio
async def test_user_message_launcher_id_stable_across_messages() -> None:
    """Two distinct messages from the same LINE user must resolve to the same
    sender id, otherwise every message starts a brand new session (context loss).
    """
    event1 = _make_event(source_type='user', user_id='U-stable-user', message_id='msg-1')
    event2 = _make_event(source_type='user', user_id='U-stable-user', message_id='msg-2')

    result1 = await line.LINEEventConverter.target2yiri(event1, bot_client=None)
    result2 = await line.LINEEventConverter.target2yiri(event2, bot_client=None)

    assert result1.sender.id == 'U-stable-user'
    assert result1.sender.id == result2.sender.id
    assert result1.sender.id != event1.message.id


@pytest.mark.asyncio
async def test_group_message_uses_group_id_not_message_id() -> None:
    event1 = _make_event(source_type='group', user_id='U-member', group_id='G-stable-group', message_id='msg-1')
    event2 = _make_event(source_type='group', user_id='U-member', group_id='G-stable-group', message_id='msg-2')

    result1 = await line.LINEEventConverter.target2yiri(event1, bot_client=None)
    result2 = await line.LINEEventConverter.target2yiri(event2, bot_client=None)

    assert result1.sender.group.id == 'G-stable-group'
    assert result1.sender.group.id == result2.sender.group.id
    assert result1.sender.id == 'U-member'


@pytest.mark.asyncio
async def test_room_message_uses_room_id_and_falls_back_when_user_id_missing() -> None:
    event = _make_event(source_type='room', user_id=None, room_id='R-stable-room', message_id='msg-1')

    result = await line.LINEEventConverter.target2yiri(event, bot_client=None)

    assert result.sender.group.id == 'R-stable-room'
    assert result.sender.id == 'R-stable-room'
