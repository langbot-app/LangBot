from __future__ import annotations

import typing


async def get_mode(adapter, params: dict) -> dict:
    return {
        'webhook': not adapter.config.get('socket_mode', False),
        'socket_mode': adapter.config.get('socket_mode', False),
        'bot_account_id': adapter.bot_account_id,
    }


async def auth_test(adapter, params: dict) -> dict:
    response = await adapter.bot.client.auth_test()
    if hasattr(response, 'data'):
        return dict(response.data)
    return dict(response)


async def post_message(adapter, params: dict) -> dict:
    payload = {'channel': params['channel'], 'text': params['text']}
    if params.get('thread_ts'):
        payload['thread_ts'] = params['thread_ts']
    response = await adapter.bot.client.chat_postMessage(**payload)
    return {
        'ts': response['ts'],
        'channel': response['channel'],
        'thread_ts': response.get('message', {}).get('thread_ts') or payload.get('thread_ts'),
    }


async def get_message_context(adapter, params: dict) -> dict:
    key = (str(params['channel']), str(params['message_id']))
    event = adapter._message_cache.get(key)
    if event is None:
        raise KeyError('message_not_found')
    raw = event.source_platform_object['event']
    return {field: raw.get(field) for field in ('ts', 'thread_ts', 'channel', 'user', 'parent_user_id')}


PLATFORM_API_MAP: dict[str, typing.Callable[[typing.Any, dict], typing.Awaitable[dict]]] = {
    'get_mode': get_mode,
    'auth_test': auth_test,
    'post_message': post_message,
    'get_message_context': get_message_context,
}
