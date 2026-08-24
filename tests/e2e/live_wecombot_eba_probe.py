from __future__ import annotations

import argparse
import asyncio
import json
import os
from pathlib import Path
from typing import Any

from quart import Quart, request

from langbot.pkg.platform.adapters.wecombot.adapter import WecomBotAdapter
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


def redact(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: '<redacted>' if key.lower() in {'secret', 'token', 'encodingaeskey', 'encrypt', 'aeskey'} else redact(item)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [redact(item) for item in value]
    return value


def summarize_event(event: platform_events.EBAEvent) -> dict:
    data = {
        'type': event.type,
        'adapter_name': event.adapter_name,
        'timestamp': event.timestamp,
    }
    for field in ('message_id', 'chat_id', 'chat_type', 'action', 'data', 'feedback_id', 'feedback_type'):
        if hasattr(event, field):
            value = getattr(event, field)
            if hasattr(value, 'value'):
                value = value.value
            data[field] = redact(value)
    if hasattr(event, 'sender') and event.sender is not None:
        data['sender'] = event.sender.model_dump()
    if hasattr(event, 'group') and event.group is not None:
        data['group'] = event.group.model_dump()
    if hasattr(event, 'message_chain') and event.message_chain is not None:
        data['message_chain'] = event.message_chain.model_dump()
    return data


def record_api(results: list[dict[str, Any]], name: str, ok: bool, result: Any = None, error: Exception | None = None):
    entry = {'name': name, 'ok': ok}
    if result is not None:
        entry['result'] = redact(result)
    if error is not None:
        entry['error'] = repr(error)
    results.append(entry)
    print('WECOMBOT_EBA_API', json.dumps(entry, ensure_ascii=False, default=str))


async def run_api(results: list[dict[str, Any]], name: str, func):
    try:
        result = await func()
        record_api(results, name, True, result)
        return result
    except Exception as exc:
        record_api(results, name, False, error=exc)
        return None


def config_from_env(enable_webhook: bool) -> dict:
    config = {
        'BotId': os.getenv('WECOMBOT_BOT_ID', ''),
        'robot_name': os.getenv('WECOMBOT_ROBOT_NAME', ''),
        'enable-webhook': enable_webhook,
        'Secret': os.getenv('WECOMBOT_SECRET', ''),
        'Token': os.getenv('WECOMBOT_TOKEN', ''),
        'EncodingAESKey': os.getenv('WECOMBOT_ENCODING_AES_KEY', ''),
        'Corpid': os.getenv('WECOMBOT_CORPID', ''),
        'enable-stream-reply': os.getenv('WECOMBOT_ENABLE_STREAM_REPLY', '1') != '0',
    }
    required = ['BotId', 'Secret'] if not enable_webhook else ['Token', 'EncodingAESKey', 'Corpid']
    missing = [key for key in required if not config.get(key)]
    if missing:
        raise RuntimeError(f'Missing required WeComBot env vars for fields: {missing}')
    return config


async def run_probe(args: argparse.Namespace):
    adapter = WecomBotAdapter(config_from_env(args.webhook), ProbeLogger())
    events: list[platform_events.EBAEvent] = []
    api_results: list[dict[str, Any]] = []
    first_message = asyncio.Event()
    log_path = Path(args.log)
    log_path.parent.mkdir(parents=True, exist_ok=True)

    async def listener(event, adapter):
        events.append(event)
        with log_path.open('a', encoding='utf-8') as fp:
            fp.write(json.dumps(summarize_event(event), ensure_ascii=False, default=str) + '\n')
        print('WECOMBOT_EBA_EVENT', json.dumps(summarize_event(event), ensure_ascii=False, default=str))
        if isinstance(event, platform_events.MessageReceivedEvent):
            first_message.set()

    adapter.register_listener(platform_events.EBAEvent, listener)

    run_task = None
    server_task = None
    if args.webhook:
        app = Quart(__name__)

        @app.route(args.path, methods=['GET', 'POST'])
        async def callback():
            return await adapter.handle_unified_webhook(args.bot_uuid, '', request)

        server_task = asyncio.create_task(app.run_task(host=args.host, port=args.port))
        print(f'READY: configure WeComBot callback URL to http://{args.host}:{args.port}{args.path}')
    else:
        run_task = asyncio.create_task(adapter.run_async())
        print('READY: WeComBot WebSocket long connection started; no webhook URL is required.')

    try:
        print('READY: send a real WeComBot message to the bot now.')
        await asyncio.wait_for(first_message.wait(), timeout=args.timeout)

        source = next(event for event in events if isinstance(event, platform_events.MessageReceivedEvent))

        if not args.skip_api:
            await run_api(
                api_results,
                'reply_message:text',
                lambda: adapter.reply_message(
                    source,
                    platform_message.MessageChain([platform_message.Plain(text='WeComBot EBA probe reply')]),
                ),
            )
            if not args.webhook:
                await run_api(
                    api_results,
                    'send_message:text',
                    lambda: adapter.send_message(
                        'group' if source.chat_type.value == 'group' else 'person',
                        source.chat_id,
                        platform_message.MessageChain([platform_message.Plain(text='WeComBot EBA probe send')]),
                    ),
                )
            await run_api(api_results, 'get_message', lambda: adapter.get_message(source.chat_type.value, source.chat_id, source.message_id))
            await run_api(api_results, 'get_user_info', lambda: adapter.get_user_info(source.sender.id))
            if source.group:
                await run_api(api_results, 'get_group_info', lambda: adapter.get_group_info(source.group.id))
                await run_api(api_results, 'get_group_member_list', lambda: adapter.get_group_member_list(source.group.id))
            await run_api(api_results, 'call_platform_api:is_websocket_mode', lambda: adapter.call_platform_api('is_websocket_mode', {}))
            await run_api(
                api_results,
                'call_platform_api:get_stream_session_status',
                lambda: adapter.call_platform_api('get_stream_session_status', {'message_id': source.message_id}),
            )

        summary = {
            'events': [event.type for event in events],
            'api_results': api_results,
            'log_path': str(log_path),
            'mode': 'webhook' if args.webhook else 'websocket',
        }
        print('WECOMBOT_EBA_SUMMARY', json.dumps(summary, ensure_ascii=False, default=str))
        return summary
    finally:
        if server_task:
            server_task.cancel()
        if run_task:
            run_task.cancel()
        await adapter.kill()


def main():
    parser = argparse.ArgumentParser(description='Live WeComBot EBA adapter probe.')
    parser.add_argument('--webhook', action='store_true', help='Use webhook mode. Default is WebSocket long connection mode.')
    parser.add_argument('--host', default='0.0.0.0')
    parser.add_argument('--port', type=int, default=5313)
    parser.add_argument('--path', default='/wecombot/callback')
    parser.add_argument('--timeout', type=int, default=180)
    parser.add_argument('--bot-uuid', default='wecombot-eba-live-probe')
    parser.add_argument('--log', default='data/temp/wecombot_eba_live_probe.jsonl')
    parser.add_argument('--skip-api', action='store_true')
    args = parser.parse_args()
    asyncio.run(run_probe(args))


if __name__ == '__main__':
    main()
