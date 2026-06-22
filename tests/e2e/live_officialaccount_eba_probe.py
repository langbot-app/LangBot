from __future__ import annotations

import argparse
import asyncio
import json
import os
from pathlib import Path
from typing import Any

from quart import Quart, request

from langbot.pkg.platform.adapters.officialaccount.adapter import OfficialAccountAdapter
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
            key: '<redacted>' if key.lower() in {'secret', 'token', 'encodingaeskey', 'encrypt', 'appsecret'} else redact(item)
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
    for field in ('message_id', 'chat_id', 'chat_type', 'action', 'data'):
        if hasattr(event, field):
            value = getattr(event, field)
            if hasattr(value, 'value'):
                value = value.value
            data[field] = redact(value)
    if hasattr(event, 'sender') and event.sender is not None:
        data['sender'] = event.sender.model_dump()
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
    print('OFFICIALACCOUNT_EBA_API', json.dumps(entry, ensure_ascii=False, default=str))


async def run_api(results: list[dict[str, Any]], name: str, func):
    try:
        result = await func()
        record_api(results, name, True, result)
        return result
    except Exception as exc:
        record_api(results, name, False, error=exc)
        return None


def config_from_env() -> dict:
    config = {
        'token': os.getenv('OFFICIALACCOUNT_TOKEN', ''),
        'EncodingAESKey': os.getenv('OFFICIALACCOUNT_ENCODING_AES_KEY', ''),
        'AppSecret': os.getenv('OFFICIALACCOUNT_APP_SECRET', ''),
        'AppID': os.getenv('OFFICIALACCOUNT_APP_ID', ''),
        'Mode': os.getenv('OFFICIALACCOUNT_MODE', 'drop'),
        'LoadingMessage': os.getenv('OFFICIALACCOUNT_LOADING_MESSAGE', 'AI正在思考中，请发送任意内容获取回复。'),
        'api_base_url': os.getenv('OFFICIALACCOUNT_API_BASE_URL', 'https://api.weixin.qq.com'),
    }
    missing = [key for key in ('token', 'EncodingAESKey', 'AppSecret', 'AppID', 'Mode') if not config.get(key)]
    if missing:
        raise RuntimeError(f'Missing required OfficialAccount env vars for fields: {missing}')
    return config


async def run_probe(args: argparse.Namespace):
    adapter = OfficialAccountAdapter(config_from_env(), ProbeLogger())
    events: list[platform_events.EBAEvent] = []
    api_results: list[dict[str, Any]] = []
    first_message = asyncio.Event()
    log_path = Path(args.log)
    log_path.parent.mkdir(parents=True, exist_ok=True)

    async def listener(event, adapter):
        events.append(event)
        with log_path.open('a', encoding='utf-8') as fp:
            fp.write(json.dumps(summarize_event(event), ensure_ascii=False, default=str) + '\n')
        print('OFFICIALACCOUNT_EBA_EVENT', json.dumps(summarize_event(event), ensure_ascii=False, default=str))
        if isinstance(event, platform_events.MessageReceivedEvent):
            first_message.set()

    adapter.register_listener(platform_events.EBAEvent, listener)

    app = Quart(__name__)

    @app.route('/callback', methods=['GET', 'POST'])
    async def callback():
        return await adapter.handle_unified_webhook('probe', '', request)

    server_task = asyncio.create_task(app.run_task(host=args.host, port=args.port))
    try:
        await asyncio.wait_for(first_message.wait(), timeout=args.timeout)
        first = next(event for event in events if isinstance(event, platform_events.MessageReceivedEvent))
        await run_api(api_results, 'reply_message', lambda: adapter.reply_message(first, platform_message.MessageChain([platform_message.Plain(text=args.reply_text)])))
        await run_api(api_results, 'get_message', lambda: adapter.get_message(first.chat_type.value, first.chat_id, first.message_id))
        await run_api(api_results, 'get_user_info', lambda: adapter.get_user_info(first.sender.id))
        await run_api(api_results, 'get_friend_list', adapter.get_friend_list)
        await run_api(api_results, 'call_platform_api.get_mode', lambda: adapter.call_platform_api('get_mode', {}))
    finally:
        server_task.cancel()
        try:
            await server_task
        except asyncio.CancelledError:
            pass

    summary = {
        'events': [event.type for event in events],
        'api_results': api_results,
        'log': str(log_path),
    }
    print('OFFICIALACCOUNT_EBA_SUMMARY', json.dumps(summary, ensure_ascii=False, default=str))


def main():
    parser = argparse.ArgumentParser(description='Live OfficialAccount EBA adapter probe')
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--port', type=int, default=5311)
    parser.add_argument('--timeout', type=float, default=300)
    parser.add_argument('--log', default='data/temp/officialaccount_eba_probe.jsonl')
    parser.add_argument('--reply-text', default='OfficialAccount EBA probe reply')
    args = parser.parse_args()
    asyncio.run(run_probe(args))


if __name__ == '__main__':
    main()
