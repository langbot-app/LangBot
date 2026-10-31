from __future__ import annotations

import typing

from langbot.libs.wecom_api.api import WecomClient


async def check_access_token(bot: WecomClient, params: dict) -> dict:
    return {'valid': await bot.check_access_token()}


async def refresh_access_token(bot: WecomClient, params: dict) -> dict:
    bot.access_token = await bot.get_access_token(bot.secret)
    return {'ok': bool(bot.access_token)}


async def get_user_info(bot: WecomClient, params: dict) -> dict:
    user_id = params.get('user_id') or params.get('userid')
    if not user_id:
        raise ValueError('user_id is required')
    return await bot.get_user_info(str(user_id))


async def send_to_all(bot: WecomClient, params: dict) -> dict:
    content = params.get('content')
    agent_id = params.get('agent_id') or params.get('agentid')
    if not content:
        raise ValueError('content is required')
    if agent_id is None:
        raise ValueError('agent_id is required')
    await bot.send_to_all(str(content), int(agent_id))
    return {'ok': True}


PLATFORM_API_MAP: dict[str, typing.Callable[[WecomClient, dict], typing.Awaitable[dict]]] = {
    'check_access_token': check_access_token,
    'refresh_access_token': refresh_access_token,
    'get_user_info': get_user_info,
    'send_to_all': send_to_all,
}
