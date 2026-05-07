"""Telegram message chain converter.

Migrated from the original sources/telegram.py TelegramMessageConverter. Logic unchanged.
"""

from __future__ import annotations

import base64

import telegram

from langbot.pkg.utils import httpclient
import langbot_plugin.api.definition.abstract.platform.adapter as abstract_platform_adapter
import langbot_plugin.api.entities.builtin.platform.message as platform_message


class TelegramMessageConverter(abstract_platform_adapter.AbstractMessageConverter):
    @staticmethod
    async def yiri2target(message_chain: platform_message.MessageChain, bot: telegram.Bot) -> list[dict]:
        """Convert a LangBot MessageChain to a list of Telegram-sendable components."""
        components = []

        for component in message_chain:
            if isinstance(component, platform_message.Plain):
                components.append({'type': 'text', 'text': component.text})
            elif isinstance(component, platform_message.Image):
                photo_bytes = None

                if component.base64:
                    photo_bytes = base64.b64decode(component.base64)
                elif component.url:
                    session = httpclient.get_session()
                    async with session.get(component.url) as response:
                        photo_bytes = await response.read()
                elif component.path:
                    with open(component.path, 'rb') as f:
                        photo_bytes = f.read()

                components.append({'type': 'photo', 'photo': photo_bytes})
            elif isinstance(component, platform_message.File):
                file_bytes = None

                if component.base64:
                    b64_data = component.base64
                    if ';base64,' in b64_data:
                        b64_data = b64_data.split(';base64,', 1)[1]
                    file_bytes = base64.b64decode(b64_data)
                elif component.url:
                    session = httpclient.get_session()
                    async with session.get(component.url) as response:
                        file_bytes = await response.read()
                elif component.path:
                    with open(component.path, 'rb') as f:
                        file_bytes = f.read()

                file_name = getattr(component, 'name', None) or 'file'
                components.append({'type': 'document', 'document': file_bytes, 'filename': file_name})
            elif isinstance(component, platform_message.Forward):
                for node in component.node_list:
                    components.extend(await TelegramMessageConverter.yiri2target(node.message_chain, bot))

        return components

    @staticmethod
    async def target2yiri(message: telegram.Message, bot: telegram.Bot, bot_account_id: str):
        """Convert a Telegram Message to a LangBot MessageChain."""
        message_components = []

        def parse_message_text(text: str) -> list[platform_message.MessageComponent]:
            msg_components = []

            if f'@{bot_account_id}' in text:
                msg_components.append(platform_message.At(target=bot_account_id))
                text = text.replace(f'@{bot_account_id}', '')
            msg_components.append(platform_message.Plain(text=text))

            return msg_components

        if message.text:
            message_text = message.text
            message_components.extend(parse_message_text(message_text))

        if message.photo:
            if message.caption:
                message_components.extend(parse_message_text(message.caption))

            file = await message.photo[-1].get_file()

            file_bytes = None
            file_format = ''

            async with httpclient.get_session(trust_env=True).get(file.file_path) as response:
                file_bytes = await response.read()
                file_format = 'image/jpeg'

            message_components.append(
                platform_message.Image(
                    base64=f'data:{file_format};base64,{base64.b64encode(file_bytes).decode("utf-8")}'
                )
            )

        if message.voice:
            if message.caption:
                message_components.extend(parse_message_text(message.caption))

            file = await message.voice.get_file()

            file_bytes = None
            file_format = message.voice.mime_type or 'audio/ogg'

            async with httpclient.get_session(trust_env=True).get(file.file_path) as response:
                file_bytes = await response.read()

            message_components.append(
                platform_message.Voice(
                    base64=f'data:{file_format};base64,{base64.b64encode(file_bytes).decode("utf-8")}',
                    length=message.voice.duration,
                )
            )

        if message.document:
            if message.caption:
                message_components.extend(parse_message_text(message.caption))

            file = await message.document.get_file()
            file_name = message.document.file_name or 'document'
            file_size = message.document.file_size or 0
            file_format = message.document.mime_type or 'application/octet-stream'

            file_bytes = None
            async with httpclient.get_session(trust_env=True).get(file.file_path) as response:
                file_bytes = await response.read()

            message_components.append(
                platform_message.File(
                    name=file_name,
                    size=file_size,
                    base64=f'data:{file_format};base64,{base64.b64encode(file_bytes).decode("utf-8")}',
                )
            )

        return platform_message.MessageChain(message_components)
