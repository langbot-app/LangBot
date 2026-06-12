"""Telegram platform-specific API dispatch table for call_platform_api."""

from __future__ import annotations

import typing

import telegram


async def pin_message(bot: telegram.Bot, params: dict) -> dict:
    """Pin a message in a chat."""
    await bot.pin_chat_message(
        chat_id=params['chat_id'],
        message_id=params['message_id'],
        disable_notification=params.get('disable_notification', False),
    )
    return {"ok": True}


async def unpin_message(bot: telegram.Bot, params: dict) -> dict:
    """Unpin a message in a chat."""
    await bot.unpin_chat_message(
        chat_id=params['chat_id'],
        message_id=params.get('message_id'),
    )
    return {"ok": True}


async def unpin_all_messages(bot: telegram.Bot, params: dict) -> dict:
    """Unpin all messages in a chat."""
    await bot.unpin_all_chat_messages(chat_id=params['chat_id'])
    return {"ok": True}


async def get_chat_administrators(bot: telegram.Bot, params: dict) -> dict:
    """Get chat administrator list."""
    admins = await bot.get_chat_administrators(chat_id=params['chat_id'])
    return {
        "administrators": [
            {
                "user_id": a.user.id,
                "username": a.user.username,
                "first_name": a.user.first_name,
                "status": a.status,
                "custom_title": getattr(a, 'custom_title', None),
            }
            for a in admins
        ]
    }


async def set_chat_title(bot: telegram.Bot, params: dict) -> dict:
    """Set chat title."""
    await bot.set_chat_title(
        chat_id=params['chat_id'],
        title=params['title'],
    )
    return {"ok": True}


async def set_chat_description(bot: telegram.Bot, params: dict) -> dict:
    """Set chat description."""
    await bot.set_chat_description(
        chat_id=params['chat_id'],
        description=params.get('description', ''),
    )
    return {"ok": True}


async def get_chat_member_count(bot: telegram.Bot, params: dict) -> dict:
    """Get chat member count."""
    count = await bot.get_chat_member_count(chat_id=params['chat_id'])
    return {"count": count}


async def send_chat_action(bot: telegram.Bot, params: dict) -> dict:
    """Send a chat action (e.g. typing)."""
    await bot.send_chat_action(
        chat_id=params['chat_id'],
        action=params.get('action', 'typing'),
    )
    return {"ok": True}


async def create_chat_invite_link(bot: telegram.Bot, params: dict) -> dict:
    """Create a chat invite link."""
    link = await bot.create_chat_invite_link(
        chat_id=params['chat_id'],
        name=params.get('name'),
        expire_date=params.get('expire_date'),
        member_limit=params.get('member_limit'),
    )
    return {
        "invite_link": link.invite_link,
        "name": link.name,
        "is_primary": link.is_primary,
        "is_revoked": link.is_revoked,
    }


async def answer_callback_query(bot: telegram.Bot, params: dict) -> dict:
    """Answer a callback query."""
    await bot.answer_callback_query(
        callback_query_id=params['callback_query_id'],
        text=params.get('text'),
        show_alert=params.get('show_alert', False),
        url=params.get('url'),
    )
    return {"ok": True}


# ---- Action dispatch table ----

PLATFORM_API_MAP: dict[str, typing.Callable[[telegram.Bot, dict], typing.Awaitable[dict]]] = {
    "pin_message": pin_message,
    "unpin_message": unpin_message,
    "unpin_all_messages": unpin_all_messages,
    "get_chat_administrators": get_chat_administrators,
    "set_chat_title": set_chat_title,
    "set_chat_description": set_chat_description,
    "get_chat_member_count": get_chat_member_count,
    "send_chat_action": send_chat_action,
    "create_chat_invite_link": create_chat_invite_link,
    "answer_callback_query": answer_callback_query,
}
