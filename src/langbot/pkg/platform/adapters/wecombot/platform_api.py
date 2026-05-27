from __future__ import annotations

import typing


async def is_websocket_mode(bot, params: dict) -> dict:
    return {'websocket': hasattr(bot, 'bot_id') and not hasattr(bot, 'Token')}


async def get_stream_session_status(bot, params: dict) -> dict:
    msg_id = str(params.get('message_id') or params.get('msg_id') or '')
    if not msg_id:
        raise ValueError('message_id is required')
    if hasattr(bot, 'stream_sessions'):
        stream_id = bot.stream_sessions.get_stream_id_by_msg(msg_id)
        session = bot.stream_sessions.get_session(stream_id) if stream_id else None
        return {'stream_id': stream_id, 'active': session is not None}
    stream_key = getattr(bot, '_stream_ids', {}).get(msg_id)
    if not stream_key:
        return {'stream_id': None, 'active': False}
    _req_id, _sep, stream_id = stream_key.partition('|')
    return {'stream_id': stream_id, 'active': True}


async def send_markdown(bot, params: dict) -> dict:
    chat_id = params.get('chat_id') or params.get('chatid') or params.get('target_id')
    content = params.get('content')
    if not chat_id:
        raise ValueError('chat_id is required')
    if not content:
        raise ValueError('content is required')
    if not hasattr(bot, 'send_message'):
        raise ValueError('send_markdown is only available in WebSocket mode')
    result = await bot.send_message(str(chat_id), str(content), msgtype='markdown')
    return {'ok': True, 'raw': result}


PLATFORM_API_MAP: dict[str, typing.Callable[[typing.Any, dict], typing.Awaitable[dict]]] = {
    'is_websocket_mode': is_websocket_mode,
    'get_stream_session_status': get_stream_session_status,
    'send_markdown': send_markdown,
}
