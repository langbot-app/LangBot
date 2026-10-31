from __future__ import annotations

import pytest
from unittest.mock import MagicMock

from linebot.v3.webhooks import TextMessageContent, UserMentionee, AllMentionee

from langbot.pkg.platform import botmgr as _botmgr  # noqa: F401
from langbot.pkg.platform.sources import line
import langbot_plugin.api.entities.builtin.platform.message as platform_message

BOT_ACCOUNT_ID = 'line-bot-account'


def _make_event(
    *, source_type: str, user_id, group_id=None, room_id=None, message_id: str, text: str = 'hi', mention=None
):
    event = MagicMock()
    event.timestamp = 1700000000000
    message = MagicMock(spec=TextMessageContent)
    message.id = message_id
    message.text = text
    message.mention = mention
    event.message = message
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


def _make_converter(bot_account_id: str = BOT_ACCOUNT_ID) -> line.LINEEventConverter:
    return line.LINEEventConverter(bot_account_id=bot_account_id)


@pytest.mark.asyncio
async def test_user_message_launcher_id_stable_across_messages() -> None:
    """Two distinct messages from the same LINE user must resolve to the same
    sender id, otherwise every message starts a brand new session (context loss).
    """
    converter = _make_converter()
    event1 = _make_event(source_type='user', user_id='U-stable-user', message_id='msg-1')
    event2 = _make_event(source_type='user', user_id='U-stable-user', message_id='msg-2')

    result1 = await converter.target2yiri(event1, bot_client=None)
    result2 = await converter.target2yiri(event2, bot_client=None)

    assert result1.sender.id == 'U-stable-user'
    assert result1.sender.id == result2.sender.id
    assert result1.sender.id != event1.message.id


@pytest.mark.asyncio
async def test_group_message_uses_group_id_not_message_id() -> None:
    converter = _make_converter()
    event1 = _make_event(source_type='group', user_id='U-member', group_id='G-stable-group', message_id='msg-1')
    event2 = _make_event(source_type='group', user_id='U-member', group_id='G-stable-group', message_id='msg-2')

    result1 = await converter.target2yiri(event1, bot_client=None)
    result2 = await converter.target2yiri(event2, bot_client=None)

    assert result1.sender.group.id == 'G-stable-group'
    assert result1.sender.group.id == result2.sender.group.id
    assert result1.sender.id == 'U-member'


@pytest.mark.asyncio
async def test_room_message_uses_room_id_and_falls_back_when_user_id_missing() -> None:
    converter = _make_converter()
    event = _make_event(source_type='room', user_id=None, room_id='R-stable-room', message_id='msg-1')

    result = await converter.target2yiri(event, bot_client=None)

    assert result.sender.group.id == 'R-stable-room'
    assert result.sender.id == 'R-stable-room'


def _plain_texts(chain: platform_message.MessageChain) -> list[str]:
    return [c.text for c in chain if isinstance(c, platform_message.Plain)]


def _ats(chain: platform_message.MessageChain) -> list[platform_message.At]:
    return [c for c in chain if isinstance(c, platform_message.At)]


@pytest.mark.asyncio
async def test_no_mention_keeps_plain_text() -> None:
    converter = _make_converter()
    event = _make_event(source_type='group', user_id='U-member', group_id='G1', message_id='m1', text='hello world')

    chain = await converter.message_converter.target2yiri(event, bot_client=None)

    assert _plain_texts(chain) == ['hello world']
    assert _ats(chain) == []


@pytest.mark.asyncio
async def test_bot_mention_maps_to_at_with_bot_account_id() -> None:
    """A @bot mention must become At(target=bot_account_id) so the 'at-bot'
    group respond rule matches (previously the mention was lost and the message
    was silently dropped in groups with at-only rules).
    """
    mention = MagicMock()
    mention.mentionees = [
        UserMentionee(type='user', index=0, length=4, userId='U-bot-user-id', isSelf=True),
    ]
    converter = _make_converter()
    event = _make_event(
        source_type='group',
        user_id='U-member',
        group_id='G1',
        message_id='m1',
        text='@BOT hey',
        mention=mention,
    )

    chain = await converter.message_converter.target2yiri(event, bot_client=None)

    ats = _ats(chain)
    assert len(ats) == 1
    assert ats[0].target == BOT_ACCOUNT_ID
    assert _plain_texts(chain) == [' hey']


@pytest.mark.asyncio
async def test_other_user_mention_keeps_display_text() -> None:
    """Mentions of other users keep their display text in the message string,
    so prefix/regexp rules that match the raw '@Name ...' text still work.
    """
    mention = MagicMock()
    mention.mentionees = [
        UserMentionee(type='user', index=0, length=6, userId='U-other', isSelf=False),
    ]
    converter = _make_converter()
    event = _make_event(
        source_type='group',
        user_id='U-member',
        group_id='G1',
        message_id='m1',
        text='@Alice hello',
        mention=mention,
    )

    chain = await converter.message_converter.target2yiri(event, bot_client=None)

    ats = _ats(chain)
    assert len(ats) == 1
    assert ats[0].target == 'U-other'
    # str() of the At component falls back to display when set
    assert str(chain) == '@Alice hello'


@pytest.mark.asyncio
async def test_bot_mention_triggers_atbot_rule() -> None:
    """End-to-end: a group message that @mentions the bot must be accepted by
    the at-bot respond rule (this is the regression that silently dropped
    '@bot' messages in LINE groups).
    """
    from langbot.pkg.pipeline.resprule.rules.atbot import AtBotRule

    mention = MagicMock()
    mention.mentionees = [
        UserMentionee(type='user', index=0, length=6, userId='U-bot-user-id', isSelf=True),
    ]
    converter = _make_converter()
    event = _make_event(
        source_type='group',
        user_id='U-member',
        group_id='G1',
        message_id='m1',
        text='@RAIQt hi',
        mention=mention,
    )

    chain = await converter.message_converter.target2yiri(event, bot_client=None)

    query = MagicMock()
    query.adapter = MagicMock()
    query.adapter.bot_account_id = BOT_ACCOUNT_ID

    rule = AtBotRule(ap=MagicMock())
    result = await rule.match(str(chain), chain, {'at': True}, query)

    assert result.matching is True


@pytest.mark.asyncio
async def test_group_without_bot_mention_still_dropped_by_atbot_rule() -> None:
    from langbot.pkg.pipeline.resprule.rules.atbot import AtBotRule

    converter = _make_converter()
    event = _make_event(source_type='group', user_id='U-member', group_id='G1', message_id='m1', text='hello')

    chain = await converter.message_converter.target2yiri(event, bot_client=None)

    query = MagicMock()
    query.adapter = MagicMock()
    query.adapter.bot_account_id = BOT_ACCOUNT_ID

    rule = AtBotRule(ap=MagicMock())
    result = await rule.match(str(chain), chain, {'at': True}, query)

    assert result.matching is False


@pytest.mark.asyncio
async def test_at_all_mention_preserved_as_at_component() -> None:
    mention = MagicMock()
    mention.mentionees = [
        AllMentionee(type='all', index=0, length=4),
    ]
    converter = _make_converter()
    event = _make_event(
        source_type='group',
        user_id='U-member',
        group_id='G1',
        message_id='m1',
        text='@All hello',
        mention=mention,
    )

    chain = await converter.message_converter.target2yiri(event, bot_client=None)

    ats = _ats(chain)
    assert len(ats) == 1
    assert str(chain) == '@All hello'


@pytest.mark.asyncio
async def test_multiple_mentions_sorted_by_position() -> None:
    mention = MagicMock()
    # Intentionally out of order to exercise sorting
    mention.mentionees = [
        UserMentionee(type='user', index=9, length=4, userId='U-b', isSelf=False),
        UserMentionee(type='user', index=0, length=4, userId='U-a', isSelf=False),
    ]
    converter = _make_converter()
    event = _make_event(
        source_type='group',
        user_id='U-member',
        group_id='G1',
        message_id='m1',
        text='@aaa mid @bbb tail',
        mention=mention,
    )

    chain = await converter.message_converter.target2yiri(event, bot_client=None)

    ats = _ats(chain)
    assert [a.target for a in ats] == ['U-a', 'U-b']
    assert str(chain) == '@aaa mid @bbb tail'
