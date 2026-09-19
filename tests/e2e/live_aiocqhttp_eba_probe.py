from __future__ import annotations

import argparse
import asyncio
import base64
import json
import time
from collections import Counter
from pathlib import Path

from langbot.pkg.platform.adapters.aiocqhttp.adapter import AiocqhttpAdapter
from langbot_plugin.api.definition.abstract.platform.event_logger import AbstractEventLogger
from langbot_plugin.api.entities.builtin.platform import events as platform_events
from langbot_plugin.api.entities.builtin.platform import message as platform_message


class ProbeLogger(AbstractEventLogger):
    async def info(self, text, images=None, message_session_id=None, no_throw=True):
        print(f'[info] {text}')

    async def debug(self, text, images=None, message_session_id=None, no_throw=True):
        print(f'[debug] {text}')

    async def warning(self, text, images=None, message_session_id=None, no_throw=True):
        print(f'[warn] {text}')

    async def error(self, text, images=None, message_session_id=None, no_throw=True):
        print(f'[error] {text}')


def dump_event(event: platform_events.Event) -> dict:
    data = event.model_dump(exclude={'source_platform_object'})
    data['event_class'] = type(event).__name__
    return data


async def main():
    parser = argparse.ArgumentParser(description='Live OneBot v11 / aiocqhttp EBA probe for Matcha or a real endpoint.')
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--port', type=int, default=2280)
    parser.add_argument('--access-token', default='')
    parser.add_argument('--timeout', type=int, default=120)
    parser.add_argument('--target-type', choices=['private', 'group'], default=None)
    parser.add_argument('--target-id', default=None)
    parser.add_argument(
        '--component-sweep', action='store_true', help='Send text, mention, image, file, face, and forward samples.'
    )
    parser.add_argument('--destructive', action='store_true', help='Enable delete/mute/kick/leave style APIs.')
    parser.add_argument('--out', default='data/temp/aiocqhttp_eba_live_probe.jsonl')
    args = parser.parse_args()

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_fp = out_path.open('a', encoding='utf-8')

    adapter = AiocqhttpAdapter(
        {'host': args.host, 'port': args.port, 'access-token': args.access_token},
        ProbeLogger(),
    )

    observed: list[platform_events.Event] = []
    first_message = asyncio.Event()

    async def listener(event, adapter):
        observed.append(event)
        out_fp.write(json.dumps(dump_event(event), ensure_ascii=False, default=str) + '\n')
        out_fp.flush()
        print(f'[event] {type(event).__name__} {event.type}')
        if isinstance(event, platform_events.MessageReceivedEvent):
            first_message.set()

    adapter.register_listener(platform_events.EBAEvent, listener)

    async def call_api(name: str, awaitable, timeout: int = 8):
        try:
            return await asyncio.wait_for(awaitable, timeout=timeout)
        except Exception as exc:
            api_results[name] = f'skip:{type(exc).__name__}:{exc}'
            return None

    task = asyncio.create_task(adapter.run_async())
    print(f'Listening on ws://{args.host}:{args.port}/ws/ . Trigger events from Matcha now.')

    api_results: dict[str, str] = {}
    try:
        try:
            await asyncio.wait_for(first_message.wait(), timeout=args.timeout)
            first = next(event for event in observed if isinstance(event, platform_events.MessageReceivedEvent))
            target_type = args.target_type or ('group' if first.chat_type.value == 'group' else 'private')
            target_id = args.target_id or str(first.chat_id)

            reply = await call_api(
                'reply_message',
                adapter.reply_message(
                    first,
                    platform_message.MessageChain([platform_message.Plain(text='aiocqhttp EBA reply probe')]),
                    quote_origin=True,
                ),
            )
            if reply:
                api_results['reply_message'] = f'ok:{reply.message_id}'

            sent = await call_api(
                'send_message',
                adapter.send_message(
                    target_type,
                    target_id,
                    platform_message.MessageChain([platform_message.Plain(text='aiocqhttp EBA send probe')]),
                ),
            )
            if sent:
                api_results['send_message'] = f'ok:{sent.message_id}'

            if args.component_sweep:
                png_base64 = base64.b64encode(
                    base64.b64decode(
                        'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+P+/HgAFeAJ5mZtH5QAAAABJRU5ErkJggg=='
                    )
                ).decode()
                component_cases = {
                    'component:text_at_face': platform_message.MessageChain(
                        [
                            platform_message.Plain(text='component sweep '),
                            platform_message.At(target=str(first.sender.id)),
                            platform_message.Plain(text=' '),
                            platform_message.AtAll(),
                            platform_message.Plain(text=' '),
                            platform_message.Face(face_id=14, face_name='微笑'),
                        ]
                    ),
                    'component:image_base64': platform_message.MessageChain(
                        [
                            platform_message.Plain(text='image component '),
                            platform_message.Image(base64=f'data:image/png;base64,{png_base64}'),
                        ]
                    ),
                    'component:file': platform_message.MessageChain(
                        [
                            platform_message.Plain(text='file component '),
                            platform_message.File(name='probe.txt', url='https://example.com/probe.txt'),
                        ]
                    ),
                }
                if target_type == 'group':
                    component_cases['component:forward'] = platform_message.MessageChain(
                        [
                            platform_message.Forward(
                                node_list=[
                                    platform_message.ForwardMessageNode(
                                        sender_id=adapter.bot_account_id or '960164003',
                                        sender_name='LangBot',
                                        message_chain=platform_message.MessageChain(
                                            [platform_message.Plain(text='forward node 1')]
                                        ),
                                    ),
                                    platform_message.ForwardMessageNode(
                                        sender_id=str(first.sender.id),
                                        sender_name=first.sender.nickname or 'Matcha',
                                        message_chain=platform_message.MessageChain(
                                            [platform_message.Plain(text='forward node 2')]
                                        ),
                                    ),
                                ]
                            )
                        ]
                    )
                for name, chain in component_cases.items():
                    result = await call_api(name, adapter.send_message(target_type, target_id, chain))
                    if result:
                        api_results[name] = f'ok:{result.message_id}'

            if sent and sent.message_id:
                fetched = await call_api('get_message', adapter.get_message(target_type, target_id, sent.message_id))
                if fetched:
                    api_results['get_message'] = f'ok:{fetched.message_id}'
                if args.destructive:
                    deleted = await call_api(
                        'delete_message',
                        adapter.delete_message(target_type, target_id, sent.message_id),
                    )
                    if deleted is not None:
                        api_results['delete_message'] = 'ok'

            if target_type == 'group':
                group = await call_api('get_group_info', adapter.get_group_info(target_id))
                if group:
                    api_results['get_group_info'] = f'ok:{group.id}'
                members = await call_api('get_group_member_list', adapter.get_group_member_list(target_id))
                if members is not None:
                    api_results['get_group_member_list'] = f'ok:{len(members)}'
                if members:
                    member = await call_api(
                        'get_group_member_info',
                        adapter.get_group_member_info(target_id, members[0].user.id),
                    )
                    if member:
                        api_results['get_group_member_info'] = f'ok:{member.user.id}'

            for action in ('get_login_info', 'get_status', 'get_version_info', 'can_send_image', 'can_send_record'):
                result = await call_api(
                    f'call_platform_api:{action}',
                    adapter.call_platform_api(action, {}),
                )
                if result is not None:
                    api_results[f'call_platform_api:{action}'] = 'ok'
        except asyncio.TimeoutError:
            api_results['first_message'] = 'timeout'
    finally:
        task.cancel()
        try:
            await asyncio.wait_for(task, timeout=3)
        except (asyncio.CancelledError, asyncio.TimeoutError):
            pass
        out_fp.close()

    counts = Counter(event.type for event in observed)
    print(
        json.dumps(
            {
                'output': str(out_path),
                'observed_events': counts,
                'api_results': api_results,
                'duration_seconds': round(time.monotonic(), 3),
            },
            ensure_ascii=False,
            default=str,
            indent=2,
        )
    )


if __name__ == '__main__':
    asyncio.run(main())
