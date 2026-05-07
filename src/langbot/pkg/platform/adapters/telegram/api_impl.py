"""Telegram universal API implementation (EBA version).

Implements optional API methods defined in AbstractPlatformAdapter.
"""

from __future__ import annotations

import typing

import telegram

import langbot_plugin.api.entities.builtin.platform.entities as platform_entities
import langbot_plugin.api.entities.builtin.platform.message as platform_message
import langbot_plugin.api.entities.builtin.platform.events as platform_events

from langbot.pkg.platform.adapters.telegram.message_converter import TelegramMessageConverter


class TelegramAPIMixin:
    """Telegram universal API implementation mixin.

    Used via multiple inheritance in TelegramAdapter.
    Requires self.bot: telegram.Bot and self.config: dict attributes.
    """

    bot: telegram.Bot

    async def edit_message(
        self,
        chat_type: str,
        chat_id: typing.Union[int, str],
        message_id: typing.Union[int, str],
        new_content: platform_message.MessageChain,
    ) -> None:
        """Edit a previously sent message."""
        components = await TelegramMessageConverter.yiri2target(new_content, self.bot)

        for component in components:
            if component['type'] == 'text':
                text = component['text']
                if self.config.get('markdown_card', False):
                    import telegramify_markdown

                    text = telegramify_markdown.markdownify(content=text)
                args = {
                    'chat_id': chat_id,
                    'message_id': message_id,
                    'text': text,
                }
                if self.config.get('markdown_card', False):
                    args['parse_mode'] = 'MarkdownV2'
                await self.bot.edit_message_text(**args)
                return

    async def delete_message(
        self,
        chat_type: str,
        chat_id: typing.Union[int, str],
        message_id: typing.Union[int, str],
    ) -> None:
        """Delete / recall a message."""
        await self.bot.delete_message(chat_id=chat_id, message_id=message_id)

    async def forward_message(
        self,
        from_chat_type: str,
        from_chat_id: typing.Union[int, str],
        message_id: typing.Union[int, str],
        to_chat_type: str,
        to_chat_id: typing.Union[int, str],
    ) -> platform_events.MessageResult:
        """Forward a message to another chat."""
        result = await self.bot.forward_message(
            chat_id=to_chat_id,
            from_chat_id=from_chat_id,
            message_id=message_id,
        )
        return platform_events.MessageResult(
            message_id=result.message_id,
            raw={'message_id': result.message_id},
        )

    async def get_group_info(
        self,
        group_id: typing.Union[int, str],
    ) -> platform_entities.UserGroup:
        """Get group information."""
        chat = await self.bot.get_chat(chat_id=group_id)
        return platform_entities.UserGroup(
            id=chat.id,
            name=chat.title or '',
            description=chat.description or None,
            member_count=await self._get_member_count(group_id),
        )

    async def _get_member_count(self, group_id: typing.Union[int, str]) -> typing.Optional[int]:
        """Get group member count."""
        try:
            return await self.bot.get_chat_member_count(chat_id=group_id)
        except Exception:
            return None

    async def get_group_member_list(
        self,
        group_id: typing.Union[int, str],
    ) -> list[platform_entities.UserGroupMember]:
        """Get group member list.

        Note: Telegram Bot API only supports fetching the admin list
        (get_chat_administrators), not the full member list.
        This method returns the admin list.
        """
        admins = await self.bot.get_chat_administrators(chat_id=group_id)
        members = []
        for admin in admins:
            role = platform_entities.MemberRole.MEMBER
            if admin.status == 'creator':
                role = platform_entities.MemberRole.OWNER
            elif admin.status == 'administrator':
                role = platform_entities.MemberRole.ADMIN

            members.append(
                platform_entities.UserGroupMember(
                    user=platform_entities.User(
                        id=admin.user.id,
                        nickname=admin.user.first_name or '',
                        username=admin.user.username,
                        is_bot=admin.user.is_bot,
                    ),
                    group_id=group_id,
                    role=role,
                    display_name=admin.custom_title if hasattr(admin, 'custom_title') else None,
                )
            )
        return members

    async def get_group_member_info(
        self,
        group_id: typing.Union[int, str],
        user_id: typing.Union[int, str],
    ) -> platform_entities.UserGroupMember:
        """Get information about a specific group member."""
        member = await self.bot.get_chat_member(chat_id=group_id, user_id=user_id)

        role = platform_entities.MemberRole.MEMBER
        if member.status == 'creator':
            role = platform_entities.MemberRole.OWNER
        elif member.status == 'administrator':
            role = platform_entities.MemberRole.ADMIN

        return platform_entities.UserGroupMember(
            user=platform_entities.User(
                id=member.user.id,
                nickname=member.user.first_name or '',
                username=member.user.username,
                is_bot=member.user.is_bot,
            ),
            group_id=group_id,
            role=role,
            display_name=member.custom_title if hasattr(member, 'custom_title') else None,
        )

    async def get_user_info(
        self,
        user_id: typing.Union[int, str],
    ) -> platform_entities.User:
        """Get user information."""
        chat = await self.bot.get_chat(chat_id=user_id)
        return platform_entities.User(
            id=chat.id,
            nickname=chat.first_name or '',
            username=chat.username,
        )

    async def upload_file(
        self,
        file_data: bytes,
        filename: str,
    ) -> str:
        """Upload a file.

        Telegram does not support standalone file uploads; files are sent as
        part of messages. This method raises NotSupportedError.
        """
        from langbot_plugin.api.entities.builtin.platform.errors import NotSupportedError

        raise NotSupportedError('upload_file')

    async def get_file_url(
        self,
        file_id: str,
    ) -> str:
        """Get file download URL."""
        file = await self.bot.get_file(file_id)
        return file.file_path

    async def mute_member(
        self,
        group_id: typing.Union[int, str],
        user_id: typing.Union[int, str],
        duration: int = 0,
    ) -> None:
        """Mute a group member."""
        import datetime

        permissions = telegram.ChatPermissions(can_send_messages=False)
        kwargs = {
            'chat_id': group_id,
            'user_id': user_id,
            'permissions': permissions,
        }
        if duration > 0:
            kwargs['until_date'] = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(seconds=duration)
        await self.bot.restrict_chat_member(**kwargs)

    async def unmute_member(
        self,
        group_id: typing.Union[int, str],
        user_id: typing.Union[int, str],
    ) -> None:
        """Unmute a group member."""
        permissions = telegram.ChatPermissions(
            can_send_messages=True,
            can_send_other_messages=True,
            can_add_web_page_previews=True,
            can_send_audios=True,
            can_send_documents=True,
            can_send_photos=True,
            can_send_videos=True,
            can_send_video_notes=True,
            can_send_voice_notes=True,
        )
        await self.bot.restrict_chat_member(
            chat_id=group_id,
            user_id=user_id,
            permissions=permissions,
        )

    async def kick_member(
        self,
        group_id: typing.Union[int, str],
        user_id: typing.Union[int, str],
    ) -> None:
        """Kick a member from the group."""
        await self.bot.ban_chat_member(chat_id=group_id, user_id=user_id)

    async def leave_group(
        self,
        group_id: typing.Union[int, str],
    ) -> None:
        """Make the bot leave a group."""
        await self.bot.leave_chat(chat_id=group_id)
