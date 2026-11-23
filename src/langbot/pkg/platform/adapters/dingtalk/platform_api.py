from __future__ import annotations

import typing

from langbot.libs.dingtalk_api.api import DingTalkClient


async def check_access_token(bot: DingTalkClient, params: dict) -> dict:
    return {'valid': await bot.check_access_token()}


async def refresh_access_token(bot: DingTalkClient, params: dict) -> dict:
    await bot.get_access_token()
    return {'ok': bool(bot.access_token)}


async def get_file_url(bot: DingTalkClient, params: dict) -> dict:
    download_code = params.get('download_code') or params.get('downloadCode') or params.get('file_id')
    if not download_code:
        raise ValueError('download_code is required')
    return {'url': await bot.get_file_url(str(download_code))}


async def get_audio_base64(bot: DingTalkClient, params: dict) -> dict:
    download_code = params.get('download_code') or params.get('downloadCode') or params.get('file_id')
    if not download_code:
        raise ValueError('download_code is required')
    return {'base64': await bot.get_audio_url(str(download_code))}


async def download_image_base64(bot: DingTalkClient, params: dict) -> dict:
    download_code = params.get('download_code') or params.get('downloadCode') or params.get('file_id')
    if not download_code:
        raise ValueError('download_code is required')
    return {'base64': await bot.download_image(str(download_code))}


PLATFORM_API_MAP: dict[str, typing.Callable[[DingTalkClient, dict], typing.Awaitable[dict]]] = {
    'check_access_token': check_access_token,
    'refresh_access_token': refresh_access_token,
    'get_file_url': get_file_url,
    'get_audio_base64': get_audio_base64,
    'download_image_base64': download_image_base64,
}
