from __future__ import annotations

import argparse
import asyncio
import base64
import json
import os
from pathlib import Path

import telegram

from langbot.pkg.platform.adapters.telegram.adapter import TelegramAdapter
from langbot_plugin.api.definition.abstract.platform.event_logger import AbstractEventLogger
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
    return data


async def run_probe(token: str, log_path: Path, timeout: int):
    adapter = TelegramAdapter(
        {
            'token': token,
            'markdown_card': False,
            'enable-stream-reply': False,
        },
        ProbeLogger(),
    )
    events: list[platform_events.EBAEvent] = []
    first_message = asyncio.Event()

    async def listener(event, adapter):
        events.append(event)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with log_path.open('a', encoding='utf-8') as fp:
            fp.write(json.dumps(summarize_event(event), ensure_ascii=False) + '\n')
        print('TELEGRAM_EBA_EVENT', json.dumps(summarize_event(event), ensure_ascii=False))
        if isinstance(event, platform_events.MessageReceivedEvent):
            first_message.set()

    adapter.register_listener(platform_events.EBAEvent, listener)
    await adapter.run_async()

    try:
        print('READY: send a private or group message to the Telegram test bot now.')
        await asyncio.wait_for(first_message.wait(), timeout=timeout)
        source = next(event for event in events if isinstance(event, platform_events.MessageReceivedEvent))

        await adapter.reply_message(
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
        )
        await adapter.send_message(
            source.chat_type.value if hasattr(source.chat_type, 'value') else str(source.chat_type),
            source.chat_id,
            platform_message.MessageChain([platform_message.Plain(text='EBA live send_message OK')]),
        )

        edit_probe = await adapter.bot.send_message(chat_id=source.chat_id, text='EBA edit/delete probe')
        await adapter.edit_message(
            str(source.chat_type),
            source.chat_id,
            edit_probe.message_id,
            platform_message.MessageChain([platform_message.Plain(text='EBA edit probe edited')]),
        )
        await adapter.delete_message(str(source.chat_type), source.chat_id, edit_probe.message_id)

        await adapter.bot.send_message(
            chat_id=source.chat_id,
            text='EBA callback probe',
            reply_markup=telegram.InlineKeyboardMarkup(
                [[telegram.InlineKeyboardButton('callback probe', callback_data='eba-callback-probe')]]
            ),
        )

        if str(source.chat_type) == 'ChatType.GROUP' or getattr(source.chat_type, 'value', '') == 'group':
            group_info = await adapter.get_group_info(source.chat_id)
            print('GROUP_INFO', group_info.model_dump())
            members = await adapter.get_group_member_list(source.chat_id)
            print('GROUP_MEMBER_LIST_COUNT', len(members))
            await adapter.call_platform_api('send_chat_action', {'chat_id': source.chat_id, 'action': 'typing'})
            count = await adapter.call_platform_api('get_chat_member_count', {'chat_id': source.chat_id})
            print('GROUP_MEMBER_COUNT', count)

        print('READY: click the callback button or react to a bot message if you want live callback/reaction events.')
        await asyncio.sleep(max(5, timeout // 3))
    finally:
        await adapter.kill()
        summary = {
            'events': [summarize_event(event) for event in events],
            'event_types': [event.type for event in events],
        }
        print('SUMMARY', json.dumps(summary, ensure_ascii=False))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--token', default=os.getenv('TELEGRAM_BOT_TOKEN', ''))
    parser.add_argument('--log', default='data/temp/live_telegram_eba_probe.jsonl')
    parser.add_argument('--timeout', type=int, default=90)
    args = parser.parse_args()

    if not args.token:
        raise SystemExit('Set TELEGRAM_BOT_TOKEN or pass --token')

    log_path = Path(args.log)
    if log_path.exists():
        log_path.unlink()
    asyncio.run(run_probe(args.token, log_path, args.timeout))


if __name__ == '__main__':
    main()
