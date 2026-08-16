from __future__ import annotations

import typing


async def get_mode(adapter, params: dict) -> dict:
    return {
        'webhook': True,
        'bot_account_id': adapter.bot_account_id,
    }


async def auth_test(adapter, params: dict) -> dict:
    response = await adapter.bot.client.auth_test()
    if hasattr(response, 'data'):
        return dict(response.data)
    return dict(response)


PLATFORM_API_MAP: dict[str, typing.Callable[[typing.Any, dict], typing.Awaitable[dict]]] = {
    'get_mode': get_mode,
    'auth_test': auth_test,
}
