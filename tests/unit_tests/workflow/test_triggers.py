from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from langbot.pkg.command import builtin
from langbot.pkg.workflow import operations
from langbot.pkg.workflow.scheduler import WorkflowScheduler
from langbot.pkg.workflow.triggers import (
    cron_matches,
    parse_command_args,
    schedule_due,
    validate_triggers,
)


def at(text):
    return datetime.fromisoformat(text)


def test_cron_fields_lists_ranges_and_steps():
    assert cron_matches('0 8 * * *', at('2026-11-28T08:00'))
    assert not cron_matches('0 8 * * *', at('2026-11-28T08:01'))
    assert cron_matches('*/15 9-17 * * 1-5', at('2026-11-30T09:45'))  # Monday
    assert not cron_matches('*/15 9-17 * * 1-5', at('2026-11-29T09:45'))  # Sunday
    assert cron_matches('30 7 * * 0', at('2026-11-29T07:30'))
    assert cron_matches('30 7 * * 7', at('2026-11-29T07:30'))
    # Both day fields restricted: either one matches, as in standard cron.
    assert cron_matches('0 0 1 * 1', at('2026-12-01T00:00'))
    assert cron_matches('0 0 1 * 1', at('2026-11-30T00:00'))


def test_every_minutes_counts_from_midnight():
    assert schedule_due({'every': 30}, at('2026-11-28T10:30'))
    assert not schedule_due({'every': 30}, at('2026-11-28T10:31'))


@pytest.mark.parametrize('expression', ['0 8 * *', '61 * * * *', '* * * * 8', 'x * * * *'])
def test_invalid_cron_is_rejected(expression):
    with pytest.raises(ValueError):
        validate_triggers(
            [{'type': 'schedule', 'cron': expression, 'bot_uuid': 'b', 'targets': [{'type': 'group', 'id': '1'}]}]
        )


def test_command_arguments_last_takes_the_rest():
    trigger = {'args': [{'name': 'city', 'required': True}, {'name': 'note'}]}
    assert parse_command_args(trigger, '北京 明天 会下雨吗') == ({'city': '北京', 'note': '明天 会下雨吗'}, [])
    assert parse_command_args(trigger, '') == ({'city': '', 'note': ''}, ['city'])
    assert parse_command_args({'args': []}, 'ignored') == ({}, [])


def test_validation_of_each_trigger_kind():
    triggers = [
        {'type': 'message'},
        {'type': 'command', 'name': '天气', 'aliases': ['tq'], 'args': [{'name': 'city'}], 'bots': 'all'},
        {'type': 'schedule', 'every': 60, 'bot_uuid': 'b', 'targets': [{'type': 'group', 'id': '42'}]},
        {'type': 'webhook', 'bot_uuid': 'b'},
        {'type': 'event', 'events': ['group.member_joined']},
    ]
    validate_triggers(triggers)
    assert len(triggers[3]['secret']) >= 16
    kept = triggers[3]['secret']
    validate_triggers(triggers)
    assert triggers[3]['secret'] == kept
    for bad in (
        [{'type': 'command', 'name': 'has space'}],
        [{'type': 'command', 'name': 'a', 'aliases': ['a']}],
        [{'type': 'schedule', 'every': 0, 'bot_uuid': 'b', 'targets': [{'type': 'group', 'id': '1'}]}],
        [{'type': 'schedule', 'every': 5, 'bot_uuid': 'b', 'targets': []}],
        [{'type': 'webhook'}],
        [{'type': 'unknown'}],
    ):
        with pytest.raises(ValueError):
            validate_triggers(bad)


def bot(workspace, uuid):
    instance = SimpleNamespace(
        enable=True,
        workspace_uuid=workspace,
        bot_entity=SimpleNamespace(uuid=uuid),
        execution_context=SimpleNamespace(workspace_uuid=workspace, bot_uuid=uuid),
        run_triggered_workflow=AsyncMock(return_value=('e', None)),
    )

    async def delivery(handler, *args, **kwargs):
        return await handler(*args, **kwargs)

    instance._run_event_delivery = delivery
    return instance


async def test_scheduler_fires_each_slot_once_per_target_in_workflow_timezone():
    sender = bot('w', 'bot-a')
    workflow = {
        'uuid': 'wf',
        'timezone': 'Asia/Shanghai',
        'triggers': [
            {
                'type': 'schedule',
                'cron': '0 8 * * *',
                'bot_uuid': 'bot-a',
                'targets': [{'type': 'group', 'id': '1'}, {'type': 'group', 'id': '2'}],
            },
            {'type': 'schedule', 'every': 1, 'bot_uuid': 'not-running', 'targets': [{'type': 'group', 'id': '3'}]},
        ],
    }
    ap = SimpleNamespace(
        platform_mgr=SimpleNamespace(bots=[sender]),
        workflow_service=SimpleNamespace(workflows_with_trigger=AsyncMock(return_value=[workflow])),
        logger=SimpleNamespace(warning=lambda *_: None),
    )
    scheduler = WorkflowScheduler(ap)
    # 08:00 in Shanghai is 00:00 UTC.
    moment = datetime(2026, 11, 28, 0, 0, tzinfo=timezone.utc)
    for task in await scheduler.tick(moment):
        await task
    assert sender.run_triggered_workflow.await_count == 2
    assert await scheduler.tick(moment) == []
    assert await scheduler.tick(datetime(2026, 11, 28, 0, 1, tzinfo=timezone.utc)) == []


async def test_help_lists_workflow_commands_the_sender_may_run():
    workflow = {
        'name': '天气',
        'triggers': [
            {'type': 'command', 'name': '天气', 'args': [{'name': 'city'}], 'bots': 'all'},
            {'type': 'command', 'name': 'ban', 'admin_only': True, 'bots': 'all'},
            {'type': 'command', 'name': 'other', 'bots': ['someone-else']},
        ],
    }
    runtime_bot = SimpleNamespace(
        ap=SimpleNamespace(workflow_service=SimpleNamespace(command_workflows=AsyncMock(return_value=[workflow]))),
        execution_context=None,
        bot_entity=SimpleNamespace(uuid='me'),
        _effective_plugin_commands=AsyncMock(return_value=[]),
    )
    text = await builtin._help(
        runtime_bot,
        None,
        {'prefixes': ['/'], 'builtin': {name: {'enabled': False} for name in builtin.DESCRIPTIONS}},
        False,
    )
    assert '/天气 <city> — 天气' in text
    assert '/ban' not in text and '/other' not in text


async def test_platform_step_rejects_unsupported_actions_and_calls_supported_ones():
    adapter = SimpleNamespace(
        get_supported_apis=lambda: ['mute_member', 'call_platform_api'],
        mute_member=AsyncMock(return_value=None),
        call_platform_api=AsyncMock(return_value={'ok': True}),
    )
    running = SimpleNamespace(adapter=adapter)
    ap = SimpleNamespace(platform_mgr=SimpleNamespace(get_bot_by_uuid=AsyncMock(return_value=running)))
    runtime = SimpleNamespace(execution_context=SimpleNamespace(bot_uuid='b'))
    await operations.platform(
        {'action': 'mute_member', 'params': {'group_id': '1', 'user_id': '2', 'duration': '60'}}, ap, runtime
    )
    adapter.mute_member.assert_awaited_once_with(group_id='1', user_id='2', duration=60)
    result = await operations.platform(
        {'action': 'call_platform_api', 'params': {'action': 'set_group_card', 'params': {'card': 'x'}}}, ap, runtime
    )
    assert result == {'result': {'ok': True}}
    with pytest.raises(ValueError, match='not supported'):
        await operations.platform({'action': 'kick_member', 'params': {}}, ap, runtime)


async def test_tts_saves_audio_as_media_and_asr_reads_it_back():
    saved = {}

    async def save_media(data, mime):
        saved['data'] = data
        return 'hash', 'media/abc.mp3', len(data)

    async def get_media(name):
        return saved['data'], 'audio/mpeg'

    tts_model = SimpleNamespace(
        extra_args={'voice': 'alloy'},
        model_entity=SimpleNamespace(extra_args={}),
        execution_context=None,
        provider=SimpleNamespace(invoke_tts=AsyncMock(return_value=(b'ID3audio', 'audio/mpeg'))),
    )
    asr_model = SimpleNamespace(
        execution_context=None, provider=SimpleNamespace(invoke_asr=AsyncMock(return_value=' 你好 '))
    )
    ap = SimpleNamespace(
        model_mgr=SimpleNamespace(
            get_tts_model_by_uuid=AsyncMock(return_value=tts_model),
            get_asr_model_by_uuid=AsyncMock(return_value=asr_model),
        ),
        storage_mgr=SimpleNamespace(media_cache=SimpleNamespace(save_media=save_media, get_media=get_media)),
    )
    runtime = SimpleNamespace(execution_context=None)
    voice = (await operations.tts({'model_uuid': 'm', 'text': '你好'}, ap, runtime))['voice']
    assert voice == '/api/v1/files/media/abc.mp3'
    assert tts_model.provider.invoke_tts.await_args.kwargs['extra_args'] == {'response_format': 'mp3', 'voice': 'alloy'}
    assert await operations.asr({'model_uuid': 'm', 'voice': voice}, ap, runtime) == {'text': '你好'}
    with pytest.raises(ValueError):
        await operations.asr({'model_uuid': 'm', 'voice': 'https://example.com/a.mp3'}, ap, runtime)
