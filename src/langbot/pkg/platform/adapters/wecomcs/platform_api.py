from __future__ import annotations

import typing

from langbot.libs.wecom_customer_service_api.api import WecomCSClient


async def check_access_token(bot: WecomCSClient, params: dict) -> dict:
    return {'valid': await bot.check_access_token()}


async def refresh_access_token(bot: WecomCSClient, params: dict) -> dict:
    bot.access_token = await bot.get_access_token(bot.secret)
    return {'ok': bool(bot.access_token)}


async def get_customer_info(bot: WecomCSClient, params: dict) -> dict:
    user_id = params.get('external_userid') or params.get('user_id') or params.get('userid')
    if not user_id:
        raise ValueError('external_userid is required')
    info = await bot.get_customer_info(str(user_id))
    return info or {}


PLATFORM_API_MAP: dict[str, typing.Callable[[WecomCSClient, dict], typing.Awaitable[dict]]] = {
    'check_access_token': check_access_token,
    'refresh_access_token': refresh_access_token,
    'get_customer_info': get_customer_info,
}
