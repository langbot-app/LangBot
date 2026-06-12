from __future__ import annotations

import argparse
import asyncio
import json
import os
from pathlib import Path
from typing import Any

from quart import Quart, request

from langbot.pkg.platform.adapters.slack.adapter import SlackAdapter
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
        secret_keys = {'token', 'signing_secret', 'authorization', 'access_token'}
        return {key: '<redacted>' if key.lower() in secret_keys else redact(item) for key, item in value.items()}
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
    print('SLACK_EBA_API', json.dumps(entry, ensure_ascii=False, default=str))


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
        'bot_token': os.getenv('SLACK_BOT_TOKEN', ''),
        'signing_secret': os.getenv('SLACK_SIGNING_SECRET', ''),
        'bot_user_id': os.getenv('SLACK_BOT_USER_ID', ''),
    }
    missing = [key for key in ('bot_token', 'signing_secret') if not config.get(key)]
    if missing:
        raise RuntimeError(f'Missing required Slack env vars for fields: {missing}')
    return config


async def run_probe(args: argparse.Namespace):
    adapter = SlackAdapter(config_from_env(), ProbeLogger())
    events: list[platform_events.EBAEvent] = []
    api_results: list[dict[str, Any]] = []
    first_message = asyncio.Event()
    log_path = Path(args.log)
    log_path.parent.mkdir(parents=True, exist_ok=True)

    async def listener(event, adapter):
        events.append(event)
        summary = summarize_event(event)
        with log_path.open('a', encoding='utf-8') as fp:
            fp.write(json.dumps(summary, ensure_ascii=False, default=str) + '\n')
        print('SLACK_EBA_EVENT', json.dumps(summary, ensure_ascii=False, default=str))
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
        if getattr(first, 'group', None):
            await run_api(api_results, 'get_group_info', lambda: adapter.get_group_info(first.group.id))
            await run_api(api_results, 'get_group_member_info', lambda: adapter.get_group_member_info(first.group.id, first.sender.id))
            await run_api(api_results, 'get_group_member_list', lambda: adapter.get_group_member_list(first.group.id))
        await run_api(api_results, 'call_platform_api.get_mode', lambda: adapter.call_platform_api('get_mode', {}))
        await run_api(api_results, 'call_platform_api.auth_test', lambda: adapter.call_platform_api('auth_test', {}))
    finally:
        server_task.cancel()
        try:
            await server_task
        except asyncio.CancelledError:
            pass
        await adapter.kill()

    summary = {
        'events': [event.type for event in events],
        'api_results': api_results,
        'log': str(log_path),
    }
    print('SLACK_EBA_SUMMARY', json.dumps(summary, ensure_ascii=False, default=str))


def main():
    parser = argparse.ArgumentParser(description='Live Slack EBA adapter probe')
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--port', type=int, default=5313)
    parser.add_argument('--timeout', type=float, default=300)
    parser.add_argument('--log', default='data/temp/slack_eba_probe.jsonl')
    parser.add_argument('--reply-text', default='Slack EBA probe reply')
    args = parser.parse_args()
    asyncio.run(run_probe(args))


if __name__ == '__main__':
    main()
