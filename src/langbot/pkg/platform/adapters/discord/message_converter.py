from __future__ import annotations

import base64
import datetime
import io
import os
import re
import uuid

import discord

from langbot.pkg.utils import httpclient
from langbot_plugin.api.entities.builtin.platform import message as platform_message


class DiscordMessageConverter:
    @staticmethod
    async def yiri2target(
        message_chain: platform_message.MessageChain,
    ) -> tuple[str, list[discord.File]]:
        text_parts: list[str] = []
        files: list[discord.File] = []

        for element in list(message_chain):
            if isinstance(element, platform_message.At):
                text_parts.append(f'<@{element.target}>')
            elif isinstance(element, platform_message.AtAll):
                text_parts.append('@everyone')
            elif isinstance(element, platform_message.Plain):
                text_parts.append(element.text)
            elif isinstance(element, platform_message.Image):
                file_bytes, filename = await DiscordMessageConverter._load_image(element)
                if file_bytes:
                    files.append(discord.File(fp=io.BytesIO(file_bytes), filename=filename))
            elif isinstance(element, platform_message.Voice):
                file_bytes, filename = await DiscordMessageConverter._load_voice(element)
                if file_bytes:
                    files.append(discord.File(fp=io.BytesIO(file_bytes), filename=filename))
            elif isinstance(element, platform_message.File):
                file_bytes = await DiscordMessageConverter._load_file(element)
                if file_bytes:
                    filename = element.name or f'{uuid.uuid4()}.bin'
                    files.append(discord.File(fp=io.BytesIO(file_bytes), filename=filename))
            elif isinstance(element, platform_message.Forward):
                for node in element.node_list:
                    node_text, node_files = await DiscordMessageConverter.yiri2target(node.message_chain)
                    text_parts.append(node_text)
                    files.extend(node_files)

        return ''.join(text_parts), files

    @staticmethod
    async def target2yiri(message: discord.Message) -> platform_message.MessageChain:
        message_time = datetime.datetime.fromtimestamp(int(message.created_at.timestamp()))
        elements: list[platform_message.MessageComponent] = [platform_message.Source(id=message.id, time=message_time)]
        elements.extend(DiscordMessageConverter._text_components(message.content))

        for attachment in message.attachments:
            if DiscordMessageConverter._is_image_attachment(attachment):
                elements.append(platform_message.Image(url=attachment.url))
            else:
                elements.append(
                    platform_message.File(
                        name=attachment.filename,
                        size=attachment.size or 0,
                        url=attachment.url,
                    )
                )

        return platform_message.MessageChain(elements)

    @staticmethod
    def _text_components(text: str) -> list[platform_message.MessageComponent]:
        if not text:
            return []

        pattern = re.compile(r'(@everyone|@here|<@!?(\d+)>)')
        components: list[platform_message.MessageComponent] = []
        last = 0
        for match in pattern.finditer(text):
            if match.start() > last:
                components.append(platform_message.Plain(text=text[last : match.start()]))
            if match.group(1) in ('@everyone', '@here'):
                components.append(platform_message.AtAll())
            else:
                components.append(platform_message.At(target=match.group(2)))
            last = match.end()
        if last < len(text):
            components.append(platform_message.Plain(text=text[last:]))
        return components

    @staticmethod
    async def _load_image(element: platform_message.Image) -> tuple[bytes | None, str]:
        filename = f'{uuid.uuid4()}.png'
        if element.base64:
            header, _, payload = element.base64.partition(',')
            data = payload or header
            if 'jpeg' in header or 'jpg' in header:
                filename = f'{uuid.uuid4()}.jpg'
            elif 'gif' in header:
                filename = f'{uuid.uuid4()}.gif'
            elif 'webp' in header:
                filename = f'{uuid.uuid4()}.webp'
            return base64.b64decode(data), filename
        if element.url:
            data, content_type = await DiscordMessageConverter._download(element.url)
            if 'jpeg' in content_type or 'jpg' in content_type:
                filename = f'{uuid.uuid4()}.jpg'
            elif 'gif' in content_type:
                filename = f'{uuid.uuid4()}.gif'
            elif 'webp' in content_type:
                filename = f'{uuid.uuid4()}.webp'
            return data, filename
        if element.path:
            path = os.path.abspath(element.path.replace('\x00', ''))
            if not os.path.exists(path):
                return None, filename
            with open(path, 'rb') as fp:
                data = fp.read()
            ext = os.path.splitext(path)[1]
            if ext:
                filename = f'{uuid.uuid4()}{ext}'
            return data, filename
        return None, filename

    @staticmethod
    async def _load_voice(element: platform_message.Voice) -> tuple[bytes | None, str]:
        filename = f'{uuid.uuid4()}.mp3'
        if element.base64:
            header, _, payload = element.base64.partition(',')
            data = payload or header
            for ext in ('wav', 'mp3', 'ogg', 'm4a', 'aac', 'flac', 'opus', 'webm'):
                if ext in header:
                    filename = f'{uuid.uuid4()}.{ext}'
                    break
            return base64.b64decode(data), filename
        if element.url:
            data, _ = await DiscordMessageConverter._download(element.url)
            return data, filename
        return None, filename

    @staticmethod
    async def _load_file(element: platform_message.File) -> bytes | None:
        if element.base64:
            return base64.b64decode(element.base64.split(',')[-1])
        if element.url:
            data, _ = await DiscordMessageConverter._download(element.url)
            return data
        return None

    @staticmethod
    async def _download(url: str) -> tuple[bytes, str]:
        session = httpclient.get_session(trust_env=True)
        async with session.get(url) as response:
            return await response.read(), response.headers.get('Content-Type', '')

    @staticmethod
    def _is_image_attachment(attachment: discord.Attachment) -> bool:
        content_type = attachment.content_type or ''
        return content_type.startswith('image/') or attachment.filename.lower().endswith(
            ('.png', '.jpg', '.jpeg', '.gif', '.webp')
        )
