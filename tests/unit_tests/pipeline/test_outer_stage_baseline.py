"""Behaviour baseline for the outer stages of the message lane.

Every case states a legacy pipeline config and the behaviour it must produce:
group respond rules, access control, ignore rules, content filter, rate limit,
long text, sending (delay, @sender, quote) and user notices. The cases only
talk to ``outer_stage_harness``, so they stay valid across refactors of where
that configuration lives.
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock

import pytest

import langbot_plugin.api.entities.builtin.platform.message as platform_message
import langbot_plugin.api.entities.builtin.provider.message as provider_message

from langbot.pkg.pipeline import entities

from . import outer_stage_harness as harness

CONTINUE = entities.ResultType.CONTINUE
INTERRUPT = entities.ResultType.INTERRUPT


@pytest.fixture
def app(mock_app):
    harness.prepare_app(mock_app)
    return mock_app


def _notice_text(result) -> str:
    notice = result.user_notice
    if not notice:
        return ''
    return str(notice)


# ---------------------------------------------------------------- group rules


@pytest.mark.asyncio
async def test_group_rules_do_not_apply_to_private_messages(app, sample_query):
    config = harness.legacy_config(
        {'trigger.group-respond-rules': {'at': True, 'prefix': [], 'regexp': [], 'random': 0}}
    )
    result = await harness.run_stage(app, sample_query, 'GroupRespondRuleCheckStage', config)
    assert result.result_type == CONTINUE
    assert str(sample_query.message_chain) == 'Hello, this is a test message'


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ('rules', 'components', 'expected', 'expected_text'),
    [
        # @bot required and present: pass, the mention is removed.
        (
            {'at': True, 'prefix': [], 'regexp': [], 'random': 0},
            [platform_message.At(target=harness.BOT_ACCOUNT_ID), ' hello'],
            CONTINUE,
            ' hello',
        ),
        # @bot required but absent: dropped.
        ({'at': True, 'prefix': [], 'regexp': [], 'random': 0}, ['hello'], INTERRUPT, 'hello'),
        # @ someone else does not count.
        (
            {'at': True, 'prefix': [], 'regexp': [], 'random': 0},
            [platform_message.At(target='other'), ' hello'],
            INTERRUPT,
            None,
        ),
        # at disabled: a mention alone does not pass, but is still removed.
        (
            {'at': False, 'prefix': [], 'regexp': [], 'random': 0},
            [platform_message.At(target=harness.BOT_ACCOUNT_ID), ' hello'],
            INTERRUPT,
            ' hello',
        ),
        # Prefix matches: pass and strip the prefix.
        ({'at': False, 'prefix': ['ai'], 'regexp': [], 'random': 0}, ['ai tell me'], CONTINUE, ' tell me'),
        ({'at': False, 'prefix': ['ai'], 'regexp': [], 'random': 0}, ['tell me ai'], INTERRUPT, 'tell me ai'),
        # Regexp matches from the start of the text: pass, text untouched.
        ({'at': False, 'prefix': [], 'regexp': ['^help.*'], 'random': 0}, ['help me'], CONTINUE, 'help me'),
        ({'at': False, 'prefix': [], 'regexp': ['^help.*'], 'random': 0}, ['no help'], INTERRUPT, 'no help'),
        # Random 1.0 always passes, 0 never does.
        ({'at': False, 'prefix': [], 'regexp': [], 'random': 1.0}, ['anything'], CONTINUE, 'anything'),
        ({'at': False, 'prefix': [], 'regexp': [], 'random': 0.0}, ['anything'], INTERRUPT, 'anything'),
    ],
)
async def test_group_respond_rules(app, sample_query, rules, components, expected, expected_text):
    harness.as_group(sample_query)
    harness.set_text(sample_query, *components)
    config = harness.legacy_config({'trigger.group-respond-rules': rules})

    result = await harness.run_stage(app, sample_query, 'GroupRespondRuleCheckStage', config)

    assert result.result_type == expected
    assert not result.user_notice
    if expected_text is not None:
        assert str(result.new_query.message_chain) == expected_text


@pytest.mark.asyncio
async def test_group_stop_command_bypasses_group_rules(app, sample_query):
    harness.as_group(sample_query)
    harness.set_text(sample_query, '/stop')
    config = harness.legacy_config(
        {'trigger.group-respond-rules': {'at': True, 'prefix': [], 'regexp': [], 'random': 0}}
    )

    result = await harness.run_stage(app, sample_query, 'GroupRespondRuleCheckStage', config)

    assert result.result_type == CONTINUE


@pytest.mark.asyncio
async def test_routed_form_action_bypasses_group_rules(app, sample_query):
    harness.as_group(sample_query)
    harness.set_text(sample_query, 'submit')
    sample_query.variables.update({'_routed_by_rule': True, '_dify_form_action': {'id': 'x'}})
    config = harness.legacy_config(
        {'trigger.group-respond-rules': {'at': True, 'prefix': [], 'regexp': [], 'random': 0}}
    )

    result = await harness.run_stage(app, sample_query, 'GroupRespondRuleCheckStage', config)

    assert result.result_type == CONTINUE


# ------------------------------------------------------------- access control


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ('access', 'group', 'expected'),
    [
        ({'mode': 'blacklist', 'blacklist': [], 'whitelist': []}, False, CONTINUE),
        ({'mode': 'blacklist', 'blacklist': ['person_12345'], 'whitelist': []}, False, INTERRUPT),
        ({'mode': 'blacklist', 'blacklist': ['person_*'], 'whitelist': []}, False, INTERRUPT),
        ({'mode': 'blacklist', 'blacklist': ['group_*'], 'whitelist': []}, False, CONTINUE),
        ({'mode': 'blacklist', 'blacklist': ['*_12345'], 'whitelist': []}, False, INTERRUPT),
        ({'mode': 'whitelist', 'blacklist': [], 'whitelist': []}, False, INTERRUPT),
        ({'mode': 'whitelist', 'blacklist': [], 'whitelist': ['person_12345']}, False, CONTINUE),
        ({'mode': 'whitelist', 'blacklist': ['person_12345'], 'whitelist': ['person_12345']}, False, CONTINUE),
        ({'mode': 'blacklist', 'blacklist': ['group_group-1'], 'whitelist': []}, True, INTERRUPT),
        ({'mode': 'blacklist', 'blacklist': ['group_*'], 'whitelist': []}, True, INTERRUPT),
        # *_<id> also matches the sender inside a group.
        ({'mode': 'blacklist', 'blacklist': ['*_member-1'], 'whitelist': []}, True, INTERRUPT),
        ({'mode': 'whitelist', 'blacklist': [], 'whitelist': ['group_group-1']}, True, CONTINUE),
        ({'mode': 'whitelist', 'blacklist': [], 'whitelist': ['group_other']}, True, INTERRUPT),
    ],
)
async def test_access_control(app, sample_query, access, group, expected):
    if group:
        harness.as_group(sample_query)
    config = harness.legacy_config({'trigger.access-control': access})

    result = await harness.run_stage(app, sample_query, 'BanSessionCheckStage', config)

    assert result.result_type == expected
    assert not result.user_notice
    assert bool(result.console_notice) == (expected == INTERRUPT)


# ------------------------------------------------- ignore rules + content filter


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ('overrides', 'text', 'expected', 'notice'),
    [
        ({}, 'hello', CONTINUE, ''),
        ({'trigger.ignore-rules': {'prefix': ['#'], 'regexp': []}}, '#skip me', INTERRUPT, ''),
        ({'trigger.ignore-rules': {'prefix': [], 'regexp': ['^\\d+$']}}, '12345', INTERRUPT, ''),
        ({'trigger.ignore-rules': {'prefix': ['#'], 'regexp': ['^\\d+$']}}, 'hello #', CONTINUE, ''),
        # Sensitive words on inbound text block the message with the default hint.
        ({}, 'a badword here', INTERRUPT, 'Your message contains inappropriate content. Please revise it.'),
        (
            {'output.misc.content-filter-hint': 'custom filter hint'},
            'a badword here',
            INTERRUPT,
            'custom filter hint',
        ),
        # Sensitive-word check off: passes untouched.
        ({'safety.content-filter.check-sensitive-words': False}, 'a badword here', CONTINUE, ''),
        # Scope limited to outbound messages: inbound is not checked at all, not even ignore rules.
        ({'safety.content-filter.scope': 'output-msg'}, 'a badword here', CONTINUE, ''),
        (
            {'safety.content-filter.scope': 'output-msg', 'trigger.ignore-rules': {'prefix': ['#'], 'regexp': []}},
            '#skip me',
            CONTINUE,
            '',
        ),
        # Ignore rules still apply when the sensitive-word check is off.
        (
            {
                'safety.content-filter.check-sensitive-words': False,
                'trigger.ignore-rules': {'prefix': ['#'], 'regexp': []},
            },
            '#skip me',
            INTERRUPT,
            '',
        ),
    ],
)
async def test_inbound_content_filter(app, sample_query, overrides, text, expected, notice):
    harness.set_text(sample_query, text)
    config = harness.legacy_config(overrides)

    result = await harness.run_stage(app, sample_query, 'PreContentFilterStage', config)

    assert result.result_type == expected
    assert _notice_text(result) == notice
    if expected == CONTINUE:
        assert str(result.new_query.message_chain) == text


@pytest.mark.asyncio
async def test_inbound_content_filter_skips_non_text_messages(app, sample_query):
    harness.set_text(sample_query, 'a badword here', platform_message.Image(url='https://example.com/a.png'))
    config = harness.legacy_config({'trigger.ignore-rules': {'prefix': ['a'], 'regexp': []}})

    result = await harness.run_stage(app, sample_query, 'PreContentFilterStage', config)

    assert result.result_type == CONTINUE
    assert len(result.new_query.message_chain) == 2


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ('overrides', 'reply', 'expected_reply'),
    [
        ({}, 'this badword leaks', 'this ******* leaks'),
        ({}, '  clean reply  ', 'clean reply'),
        ({'safety.content-filter.check-sensitive-words': False}, 'this badword leaks', 'this badword leaks'),
        ({'safety.content-filter.scope': 'income-msg'}, 'this badword leaks', 'this badword leaks'),
        ({'safety.content-filter.scope': 'output-msg'}, 'this badword leaks', 'this ******* leaks'),
    ],
)
async def test_outbound_content_filter(app, sample_query, overrides, reply, expected_reply):
    sample_query.resp_messages = [provider_message.Message(role='assistant', content=reply)]
    config = harness.legacy_config(overrides)

    result = await harness.run_stage(app, sample_query, 'PostContentFilterStage', config)

    assert result.result_type == CONTINUE
    assert result.new_query.resp_messages[-1].content == expected_reply


@pytest.mark.asyncio
async def test_outbound_content_filter_skips_non_text_replies(app, sample_query):
    chain = platform_message.MessageChain([platform_message.Plain(text='this badword leaks')])
    sample_query.resp_messages = [chain]
    config = harness.legacy_config()

    result = await harness.run_stage(app, sample_query, 'PostContentFilterStage', config)

    assert result.result_type == CONTINUE
    assert str(result.new_query.resp_messages[-1]) == 'this badword leaks'


# ------------------------------------------------------------------ rate limit


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ('overrides', 'notice'),
    [
        ({}, 'Too many requests. Please try again later.'),
        ({'output.misc.rate-limit-hint': 'slow down'}, 'slow down'),
    ],
)
async def test_rate_limit_drops_with_hint_once_window_is_full(app, sample_query, overrides, notice):
    config = harness.legacy_config(
        {'safety.rate-limit': {'window-length': 3600, 'limitation': 2, 'strategy': 'drop'}, **overrides}
    )
    stage = await harness.build_stage(app, sample_query, 'RequireRateLimitOccupancy', config)

    first = await stage.process(sample_query, 'RequireRateLimitOccupancy')
    second = await stage.process(sample_query, 'RequireRateLimitOccupancy')
    third = await stage.process(sample_query, 'RequireRateLimitOccupancy')
    release = await stage.process(sample_query, 'ReleaseRateLimitOccupancy')

    assert [first.result_type, second.result_type, third.result_type] == [CONTINUE, CONTINUE, INTERRUPT]
    assert _notice_text(third) == notice
    assert release.result_type == CONTINUE


@pytest.mark.asyncio
async def test_rate_limit_counts_sessions_separately(app, sample_query):
    config = harness.legacy_config({'safety.rate-limit': {'window-length': 3600, 'limitation': 1, 'strategy': 'drop'}})
    stage = await harness.build_stage(app, sample_query, 'RequireRateLimitOccupancy', config)

    assert (await stage.process(sample_query, 'RequireRateLimitOccupancy')).result_type == CONTINUE
    assert (await stage.process(sample_query, 'RequireRateLimitOccupancy')).result_type == INTERRUPT
    sample_query.launcher_id = 'another-session'
    assert (await stage.process(sample_query, 'RequireRateLimitOccupancy')).result_type == CONTINUE


# ------------------------------------------------------------------- long text


def _reply_chain(query, *components):
    query.resp_message_chain = [
        platform_message.MessageChain(
            [platform_message.Plain(text=item) if isinstance(item, str) else item for item in components]
        )
    ]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ('long_text', 'reply', 'forwarded'),
    [
        ({'threshold': 5, 'strategy': 'none', 'font-path': ''}, 'x' * 50, False),
        ({'threshold': 5, 'strategy': 'forward', 'font-path': ''}, 'x' * 50, True),
        ({'threshold': 50, 'strategy': 'forward', 'font-path': ''}, 'x' * 50, False),
        # A missing font downgrades the image strategy to a forward message.
        ({'threshold': 5, 'strategy': 'image', 'font-path': '/nonexistent/font.ttf'}, 'x' * 50, True),
    ],
)
async def test_long_text_processing(app, sample_query, long_text, reply, forwarded):
    _reply_chain(sample_query, reply)
    sample_query.adapter.bot_account_id = harness.BOT_ACCOUNT_ID
    config = harness.legacy_config({'output.long-text-processing': long_text})

    result = await harness.run_stage(app, sample_query, 'LongTextProcessStage', config)

    assert result.result_type == CONTINUE
    components = list(result.new_query.resp_message_chain[-1])
    if forwarded:
        assert len(components) == 1 and isinstance(components[0], platform_message.Forward)
        assert str(components[0].node_list[0].message_chain) == reply
    else:
        assert str(result.new_query.resp_message_chain[-1]) == reply


@pytest.mark.asyncio
async def test_long_text_skips_replies_with_non_text_components(app, sample_query):
    _reply_chain(sample_query, 'x' * 50, platform_message.Image(url='https://example.com/a.png'))
    config = harness.legacy_config(
        {'output.long-text-processing': {'threshold': 5, 'strategy': 'forward', 'font-path': ''}}
    )

    result = await harness.run_stage(app, sample_query, 'LongTextProcessStage', config)

    assert result.result_type == CONTINUE
    assert len(result.new_query.resp_message_chain[-1]) == 2


# --------------------------------------------------------------------- sending


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ('group', 'at_sender', 'quote_origin', 'expect_at'),
    [
        (True, True, True, True),
        (True, True, False, True),
        (True, False, True, False),
        (False, True, False, False),
        (False, False, True, False),
    ],
)
async def test_send_applies_at_sender_and_quote(app, sample_query, group, at_sender, quote_origin, expect_at):
    if group:
        harness.as_group(sample_query)
    _reply_chain(sample_query, 'reply')
    config = harness.legacy_config({'output.misc.at-sender': at_sender, 'output.misc.quote-origin': quote_origin})

    result = await harness.run_stage(app, sample_query, 'SendResponseBackStage', config)

    assert result.result_type == CONTINUE
    sample_query.adapter.reply_message.assert_awaited_once()
    kwargs = sample_query.adapter.reply_message.await_args.kwargs
    assert kwargs['quote_origin'] is quote_origin
    sent = list(kwargs['message'])
    if expect_at:
        assert isinstance(sent[0], platform_message.At) and sent[0].target == 'member-1'
        assert str(platform_message.MessageChain(sent[1:])) == 'reply'
    else:
        assert str(kwargs['message']) == 'reply'


@pytest.mark.asyncio
async def test_send_waits_for_the_forced_delay(app, sample_query, monkeypatch):
    slept: list[float] = []

    async def fake_sleep(seconds):
        slept.append(seconds)

    # Patch the module itself: the wait is behaviour, wherever it is implemented.
    monkeypatch.setattr(asyncio, 'sleep', fake_sleep)
    _reply_chain(sample_query, 'reply')
    config = harness.legacy_config({'output.force-delay': {'min': 2, 'max': 2}})

    await harness.run_stage(app, sample_query, 'SendResponseBackStage', config)

    assert slept == [2]
    sample_query.adapter.reply_message.assert_awaited_once()


@pytest.mark.asyncio
async def test_send_streams_chunks_with_quote_setting(app, sample_query):
    sample_query.adapter.is_stream_output_supported = AsyncMock(return_value=True)
    chunk = provider_message.MessageChunk(role='assistant', content='partial', is_final=False)
    sample_query.resp_messages = [chunk]
    _reply_chain(sample_query, 'partial')
    config = harness.legacy_config({'output.misc.at-sender': False, 'output.misc.quote-origin': True})

    await harness.run_stage(app, sample_query, 'SendResponseBackStage', config)

    sample_query.adapter.reply_message.assert_not_awaited()
    kwargs = sample_query.adapter.reply_message_chunk.await_args.kwargs
    assert kwargs['quote_origin'] is True
    assert kwargs['is_final'] is False
    assert kwargs['bot_message'] is chunk


# ---------------------------------------------------------------- user notices


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ('group', 'at_sender', 'quote_origin', 'expect_at'),
    [
        (True, True, False, True),
        (True, False, True, False),
        (False, True, True, False),
    ],
)
async def test_user_notice_follows_at_sender_and_quote(app, sample_query, group, at_sender, quote_origin, expect_at):
    if group:
        harness.as_group(sample_query)
    config = harness.legacy_config({'output.misc.at-sender': at_sender, 'output.misc.quote-origin': quote_origin})

    await harness.deliver_notice(app, sample_query, config, 'something went wrong')

    kwargs = sample_query.adapter.reply_message.await_args.kwargs
    assert kwargs['quote_origin'] is quote_origin
    sent = list(kwargs['message'])
    assert isinstance(sent[0], platform_message.At) is expect_at
    assert str(platform_message.MessageChain(sent[1:] if expect_at else sent)) == 'something went wrong'


# ----------------------------------------------------------------- aggregation


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ('aggregation', 'expected'),
    [
        ({'enabled': False, 'delay': 1.5}, (False, 1.5)),
        ({'enabled': True, 'delay': 3}, (True, 3.0)),
        ({'enabled': True, 'delay': 0.1}, (True, 1.0)),
        ({'enabled': True, 'delay': 99}, (True, 10.0)),
        ({'enabled': True, 'delay': 'oops'}, (True, 1.5)),
    ],
)
async def test_aggregation_settings(app, sample_query, aggregation, expected):
    config = harness.legacy_config({'trigger.message-aggregation': aggregation})

    assert await harness.aggregation_settings(app, sample_query, config) == expected
