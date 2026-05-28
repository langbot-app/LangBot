from __future__ import annotations

import typing


async def get_mode(bot, params: dict) -> dict:
    return {
        'mode': params.get('mode') or ('passive' if hasattr(bot, 'msg_queue') else 'drop'),
        'longer_response': hasattr(bot, 'msg_queue'),
    }


async def get_cached_response_status(bot, params: dict) -> dict:
    message_id = params.get('message_id') or params.get('msg_id')
    user_id = params.get('user_id') or params.get('from_user')
    if hasattr(bot, 'generated_content'):
        return {'pending': str(message_id) in {str(key) for key in bot.generated_content}}
    if hasattr(bot, 'msg_queue'):
        queue = bot.msg_queue.get(str(user_id), []) if user_id is not None else []
        return {'queued': len(queue)}
    return {'pending': False}


PLATFORM_API_MAP: dict[str, typing.Callable[[typing.Any, dict], typing.Awaitable[dict]]] = {
    'get_mode': get_mode,
    'get_cached_response_status': get_cached_response_status,
}
