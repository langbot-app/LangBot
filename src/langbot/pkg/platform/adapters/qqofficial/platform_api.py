from __future__ import annotations

import typing


async def check_access_token(adapter, params: dict) -> dict:
    ok = await adapter.bot.check_access_token()
    return {'ok': bool(ok), 'expires_at': getattr(adapter.bot, 'access_token_expiry_time', None)}


async def refresh_access_token(adapter, params: dict) -> dict:
    adapter.bot.access_token = ''
    adapter.bot.access_token_expiry_time = None
    await adapter.bot.get_access_token()
    return {'ok': bool(adapter.bot.access_token), 'expires_at': adapter.bot.access_token_expiry_time}


async def get_gateway_url(adapter, params: dict) -> dict:
    url = await adapter.bot.get_gateway_url()
    return {'url': url}


async def get_mode(adapter, params: dict) -> dict:
    return {
        'webhook': bool(adapter.enable_webhook),
        'stream_reply': bool(adapter.config.get('enable-stream-reply') or adapter.config.get('enable_stream_reply')),
        'bot_account_id': adapter.bot_account_id,
    }


PLATFORM_API_MAP: dict[str, typing.Callable[[typing.Any, dict], typing.Awaitable[dict]]] = {
    'check_access_token': check_access_token,
    'refresh_access_token': refresh_access_token,
    'get_gateway_url': get_gateway_url,
    'get_mode': get_mode,
}

