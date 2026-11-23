from __future__ import annotations

import typing
import uuid

from langbot.pkg.platform.adapters.officialaccount import menu as custom_menu


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


async def menu_get(adapter, params: dict) -> dict:
    """Return the menu saved in LangBot and the menu WeChat currently serves through the API."""
    published = await adapter.menu_api().get_menu()
    return {
        'saved': adapter.config.get(custom_menu.CONFIG_KEY) or {'buttons': []},
        'published': published.get('menu') if published else None,
    }


async def menu_import_console(adapter, params: dict) -> dict:
    """Read the account's current menu, including one edited in the WeChat web console."""
    info = await adapter.menu_api().get_current_selfmenu_info()
    menu, warnings = custom_menu.from_selfmenu(info, lambda: uuid.uuid4().hex[:8])
    return {'menu': menu, 'is_menu_open': bool(info.get('is_menu_open')), 'warnings': warnings}


async def menu_publish(adapter, params: dict) -> dict:
    """Publish the saved LangBot menu, or a raw WeChat ``menu`` body when one is given."""
    raw = params.get('menu')
    if raw is not None:
        if not isinstance(raw, dict) or not isinstance(raw.get('button'), list):
            raise ValueError('menu must be a WeChat menu object with a "button" list')
        body = raw
    else:
        body = custom_menu.to_wechat(adapter.config.get(custom_menu.CONFIG_KEY))
    await adapter.menu_api().create_menu(body)
    return {'published': body}


async def menu_delete(adapter, params: dict) -> dict:
    await adapter.menu_api().delete_menu()
    return {'deleted': True}


MENU_API_MAP: dict[str, typing.Callable[[typing.Any, dict], typing.Awaitable[dict]]] = {
    'menu.get': menu_get,
    'menu.import_console': menu_import_console,
    'menu.publish': menu_publish,
    'menu.delete': menu_delete,
}
