from __future__ import annotations

import argparse
import asyncio
import json
import os
from pathlib import Path
from typing import Any

from quart import Quart, request

from langbot.pkg.platform.adapters.wecomcs.adapter import WecomCSAdapter
from langbot_plugin.api.definition.abstract.platform.event_logger import AbstractEventLogger
from langbot_plugin.api.entities.builtin.platform import events as platform_events
from langbot_plugin.api.entities.builtin.platform import message as platform_message


TINY_PNG = (
    'data:image/png;base64,'
    'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+/p9sAAAAASUVORK5CYII='
)


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
        redacted = {}
        for key, item in value.items():
            if key.lower() in {'secret', 'token', 'encodingaeskey', 'access_token'}:
                redacted[key] = '<redacted>'
            else:
                redacted[key] = redact(item)
        return redacted
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
    print('WECOMCS_EBA_API', json.dumps(entry, ensure_ascii=False, default=str))


async def run_api(results: list[dict[str, Any]], name: str, func):
    try:
        result = await func()
        record_api(results, name, True, result)
        return result
    except Exception as exc:
        record_api(results, name, False, error=exc)
        return None


def config_from_env() -> dict:
    required = {
        'corpid': os.getenv('WECOMCS_CORPID') or os.getenv('WECOM_CORPID', ''),
        'secret': os.getenv('WECOMCS_SECRET') or os.getenv('WECOMCS_KF_SECRET', ''),
        'token': os.getenv('WECOMCS_TOKEN', ''),
        'EncodingAESKey': os.getenv('WECOMCS_ENCODING_AES_KEY', ''),
    }
    missing = [key for key, value in required.items() if not value]
    if missing:
        raise RuntimeError(f'Missing required WeComCS env vars for fields: {missing}')
    return {
        **required,
        'api_base_url': os.getenv('WECOMCS_API_BASE_URL', 'https://qyapi.weixin.qq.com/cgi-bin'),
    }


async def run_probe(args: argparse.Namespace):
    adapter = WecomCSAdapter(config_from_env(), ProbeLogger())
    events: list[platform_events.EBAEvent] = []
    api_results: list[dict[str, Any]] = []
    first_message = asyncio.Event()
    log_path = Path(args.log)
    log_path.parent.mkdir(parents=True, exist_ok=True)

    async def listener(event, adapter):
        events.append(event)
        with log_path.open('a', encoding='utf-8') as fp:
            fp.write(json.dumps(summarize_event(event), ensure_ascii=False, default=str) + '\n')
        print('WECOMCS_EBA_EVENT', json.dumps(summarize_event(event), ensure_ascii=False, default=str))
        if isinstance(event, platform_events.MessageReceivedEvent):
            first_message.set()

    adapter.register_listener(platform_events.EBAEvent, listener)

    app = Quart(__name__)

    @app.route(args.path, methods=['GET', 'POST'])
    async def callback():
        return await adapter.handle_unified_webhook(args.bot_uuid, '', request)

    server_task = asyncio.create_task(app.run_task(host=args.host, port=args.port))
    try:
        print(f'READY: configure WeCom Customer Service callback URL to http://{args.host}:{args.port}{args.path}')
        print('READY: send a real customer-service message from WeCom/WeChat UI to the bot now.')
        await asyncio.wait_for(first_message.wait(), timeout=args.timeout)

        source = next(event for event in events if isinstance(event, platform_events.MessageReceivedEvent))

        if not args.skip_api:
            await run_api(
                api_results,
                'reply_message:text',
                lambda: adapter.reply_message(
                    source,
                    platform_message.MessageChain([platform_message.Plain(text='WeComCS EBA probe reply')]),
                ),
            )
            await run_api(
                api_results,
                'send_message:text',
                lambda: adapter.send_message(
                    'person',
                    source.chat_id,
                    platform_message.MessageChain([platform_message.Plain(text='WeComCS EBA probe send')]),
                ),
            )
            await run_api(
                api_results,
                'send_message:image',
                lambda: adapter.send_message(
                    'person',
                    source.chat_id,
                    platform_message.MessageChain(
                        [
                            platform_message.Plain(text='WeComCS EBA probe image'),
                            platform_message.Image(base64=TINY_PNG),
                        ]
                    ),
                ),
            )
            await run_api(api_results, 'get_message', lambda: adapter.get_message('private', source.chat_id, source.message_id))
            await run_api(api_results, 'get_user_info', lambda: adapter.get_user_info(source.sender.id))
            await run_api(api_results, 'get_friend_list', lambda: adapter.get_friend_list())
            await run_api(
                api_results,
                'call_platform_api:check_access_token',
                lambda: adapter.call_platform_api('check_access_token', {}),
            )
            await run_api(
                api_results,
                'call_platform_api:get_customer_info',
                lambda: adapter.call_platform_api('get_customer_info', {'external_userid': source.sender.id}),
            )

        summary = {
            'events': [event.type for event in events],
            'api_results': api_results,
            'log_path': str(log_path),
        }
        print('WECOMCS_EBA_SUMMARY', json.dumps(summary, ensure_ascii=False, default=str))
        return summary
    finally:
        server_task.cancel()
        await adapter.kill()


def main():
    parser = argparse.ArgumentParser(description='Live WeCom Customer Service EBA adapter probe.')
    parser.add_argument('--host', default='0.0.0.0')
    parser.add_argument('--port', type=int, default=5313)
    parser.add_argument('--path', default='/wecomcs/callback')
    parser.add_argument('--timeout', type=int, default=180)
    parser.add_argument('--bot-uuid', default='wecomcs-eba-live-probe')
    parser.add_argument('--log', default='data/temp/wecomcs_eba_live_probe.jsonl')
    parser.add_argument('--skip-api', action='store_true')
    args = parser.parse_args()
    asyncio.run(run_probe(args))


if __name__ == '__main__':
    main()
