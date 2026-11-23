from __future__ import annotations

import typing


async def get_bot_info(adapter, params: dict) -> dict:
    import asyncio

    info = await asyncio.to_thread(adapter.bot.get_bot_info)
    return {
        'user_id': info.user_id,
        'basic_id': info.basic_id,
        'display_name': info.display_name,
        'chat_mode': info.chat_mode,
    }


async def get_profile(adapter, params: dict) -> dict:
    user_id = str(params.get('user_id', ''))
    if not user_id:
        raise ValueError('get_profile requires user_id')
    import asyncio

    profile = await asyncio.to_thread(adapter.bot.get_profile, user_id)
    return {
        'user_id': profile.user_id,
        'display_name': profile.display_name,
        'picture_url': profile.picture_url or '',
        'status_message': profile.status_message or '',
    }


async def get_group_summary(adapter, params: dict) -> dict:
    group_id = str(params.get('group_id', ''))
    if not group_id:
        raise ValueError('get_group_summary requires group_id')
    import asyncio

    summary = await asyncio.to_thread(adapter.bot.get_group_summary, group_id)
    return {
        'group_id': summary.group_id,
        'group_name': summary.group_name,
        'picture_url': summary.picture_url or '',
    }


PLATFORM_API_MAP: dict[str, typing.Callable[[typing.Any, dict], typing.Awaitable[dict]]] = {
    'get_bot_info': get_bot_info,
    'get_profile': get_profile,
    'get_group_summary': get_group_summary,
}
