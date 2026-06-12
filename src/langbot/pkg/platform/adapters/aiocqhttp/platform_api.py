from __future__ import annotations

import typing

import aiocqhttp


async def _call(bot: aiocqhttp.CQHttp, action: str, params: dict[str, typing.Any]) -> dict:
    result = await bot.call_action(action, **params)
    return result or {}


async def get_login_info(bot: aiocqhttp.CQHttp, params: dict) -> dict:
    return await _call(bot, 'get_login_info', params)


async def get_status(bot: aiocqhttp.CQHttp, params: dict) -> dict:
    return await _call(bot, 'get_status', params)


async def get_version_info(bot: aiocqhttp.CQHttp, params: dict) -> dict:
    return await _call(bot, 'get_version_info', params)


async def get_group_honor_info(bot: aiocqhttp.CQHttp, params: dict) -> dict:
    return await _call(bot, 'get_group_honor_info', params)


async def set_group_card(bot: aiocqhttp.CQHttp, params: dict) -> dict:
    return await _call(bot, 'set_group_card', params)


async def set_group_special_title(bot: aiocqhttp.CQHttp, params: dict) -> dict:
    return await _call(bot, 'set_group_special_title', params)


async def set_group_admin(bot: aiocqhttp.CQHttp, params: dict) -> dict:
    return await _call(bot, 'set_group_admin', params)


async def set_group_whole_ban(bot: aiocqhttp.CQHttp, params: dict) -> dict:
    return await _call(bot, 'set_group_whole_ban', params)


async def send_group_forward_msg(bot: aiocqhttp.CQHttp, params: dict) -> dict:
    return await _call(bot, 'send_group_forward_msg', params)


async def get_forward_msg(bot: aiocqhttp.CQHttp, params: dict) -> dict:
    return await _call(bot, 'get_forward_msg', params)


async def get_record(bot: aiocqhttp.CQHttp, params: dict) -> dict:
    return await _call(bot, 'get_record', params)


async def get_image(bot: aiocqhttp.CQHttp, params: dict) -> dict:
    return await _call(bot, 'get_image', params)


async def can_send_image(bot: aiocqhttp.CQHttp, params: dict) -> dict:
    return await _call(bot, 'can_send_image', params)


async def can_send_record(bot: aiocqhttp.CQHttp, params: dict) -> dict:
    return await _call(bot, 'can_send_record', params)


PLATFORM_API_MAP = {
    'get_login_info': get_login_info,
    'get_status': get_status,
    'get_version_info': get_version_info,
    'get_group_honor_info': get_group_honor_info,
    'set_group_card': set_group_card,
    'set_group_special_title': set_group_special_title,
    'set_group_admin': set_group_admin,
    'set_group_whole_ban': set_group_whole_ban,
    'send_group_forward_msg': send_group_forward_msg,
    'get_forward_msg': get_forward_msg,
    'get_record': get_record,
    'get_image': get_image,
    'can_send_image': can_send_image,
    'can_send_record': can_send_record,
}
