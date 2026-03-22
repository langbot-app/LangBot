"""Telegram event converter (EBA version).

Converts all Telegram Update types to unified EBA events, not just messages.
"""

from __future__ import annotations

import typing

import telegram
from telegram import Update

import langbot_plugin.api.entities.builtin.platform.events as platform_events
import langbot_plugin.api.entities.builtin.platform.entities as platform_entities
import langbot_plugin.api.entities.builtin.platform.message as platform_message
import langbot_plugin.api.definition.abstract.platform.adapter as abstract_platform_adapter

from langbot.pkg.platform.adapters.telegram.message_converter import TelegramMessageConverter


def _make_user(tg_user: telegram.User) -> platform_entities.User:
    """Convert a Telegram User to a unified User entity."""
    return platform_entities.User(
        id=tg_user.id,
        nickname=tg_user.first_name or "",
        username=tg_user.username,
        is_bot=tg_user.is_bot,
    )


def _make_user_group(tg_chat: telegram.Chat) -> platform_entities.UserGroup:
    """Convert a Telegram Chat to a unified UserGroup entity."""
    return platform_entities.UserGroup(
        id=tg_chat.id,
        name=tg_chat.title or tg_chat.first_name or "",
        description=tg_chat.description if hasattr(tg_chat, 'description') else None,
    )


def _chat_type(tg_chat: telegram.Chat) -> platform_entities.ChatType:
    """Map Telegram Chat type to unified ChatType."""
    if tg_chat.type == 'private':
        return platform_entities.ChatType.PRIVATE
    return platform_entities.ChatType.GROUP


class TelegramEventConverter(abstract_platform_adapter.AbstractEventConverter):
    """Telegram event converter (EBA version)."""

    @staticmethod
    async def yiri2target(event: platform_events.Event, bot: telegram.Bot):
        """Convert a unified event to a raw Telegram event (generally not needed)."""
        if hasattr(event, 'source_platform_object'):
            return event.source_platform_object
        return None

    @staticmethod
    async def target2yiri(
        update: Update,
        bot: telegram.Bot,
        bot_account_id: str,
    ) -> typing.Optional[platform_events.EBAEvent]:
        """Convert a Telegram Update to a unified EBA event.

        Supports: message, edited_message, chat_member, my_chat_member,
        callback_query, message_reaction, etc.
        Unmappable events are wrapped as PlatformSpecificEvent.
        """
        import time

        # ---- Message event ----
        if update.message and update.message.text is not None or (
            update.message and (update.message.photo or update.message.voice or update.message.document)
        ):
            return await TelegramEventConverter._convert_message(update, bot, bot_account_id)

        # ---- Edited message event ----
        if update.edited_message:
            return await TelegramEventConverter._convert_edited_message(update, bot, bot_account_id)

        # ---- Member change event (chat_member) ----
        if update.chat_member:
            return TelegramEventConverter._convert_chat_member(update)

        # ---- Bot's own member status change (my_chat_member) ----
        if update.my_chat_member:
            return TelegramEventConverter._convert_my_chat_member(update)

        # ---- Callback query (button clicks, etc.) ----
        if update.callback_query:
            return platform_events.PlatformSpecificEvent(
                type="platform.specific",
                timestamp=time.time(),
                adapter_name="telegram",
                action="callback_query",
                data={
                    "callback_query_id": update.callback_query.id,
                    "data": update.callback_query.data,
                    "from_user_id": update.callback_query.from_user.id if update.callback_query.from_user else None,
                    "message_id": update.callback_query.message.message_id if update.callback_query.message else None,
                },
                source_platform_object=update,
            )

        # ---- Message reaction ----
        if update.message_reaction:
            return TelegramEventConverter._convert_reaction(update)

        # ---- Fallback: wrap as PlatformSpecificEvent ----
        return platform_events.PlatformSpecificEvent(
            type="platform.specific",
            timestamp=time.time(),
            adapter_name="telegram",
            action="unknown_update",
            data={"update_id": update.update_id},
            source_platform_object=update,
        )

    @staticmethod
    async def _convert_message(
        update: Update, bot: telegram.Bot, bot_account_id: str,
    ) -> platform_events.MessageReceivedEvent:
        """Convert a Telegram message to MessageReceivedEvent."""
        message = update.message
        lb_message = await TelegramMessageConverter.target2yiri(message, bot, bot_account_id)

        sender = _make_user(message.from_user) if message.from_user else platform_entities.User(id="")
        chat = message.chat
        ct = _chat_type(chat)

        group = None
        if ct == platform_entities.ChatType.GROUP:
            group = _make_user_group(chat)

        return platform_events.MessageReceivedEvent(
            type="message.received",
            timestamp=message.date.timestamp() if message.date else 0.0,
            adapter_name="telegram",
            message_id=message.message_id,
            message_chain=lb_message,
            sender=sender,
            chat_type=ct,
            chat_id=chat.id,
            group=group,
            source_platform_object=update,
        )

    @staticmethod
    async def _convert_edited_message(
        update: Update, bot: telegram.Bot, bot_account_id: str,
    ) -> platform_events.MessageEditedEvent:
        """Convert a Telegram edited message to MessageEditedEvent."""
        message = update.edited_message
        lb_message = await TelegramMessageConverter.target2yiri(message, bot, bot_account_id)

        editor = _make_user(message.from_user) if message.from_user else platform_entities.User(id="")
        chat = message.chat
        ct = _chat_type(chat)

        group = None
        if ct == platform_entities.ChatType.GROUP:
            group = _make_user_group(chat)

        return platform_events.MessageEditedEvent(
            type="message.edited",
            timestamp=message.edit_date.timestamp() if message.edit_date else 0.0,
            adapter_name="telegram",
            message_id=message.message_id,
            new_content=lb_message,
            editor=editor,
            chat_type=ct,
            chat_id=chat.id,
            group=group,
            source_platform_object=update,
        )

    @staticmethod
    def _convert_chat_member(update: Update) -> typing.Optional[platform_events.EBAEvent]:
        """Convert a chat_member update to MemberJoinedEvent / MemberLeftEvent / etc."""
        import time

        cm = update.chat_member
        chat = cm.chat
        group = _make_user_group(chat)
        member = _make_user(cm.new_chat_member.user) if cm.new_chat_member else platform_entities.User(id="")
        inviter = _make_user(cm.from_user) if cm.from_user else None

        old_status = cm.old_chat_member.status if cm.old_chat_member else None
        new_status = cm.new_chat_member.status if cm.new_chat_member else None

        # Member joined
        if old_status in (None, 'left', 'kicked') and new_status in ('member', 'administrator', 'creator', 'restricted'):
            return platform_events.MemberJoinedEvent(
                type="group.member_joined",
                timestamp=cm.date.timestamp() if cm.date else time.time(),
                adapter_name="telegram",
                group=group,
                member=member,
                inviter=inviter,
                join_type="invite" if inviter and inviter.id != member.id else "direct",
                source_platform_object=update,
            )

        # Member left / kicked
        if old_status in ('member', 'administrator', 'creator', 'restricted') and new_status in ('left', 'kicked'):
            is_kicked = new_status == 'kicked'
            return platform_events.MemberLeftEvent(
                type="group.member_left",
                timestamp=cm.date.timestamp() if cm.date else time.time(),
                adapter_name="telegram",
                group=group,
                member=member,
                is_kicked=is_kicked,
                operator=inviter if is_kicked else None,
                source_platform_object=update,
            )

        # Member muted (restricted with can_send_messages == False)
        if new_status == 'restricted' and cm.new_chat_member:
            restricted = cm.new_chat_member
            if hasattr(restricted, 'can_send_messages') and not restricted.can_send_messages:
                duration = None
                if hasattr(restricted, 'until_date') and restricted.until_date:
                    duration = int(restricted.until_date.timestamp() - time.time())
                return platform_events.MemberBannedEvent(
                    type="group.member_banned",
                    timestamp=cm.date.timestamp() if cm.date else time.time(),
                    adapter_name="telegram",
                    group=group,
                    member=member,
                    operator=inviter,
                    duration=duration,
                    source_platform_object=update,
                )

        # Other chat_member changes -> PlatformSpecificEvent
        return platform_events.PlatformSpecificEvent(
            type="platform.specific",
            timestamp=cm.date.timestamp() if cm.date else time.time(),
            adapter_name="telegram",
            action="chat_member_updated",
            data={
                "old_status": old_status,
                "new_status": new_status,
                "chat_id": chat.id,
                "user_id": member.id,
            },
            source_platform_object=update,
        )

    @staticmethod
    def _convert_my_chat_member(update: Update) -> typing.Optional[platform_events.EBAEvent]:
        """Convert a my_chat_member update to bot status events."""
        import time

        mcm = update.my_chat_member
        chat = mcm.chat
        group = _make_user_group(chat)
        inviter = _make_user(mcm.from_user) if mcm.from_user else None

        old_status = mcm.old_chat_member.status if mcm.old_chat_member else None
        new_status = mcm.new_chat_member.status if mcm.new_chat_member else None

        # Bot invited to group
        if old_status in (None, 'left', 'kicked') and new_status in ('member', 'administrator'):
            return platform_events.BotInvitedToGroupEvent(
                type="bot.invited_to_group",
                timestamp=mcm.date.timestamp() if mcm.date else time.time(),
                adapter_name="telegram",
                group=group,
                inviter=inviter,
                source_platform_object=update,
            )

        # Bot removed from group
        if old_status in ('member', 'administrator', 'creator') and new_status in ('left', 'kicked'):
            return platform_events.BotRemovedFromGroupEvent(
                type="bot.removed_from_group",
                timestamp=mcm.date.timestamp() if mcm.date else time.time(),
                adapter_name="telegram",
                group=group,
                operator=inviter,
                source_platform_object=update,
            )

        # Bot muted
        if new_status == 'restricted' and mcm.new_chat_member:
            restricted = mcm.new_chat_member
            if hasattr(restricted, 'can_send_messages') and not restricted.can_send_messages:
                duration = None
                if hasattr(restricted, 'until_date') and restricted.until_date:
                    duration = int(restricted.until_date.timestamp() - time.time())
                return platform_events.BotMutedEvent(
                    type="bot.muted",
                    timestamp=mcm.date.timestamp() if mcm.date else time.time(),
                    adapter_name="telegram",
                    group=group,
                    operator=inviter,
                    duration=duration,
                    source_platform_object=update,
                )

        return platform_events.PlatformSpecificEvent(
            type="platform.specific",
            timestamp=mcm.date.timestamp() if mcm.date else time.time(),
            adapter_name="telegram",
            action="my_chat_member_updated",
            data={
                "old_status": old_status,
                "new_status": new_status,
                "chat_id": chat.id,
            },
            source_platform_object=update,
        )

    @staticmethod
    def _convert_reaction(update: Update) -> platform_events.MessageReactionEvent:
        """Convert a Telegram message_reaction to MessageReactionEvent."""
        import time

        reaction = update.message_reaction
        chat = reaction.chat

        # Extract newly added emojis
        new_emojis = []
        if reaction.new_reaction:
            for r in reaction.new_reaction:
                if hasattr(r, 'emoji'):
                    new_emojis.append(r.emoji)
                elif hasattr(r, 'custom_emoji_id'):
                    new_emojis.append(str(r.custom_emoji_id))

        user = platform_entities.User(id="")
        if reaction.user:
            user = _make_user(reaction.user)

        ct = _chat_type(chat)
        group = _make_user_group(chat) if ct == platform_entities.ChatType.GROUP else None

        return platform_events.MessageReactionEvent(
            type="message.reaction",
            timestamp=reaction.date.timestamp() if reaction.date else time.time(),
            adapter_name="telegram",
            message_id=reaction.message_id,
            user=user,
            reaction=new_emojis[0] if new_emojis else "",
            is_add=len(new_emojis) > 0,
            chat_type=ct,
            chat_id=chat.id,
            group=group,
            source_platform_object=update,
        )


class LegacyEventConverter(abstract_platform_adapter.AbstractEventConverter):
    """Legacy event converter (compatibility layer).

    Converts Telegram Updates to the old FriendMessage / GroupMessage format.
    Used during the transition period to maintain backward compatibility.
    """

    @staticmethod
    async def yiri2target(event: platform_events.MessageEvent, bot: telegram.Bot):
        return event.source_platform_object

    @staticmethod
    async def target2yiri(event: Update, bot: telegram.Bot, bot_account_id: str):
        """Convert to legacy format (FriendMessage / GroupMessage)."""
        import langbot_plugin.api.entities.builtin.platform.events as legacy_events
        import langbot_plugin.api.entities.builtin.platform.entities as legacy_entities

        if not event.message:
            return None

        lb_message = await TelegramMessageConverter.target2yiri(event.message, bot, bot_account_id)

        if event.effective_chat.type == 'private':
            return legacy_events.FriendMessage(
                sender=legacy_entities.Friend(
                    id=event.effective_chat.id,
                    nickname=event.effective_chat.first_name,
                    remark=str(event.effective_chat.id),
                ),
                message_chain=lb_message,
                time=event.message.date.timestamp(),
                source_platform_object=event,
            )
        else:
            return legacy_events.GroupMessage(
                sender=legacy_entities.GroupMember(
                    id=event.effective_chat.id,
                    member_name=event.effective_chat.title,
                    permission=legacy_entities.Permission.Member,
                    group=legacy_entities.Group(
                        id=event.effective_chat.id,
                        name=event.effective_chat.title,
                        permission=legacy_entities.Permission.Member,
                    ),
                    special_title='',
                ),
                message_chain=lb_message,
                time=event.message.date.timestamp(),
                source_platform_object=event,
            )
