from __future__ import annotations

import argparse
import asyncio
import base64
import json
import os
from pathlib import Path
from typing import Any

from langbot.pkg.platform.adapters.discord.adapter import DiscordAdapter
from langbot_plugin.api.definition.abstract.platform.event_logger import AbstractEventLogger
from langbot_plugin.api.entities.builtin.platform import entities as platform_entities
from langbot_plugin.api.entities.builtin.platform import errors as platform_errors
from langbot_plugin.api.entities.builtin.platform import events as platform_events
from langbot_plugin.api.entities.builtin.platform import message as platform_message


class ProbeLogger(AbstractEventLogger):
    async def info(self, text, images=None, message_session_id=None, no_throw=True):
        print(f'[info] {text}')

    async def debug(self, text, images=None, message_session_id=None, no_throw=True):
        print(f'[debug] {text}')

    async def warning(self, text, images=None, message_session_id=None, no_throw=True):
        print(f'[warning] {text}')

    async def error(self, text, images=None, message_session_id=None, no_throw=True):
        print(f'[error] {text}')


PNG_1X1 = base64.b64decode(
    'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+/p9sAAAAASUVORK5CYII='
)


def summarize_event(event: platform_events.EBAEvent) -> dict[str, Any]:
    data: dict[str, Any] = {
        'type': event.type,
        'adapter_name': event.adapter_name,
        'timestamp': event.timestamp,
    }
    for field in ('message_id', 'chat_id', 'chat_type', 'reaction', 'is_add', 'action', 'data'):
        if hasattr(event, field):
            value = getattr(event, field)
            data[field] = value.value if hasattr(value, 'value') else value
    for field in ('sender', 'user', 'member', 'group', 'operator', 'inviter'):
        if hasattr(event, field):
            value = getattr(event, field)
            if value is not None and hasattr(value, 'model_dump'):
                data[field] = value.model_dump()
    return data


def chat_type_value(chat_type: platform_entities.ChatType | str) -> str:
    return chat_type.value if hasattr(chat_type, 'value') else str(chat_type)


def record_api(results: list[dict[str, Any]], name: str, ok: bool, result: Any = None, error: Exception | None = None):
    entry: dict[str, Any] = {'name': name, 'ok': ok}
    if result is not None:
        entry['result'] = result
    if error is not None:
        entry['error'] = repr(error)
    results.append(entry)
    print('DISCORD_EBA_API', json.dumps(entry, ensure_ascii=False, default=str))


async def run_api(results: list[dict[str, Any]], name: str, func):
    try:
        result = await func()
        record_api(results, name, True, result)
        return result
    except Exception as exc:
        record_api(results, name, False, error=exc)
        return None


async def run_expected_error(results: list[dict[str, Any]], name: str, func, error_type: type[Exception]):
    try:
        await func()
    except Exception as exc:
        if isinstance(exc, error_type):
            record_api(results, name, True, {'expected_error': type(exc).__name__})
            return
        record_api(results, name, False, error=exc)
        return
    record_api(results, name, False, error=RuntimeError(f'expected {error_type.__name__}'))


async def wait_for_event(events: list[platform_events.EBAEvent], predicate, timeout: int) -> platform_events.EBAEvent:
    deadline = asyncio.get_running_loop().time() + timeout
    seen = 0
    while asyncio.get_running_loop().time() < deadline:
        for event in events[seen:]:
            if predicate(event):
                return event
        seen = len(events)
        await asyncio.sleep(0.2)
    raise TimeoutError('event was not observed before timeout')


async def run_probe(
    token: str,
    client_id: str,
    channel_id: str,
    log_path: Path,
    timeout: int,
    guild_id: str | None,
    moderation_user_id: str | None,
    kick_user_id: str | None,
    allow_invite: bool,
    allow_leave_group: bool,
):
    adapter = DiscordAdapter({'client_id': client_id, 'token': token}, ProbeLogger())
    events: list[platform_events.EBAEvent] = []
    api_results: list[dict[str, Any]] = []
    first_message = asyncio.Event()

    async def listener(event, adapter):
        events.append(event)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with log_path.open('a', encoding='utf-8') as fp:
            fp.write(json.dumps(summarize_event(event), ensure_ascii=False, default=str) + '\n')
        print('DISCORD_EBA_EVENT', json.dumps(summarize_event(event), ensure_ascii=False, default=str))
        if isinstance(event, platform_events.MessageReceivedEvent):
            first_message.set()

    adapter.register_listener(platform_events.EBAEvent, listener)
    run_task = asyncio.create_task(adapter.run_async())

    try:
        print('READY: send a message in the Discord test channel now.')
        await asyncio.wait_for(first_message.wait(), timeout=timeout)
        source = next(event for event in events if isinstance(event, platform_events.MessageReceivedEvent))
        source_chat_type = chat_type_value(source.chat_type)
        target_chat_id = str(source.chat_id)
        guild_id = guild_id or (str(source.group.id) if source.group else None)
        actor_user_id = str(source.sender.id)

        await run_api(
            api_results,
            'reply_message:text_image_file',
            lambda: adapter.reply_message(
                source,
                platform_message.MessageChain(
                    [
                        platform_message.Plain(text='Discord EBA live reply: text'),
                        platform_message.Image(base64=base64.b64encode(PNG_1X1).decode()),
                        platform_message.File(
                            name='discord-eba-live.txt',
                            size=16,
                            base64='data:text/plain;base64,' + base64.b64encode(b'discord-eba-live').decode(),
                        ),
                    ]
                ),
                quote_origin=True,
            ),
        )
        sent = await run_api(
            api_results,
            'send_message:text_image_file',
            lambda: adapter.send_message(
                source_chat_type,
                target_chat_id,
                platform_message.MessageChain(
                    [
                        platform_message.Plain(text='Discord EBA live send_message OK'),
                        platform_message.Image(base64=base64.b64encode(PNG_1X1).decode()),
                    ]
                ),
            ),
        )

        edit_probe = await run_api(
            api_results,
            'send_message:edit_delete_probe',
            lambda: adapter.send_message(
                source_chat_type,
                target_chat_id,
                platform_message.MessageChain([platform_message.Plain(text='Discord EBA edit/delete probe')]),
            ),
        )
        if edit_probe:
            await run_api(
                api_results,
                'edit_message',
                lambda: adapter.edit_message(
                    source_chat_type,
                    target_chat_id,
                    edit_probe.message_id,
                    platform_message.MessageChain([platform_message.Plain(text='Discord EBA edit probe edited')]),
                ),
            )
            await run_api(
                api_results,
                'delete_message',
                lambda: adapter.delete_message(source_chat_type, target_chat_id, edit_probe.message_id),
            )
            await run_api(
                api_results,
                'event_observed:message.edited',
                lambda: wait_for_event(
                    events,
                    lambda event: isinstance(event, platform_events.MessageEditedEvent)
                    and str(event.message_id) == str(edit_probe.message_id),
                    timeout=max(10, timeout // 3),
                ),
            )
            await run_api(
                api_results,
                'event_observed:message.deleted',
                lambda: wait_for_event(
                    events,
                    lambda event: isinstance(event, platform_events.MessageDeletedEvent)
                    and str(event.message_id) == str(edit_probe.message_id),
                    timeout=max(10, timeout // 3),
                ),
            )

        if sent:
            await run_api(
                api_results,
                'forward_message',
                lambda: adapter.forward_message(
                    source_chat_type,
                    target_chat_id,
                    sent.message_id,
                    source_chat_type,
                    target_chat_id,
                ),
            )
            await run_api(
                api_results,
                'call_platform_api:add_reaction',
                lambda: adapter.call_platform_api(
                    'add_reaction',
                    {'channel_id': target_chat_id, 'message_id': sent.message_id, 'emoji': '👍'},
                ),
            )
            await run_api(
                api_results,
                'call_platform_api:remove_reaction',
                lambda: adapter.call_platform_api(
                    'remove_reaction',
                    {'channel_id': target_chat_id, 'message_id': sent.message_id, 'emoji': '👍'},
                ),
            )

        await run_api(api_results, 'get_user_info', lambda: adapter.get_user_info(actor_user_id))
        await run_expected_error(
            api_results,
            'upload_file:not_supported',
            lambda: adapter.upload_file(b'discord-eba-upload', 'discord-eba-upload.txt'),
            platform_errors.NotSupportedError,
        )
        await run_api(api_results, 'get_file_url', lambda: adapter.get_file_url('https://cdn.discordapp.com/file.txt'))
        await run_api(
            api_results,
            'call_platform_api:get_channel',
            lambda: adapter.call_platform_api('get_channel', {'channel_id': target_chat_id}),
        )
        await run_api(
            api_results,
            'call_platform_api:typing',
            lambda: adapter.call_platform_api('typing', {'channel_id': target_chat_id}),
        )

        pin_probe = await run_api(
            api_results,
            'send_message:pin_probe',
            lambda: adapter.send_message(
                source_chat_type,
                target_chat_id,
                platform_message.MessageChain([platform_message.Plain(text='Discord EBA pin probe')]),
            ),
        )
        if pin_probe:
            await run_api(
                api_results,
                'call_platform_api:pin_message',
                lambda: adapter.call_platform_api(
                    'pin_message',
                    {'channel_id': target_chat_id, 'message_id': pin_probe.message_id},
                ),
            )
            await run_api(
                api_results,
                'call_platform_api:unpin_message',
                lambda: adapter.call_platform_api(
                    'unpin_message',
                    {'channel_id': target_chat_id, 'message_id': pin_probe.message_id},
                ),
            )

        if guild_id:
            await run_api(api_results, 'get_group_info', lambda: adapter.get_group_info(guild_id))
            await run_api(api_results, 'get_group_member_list', lambda: adapter.get_group_member_list(guild_id))
            await run_api(
                api_results,
                'get_group_member_info',
                lambda: adapter.get_group_member_info(guild_id, actor_user_id),
            )
            await run_api(
                api_results,
                'call_platform_api:get_guild',
                lambda: adapter.call_platform_api('get_guild', {'guild_id': guild_id}),
            )
            await run_api(
                api_results,
                'call_platform_api:get_guild_channels',
                lambda: adapter.call_platform_api('get_guild_channels', {'guild_id': guild_id}),
            )
            await run_api(
                api_results,
                'call_platform_api:get_guild_roles',
                lambda: adapter.call_platform_api('get_guild_roles', {'guild_id': guild_id}),
            )
            if allow_invite:
                await run_api(
                    api_results,
                    'call_platform_api:create_invite',
                    lambda: adapter.call_platform_api('create_invite', {'channel_id': target_chat_id, 'max_age': 300}),
                )
            else:
                record_api(api_results, 'call_platform_api:create_invite', False, error=RuntimeError('skipped'))

            if moderation_user_id:
                await run_api(
                    api_results,
                    'mute_member',
                    lambda: adapter.mute_member(guild_id, moderation_user_id, duration=30),
                )
                await run_api(api_results, 'unmute_member', lambda: adapter.unmute_member(guild_id, moderation_user_id))
            else:
                record_api(api_results, 'mute_member', False, error=RuntimeError('skipped'))
                record_api(api_results, 'unmute_member', False, error=RuntimeError('skipped'))

            if kick_user_id:
                await run_api(api_results, 'kick_member', lambda: adapter.kick_member(guild_id, kick_user_id))
            else:
                record_api(api_results, 'kick_member', False, error=RuntimeError('skipped'))

            if allow_leave_group:
                await run_api(api_results, 'leave_group', lambda: adapter.leave_group(guild_id))
            else:
                record_api(api_results, 'leave_group', False, error=RuntimeError('skipped'))
        else:
            for name in (
                'get_group_info',
                'get_group_member_list',
                'get_group_member_info',
                'call_platform_api:get_guild',
                'call_platform_api:get_guild_channels',
                'call_platform_api:get_guild_roles',
                'call_platform_api:create_invite',
                'mute_member',
                'unmute_member',
                'kick_member',
                'leave_group',
            ):
                record_api(api_results, name, False, error=RuntimeError('skipped: no guild id'))

        await asyncio.sleep(3)
    finally:
        await adapter.kill()
        run_task.cancel()
        summary = {
            'events': [summarize_event(event) for event in events],
            'event_types': [event.type for event in events],
            'api_results': api_results,
            'api_passed': [result['name'] for result in api_results if result['ok']],
            'api_failed': [result for result in api_results if not result['ok']],
        }
        print('SUMMARY', json.dumps(summary, ensure_ascii=False, default=str))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--token', default=os.getenv('DISCORD_BOT_TOKEN', ''))
    parser.add_argument('--client-id', default=os.getenv('DISCORD_CLIENT_ID', ''))
    parser.add_argument('--channel-id', default=os.getenv('DISCORD_EBA_CHANNEL_ID', ''))
    parser.add_argument('--guild-id', default=os.getenv('DISCORD_EBA_GUILD_ID'))
    parser.add_argument('--moderation-user-id', default=os.getenv('DISCORD_EBA_MODERATION_USER_ID'))
    parser.add_argument('--kick-user-id', default=os.getenv('DISCORD_EBA_KICK_USER_ID'))
    parser.add_argument('--log', default='data/temp/live_discord_eba_probe.jsonl')
    parser.add_argument('--timeout', type=int, default=90)
    parser.add_argument('--allow-invite', action='store_true')
    parser.add_argument('--allow-leave-group', action='store_true')
    args = parser.parse_args()

    if not args.token:
        raise SystemExit('Set DISCORD_BOT_TOKEN or pass --token')
    if not args.client_id:
        raise SystemExit('Set DISCORD_CLIENT_ID or pass --client-id')
    if not args.channel_id:
        raise SystemExit('Set DISCORD_EBA_CHANNEL_ID or pass --channel-id')

    log_path = Path(args.log)
    if log_path.exists():
        log_path.unlink()
    asyncio.run(
        run_probe(
            args.token,
            args.client_id,
            args.channel_id,
            log_path,
            args.timeout,
            args.guild_id,
            args.moderation_user_id,
            args.kick_user_id,
            args.allow_invite,
            args.allow_leave_group,
        )
    )


if __name__ == '__main__':
    main()
