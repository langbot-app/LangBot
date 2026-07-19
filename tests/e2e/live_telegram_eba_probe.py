from __future__ import annotations

import argparse
import asyncio
import base64
import json
import os
import re
from pathlib import Path
from typing import Any

import telegram

from langbot.pkg.platform.adapters.telegram.adapter import TelegramAdapter
from langbot_plugin.api.definition.abstract.platform.event_logger import AbstractEventLogger
from langbot_plugin.api.entities.builtin.platform import entities as platform_entities
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


def summarize_event(event: platform_events.EBAEvent) -> dict:
    data = {
        'type': event.type,
        'adapter_name': event.adapter_name,
        'timestamp': event.timestamp,
    }
    for field in (
        'message_id',
        'chat_id',
        'chat_type',
        'reaction',
        'is_add',
        'action',
        'data',
    ):
        if hasattr(event, field):
            value = getattr(event, field)
            if hasattr(value, 'value'):
                value = value.value
            data[field] = value
    if hasattr(event, 'member') and event.member is not None:
        data['member'] = event.member.model_dump()
    if hasattr(event, 'group') and event.group is not None:
        data['group'] = event.group.model_dump()
    if hasattr(event, 'operator') and event.operator is not None:
        data['operator'] = event.operator.model_dump()
    return data


def chat_type_value(chat_type: platform_entities.ChatType | str) -> str:
    return chat_type.value if hasattr(chat_type, 'value') else str(chat_type)


def record_api(results: list[dict[str, Any]], name: str, ok: bool, result: Any = None, error: Exception | None = None):
    entry = {'name': name, 'ok': ok}
    if result is not None:
        entry['result'] = redact_sensitive(result)
    if error is not None:
        entry['error'] = repr(error)
    results.append(entry)
    print('TELEGRAM_EBA_API', json.dumps(entry, ensure_ascii=False, default=str))


def redact_sensitive(value: Any) -> Any:
    if isinstance(value, str):
        return re.sub(r'bot\d+:[A-Za-z0-9_-]+', 'bot<redacted>', value)
    if isinstance(value, dict):
        return {key: redact_sensitive(item) for key, item in value.items()}
    if isinstance(value, list):
        return [redact_sensitive(item) for item in value]
    if isinstance(value, int | float | bool) or value is None:
        return value
    return redact_sensitive(str(value))


async def run_api(results: list[dict[str, Any]], name: str, func):
    try:
        result = await func()
        record_api(results, name, True, result)
        return result
    except Exception as exc:
        record_api(results, name, False, error=exc)
        return None


async def run_expected_error(results: list[dict[str, Any]], name: str, func, error_type_name: str):
    try:
        await func()
    except Exception as exc:
        if type(exc).__name__ == error_type_name:
            record_api(results, name, True, {'expected_error': error_type_name})
            return
        record_api(results, name, False, error=exc)
        return
    record_api(results, name, False, error=RuntimeError(f'expected {error_type_name}'))


async def run_probe(
    token: str,
    log_path: Path,
    timeout: int,
    group_chat_id: str | None,
    moderation_user_id: str | None,
    kick_user_id: str | None,
    allow_group_mutation: bool,
    allow_unpin_all: bool,
    allow_leave_group: bool,
):
    adapter = TelegramAdapter(
        {
            'token': token,
            'markdown_card': False,
            'enable-stream-reply': False,
        },
        ProbeLogger(),
    )
    events: list[platform_events.EBAEvent] = []
    api_results: list[dict[str, Any]] = []
    first_message = asyncio.Event()
    callback_event = asyncio.Event()
    callback_query_id: str | None = None
    callback_probe_message_id: int | None = None
    awaiting_callback = False

    async def listener(event, adapter):
        nonlocal callback_query_id
        events.append(event)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with log_path.open('a', encoding='utf-8') as fp:
            fp.write(json.dumps(summarize_event(event), ensure_ascii=False) + '\n')
        print('TELEGRAM_EBA_EVENT', json.dumps(summarize_event(event), ensure_ascii=False))
        if isinstance(event, platform_events.MessageReceivedEvent):
            first_message.set()
        if isinstance(event, platform_events.PlatformSpecificEvent) and event.action == 'callback_query':
            message_id = event.data.get('message_id')
            if awaiting_callback and message_id == callback_probe_message_id:
                callback_query_id = event.data.get('callback_query_id')
                callback_event.set()

    adapter.register_listener(platform_events.EBAEvent, listener)
    await adapter.run_async()

    try:
        print('READY: send a private or group message to the Telegram test bot now.')
        await asyncio.wait_for(first_message.wait(), timeout=timeout)
        source = next(event for event in events if isinstance(event, platform_events.MessageReceivedEvent))
        source_chat_type = chat_type_value(source.chat_type)
        group_id = group_chat_id or (str(source.chat_id) if source_chat_type == 'group' else None)
        actor_user_id = str(source.sender.id)
        target_chat_id = str(source.chat_id)

        await run_api(
            api_results,
            'reply_message:text_image_file',
            lambda: adapter.reply_message(
                source,
                platform_message.MessageChain(
                    [
                        platform_message.Plain(text='EBA live reply: text'),
                        platform_message.Image(base64=base64.b64encode(PNG_1X1).decode()),
                        platform_message.File(
                            name='eba-live.txt',
                            size=8,
                            base64='data:text/plain;base64,' + base64.b64encode(b'eba-live').decode(),
                        ),
                    ]
                ),
                quote_origin=True,
            ),
        )
        await run_api(
            api_results,
            'send_message:text_image_file',
            lambda: adapter.send_message(
                source_chat_type,
                target_chat_id,
                platform_message.MessageChain(
                    [
                        platform_message.Plain(text='EBA live send_message OK'),
                        platform_message.Image(base64=base64.b64encode(PNG_1X1).decode()),
                        platform_message.File(
                            name='eba-send-live.txt',
                            size=13,
                            base64='data:text/plain;base64,' + base64.b64encode(b'eba-send-live').decode(),
                        ),
                    ]
                ),
            ),
        )

        edit_probe = await run_api(
            api_results,
            'bot.send_message:edit_delete_probe',
            lambda: adapter.bot.send_message(chat_id=target_chat_id, text='EBA edit/delete probe'),
        )
        if edit_probe:
            await run_api(
                api_results,
                'edit_message',
                lambda: adapter.edit_message(
                    source_chat_type,
                    target_chat_id,
                    edit_probe.message_id,
                    platform_message.MessageChain([platform_message.Plain(text='EBA edit probe edited')]),
                ),
            )
            await run_api(
                api_results,
                'delete_message',
                lambda: adapter.delete_message(source_chat_type, target_chat_id, edit_probe.message_id),
            )

        forward_probe = await run_api(
            api_results,
            'bot.send_message:forward_probe',
            lambda: adapter.bot.send_message(chat_id=target_chat_id, text='EBA forward probe'),
        )
        if forward_probe:
            forwarded = await run_api(
                api_results,
                'forward_message',
                lambda: adapter.forward_message(
                    source_chat_type,
                    target_chat_id,
                    forward_probe.message_id,
                    source_chat_type,
                    target_chat_id,
                ),
            )
            if forwarded:
                await run_api(
                    api_results,
                    'delete_message:forwarded_cleanup',
                    lambda: adapter.delete_message(source_chat_type, target_chat_id, forwarded.message_id),
                )
            await run_api(
                api_results,
                'delete_message:forward_source_cleanup',
                lambda: adapter.delete_message(source_chat_type, target_chat_id, forward_probe.message_id),
            )

        document_probe = await run_api(
            api_results,
            'bot.send_document:get_file_url_probe',
            lambda: adapter.bot.send_document(
                chat_id=target_chat_id,
                document=telegram.InputFile(b'eba-file-url', filename='eba-file-url.txt'),
            ),
        )
        if document_probe and document_probe.document:
            await run_api(
                api_results,
                'get_file_url',
                lambda: adapter.get_file_url(document_probe.document.file_id),
            )

        await run_api(
            api_results,
            'get_user_info',
            lambda: adapter.get_user_info(actor_user_id),
        )
        await run_expected_error(
            api_results,
            'upload_file:not_supported',
            lambda: adapter.upload_file(b'eba-upload-live', 'eba-upload-live.txt'),
            'NotSupportedError',
        )
        await run_api(
            api_results,
            'call_platform_api:send_chat_action',
            lambda: adapter.call_platform_api('send_chat_action', {'chat_id': target_chat_id, 'action': 'typing'}),
        )

        callback_probe = await run_api(
            api_results,
            'bot.send_message:callback_probe',
            lambda: adapter.bot.send_message(
                chat_id=target_chat_id,
                text='EBA callback probe',
                reply_markup=telegram.InlineKeyboardMarkup(
                    [[telegram.InlineKeyboardButton('callback probe', callback_data='eba-callback-probe')]]
                ),
            ),
        )
        if callback_probe:
            callback_probe_message_id = callback_probe.message_id
            awaiting_callback = True
            callback_event.clear()
            print('READY: click the callback button to test answer_callback_query.')
            try:
                await asyncio.wait_for(callback_event.wait(), timeout=max(15, timeout // 3))
            except asyncio.TimeoutError:
                record_api(
                    api_results,
                    'call_platform_api:answer_callback_query',
                    False,
                    error=TimeoutError('callback button was not clicked before timeout'),
                )
            else:
                await run_api(
                    api_results,
                    'call_platform_api:answer_callback_query',
                    lambda: adapter.call_platform_api(
                        'answer_callback_query',
                        {'callback_query_id': callback_query_id, 'text': 'EBA callback answered'},
                    ),
                )
            finally:
                awaiting_callback = False

        if group_id:
            await run_api(api_results, 'get_group_info', lambda: adapter.get_group_info(group_id))
            await run_api(api_results, 'get_group_member_list', lambda: adapter.get_group_member_list(group_id))
            await run_api(
                api_results,
                'get_group_member_info',
                lambda: adapter.get_group_member_info(group_id, actor_user_id),
            )
            await run_api(
                api_results,
                'call_platform_api:get_chat_administrators',
                lambda: adapter.call_platform_api('get_chat_administrators', {'chat_id': group_id}),
            )
            await run_api(
                api_results,
                'call_platform_api:get_chat_member_count',
                lambda: adapter.call_platform_api('get_chat_member_count', {'chat_id': group_id}),
            )
            await run_api(
                api_results,
                'call_platform_api:create_chat_invite_link',
                lambda: adapter.call_platform_api(
                    'create_chat_invite_link', {'chat_id': group_id, 'name': 'eba-probe'}
                ),
            )

            pin_probe = await run_api(
                api_results,
                'bot.send_message:pin_probe',
                lambda: adapter.bot.send_message(chat_id=group_id, text='EBA pin probe'),
            )
            if pin_probe:
                await run_api(
                    api_results,
                    'call_platform_api:pin_message',
                    lambda: adapter.call_platform_api(
                        'pin_message',
                        {'chat_id': group_id, 'message_id': pin_probe.message_id, 'disable_notification': True},
                    ),
                )
                await run_api(
                    api_results,
                    'call_platform_api:unpin_message',
                    lambda: adapter.call_platform_api(
                        'unpin_message',
                        {'chat_id': group_id, 'message_id': pin_probe.message_id},
                    ),
                )
                await run_api(
                    api_results,
                    'delete_message:pin_probe_cleanup',
                    lambda: adapter.delete_message('group', group_id, pin_probe.message_id),
                )

            if allow_unpin_all:
                await run_api(
                    api_results,
                    'call_platform_api:unpin_all_messages',
                    lambda: adapter.call_platform_api('unpin_all_messages', {'chat_id': group_id}),
                )
            else:
                record_api(api_results, 'call_platform_api:unpin_all_messages', False, error=RuntimeError('skipped'))

            if allow_group_mutation:
                chat = await adapter.bot.get_chat(chat_id=group_id)
                original_title = chat.title or 'EBA Probe Group'
                original_description = chat.description or ''
                await run_api(
                    api_results,
                    'call_platform_api:set_chat_title',
                    lambda: adapter.call_platform_api(
                        'set_chat_title',
                        {'chat_id': group_id, 'title': f'{original_title} EBA'},
                    ),
                )
                await run_api(
                    api_results,
                    'call_platform_api:set_chat_title:restore',
                    lambda: adapter.call_platform_api('set_chat_title', {'chat_id': group_id, 'title': original_title}),
                )
                await run_api(
                    api_results,
                    'call_platform_api:set_chat_description',
                    lambda: adapter.call_platform_api(
                        'set_chat_description',
                        {'chat_id': group_id, 'description': 'EBA probe temporary description'},
                    ),
                )
                await run_api(
                    api_results,
                    'call_platform_api:set_chat_description:restore',
                    lambda: adapter.call_platform_api(
                        'set_chat_description',
                        {'chat_id': group_id, 'description': original_description},
                    ),
                )
            else:
                record_api(api_results, 'call_platform_api:set_chat_title', False, error=RuntimeError('skipped'))
                record_api(api_results, 'call_platform_api:set_chat_description', False, error=RuntimeError('skipped'))

            if moderation_user_id:
                await run_api(
                    api_results,
                    'mute_member',
                    lambda: adapter.mute_member(group_id, moderation_user_id, duration=30),
                )
                await run_api(
                    api_results,
                    'unmute_member',
                    lambda: adapter.unmute_member(group_id, moderation_user_id),
                )
            else:
                record_api(api_results, 'mute_member', False, error=RuntimeError('skipped'))
                record_api(api_results, 'unmute_member', False, error=RuntimeError('skipped'))

            if kick_user_id:
                await run_api(api_results, 'kick_member', lambda: adapter.kick_member(group_id, kick_user_id))
            else:
                record_api(api_results, 'kick_member', False, error=RuntimeError('skipped'))

            if allow_leave_group:
                await run_api(api_results, 'leave_group', lambda: adapter.leave_group(group_id))
            else:
                record_api(api_results, 'leave_group', False, error=RuntimeError('skipped'))
        else:
            for name in (
                'get_group_info',
                'get_group_member_list',
                'get_group_member_info',
                'mute_member',
                'unmute_member',
                'kick_member',
                'leave_group',
                'call_platform_api:get_chat_administrators',
                'call_platform_api:get_chat_member_count',
                'call_platform_api:create_chat_invite_link',
                'call_platform_api:pin_message',
                'call_platform_api:unpin_message',
                'call_platform_api:unpin_all_messages',
                'call_platform_api:set_chat_title',
                'call_platform_api:set_chat_description',
            ):
                record_api(api_results, name, False, error=RuntimeError('skipped: no group chat id'))

        await asyncio.sleep(3)
    finally:
        await adapter.kill()
        summary = {
            'events': [summarize_event(event) for event in events],
            'event_types': [event.type for event in events],
            'api_results': api_results,
            'api_passed': [result['name'] for result in api_results if result['ok']],
            'api_failed': [result for result in api_results if not result['ok']],
        }
        print('SUMMARY', json.dumps(summary, ensure_ascii=False, default=str))


async def run_callback_probe(token: str, chat_id: str, timeout: int):
    adapter = TelegramAdapter(
        {
            'token': token,
            'markdown_card': False,
            'enable-stream-reply': False,
        },
        ProbeLogger(),
    )
    api_results: list[dict[str, Any]] = []

    callback_probe = await adapter.bot.send_message(
        chat_id=chat_id,
        text='EBA callback-only probe',
        reply_markup=telegram.InlineKeyboardMarkup(
            [[telegram.InlineKeyboardButton('callback probe', callback_data='eba-callback-only-probe')]]
        ),
    )
    deadline = asyncio.get_running_loop().time() + timeout
    offset: int | None = None
    try:
        print('READY: click the callback-only probe button.')
        callback_query_id: str | None = None
        while asyncio.get_running_loop().time() < deadline and callback_query_id is None:
            updates = await adapter.bot.get_updates(
                offset=offset,
                timeout=2,
                allowed_updates=['callback_query'],
            )
            for update in updates:
                offset = update.update_id + 1
                callback_query = update.callback_query
                if callback_query is None or callback_query.message is None:
                    continue
                if callback_query.message.message_id == callback_probe.message_id:
                    callback_query_id = callback_query.id
                    break
        if callback_query_id is None:
            raise TimeoutError('callback button was not clicked before timeout')
        await run_api(
            api_results,
            'call_platform_api:answer_callback_query',
            lambda: adapter.call_platform_api(
                'answer_callback_query',
                {'callback_query_id': callback_query_id, 'text': 'EBA callback answered'},
            ),
        )
    finally:
        print(
            'SUMMARY',
            json.dumps(
                {
                    'api_results': api_results,
                    'api_passed': [result['name'] for result in api_results if result['ok']],
                    'api_failed': [result for result in api_results if not result['ok']],
                },
                ensure_ascii=False,
                default=str,
            ),
        )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--token', default=os.getenv('TELEGRAM_BOT_TOKEN', ''))
    parser.add_argument('--log', default='data/temp/live_telegram_eba_probe.jsonl')
    parser.add_argument('--timeout', type=int, default=90)
    parser.add_argument('--group-chat-id', default=os.getenv('TELEGRAM_EBA_GROUP_CHAT_ID'))
    parser.add_argument('--moderation-user-id', default=os.getenv('TELEGRAM_EBA_MODERATION_USER_ID'))
    parser.add_argument('--kick-user-id', default=os.getenv('TELEGRAM_EBA_KICK_USER_ID'))
    parser.add_argument('--allow-group-mutation', action='store_true')
    parser.add_argument('--allow-unpin-all', action='store_true')
    parser.add_argument('--allow-leave-group', action='store_true')
    parser.add_argument('--callback-chat-id', default=os.getenv('TELEGRAM_EBA_CALLBACK_CHAT_ID'))
    args = parser.parse_args()

    if not args.token:
        raise SystemExit('Set TELEGRAM_BOT_TOKEN or pass --token')

    log_path = Path(args.log)
    if log_path.exists():
        log_path.unlink()
    if args.callback_chat_id:
        asyncio.run(run_callback_probe(args.token, args.callback_chat_id, args.timeout))
        return
    asyncio.run(
        run_probe(
            args.token,
            log_path,
            args.timeout,
            args.group_chat_id,
            args.moderation_user_id,
            args.kick_user_id,
            args.allow_group_mutation,
            args.allow_unpin_all,
            args.allow_leave_group,
        )
    )


if __name__ == '__main__':
    main()
