from __future__ import annotations

import base64
import datetime
import mimetypes

from langbot.libs.wecom_api.api import WecomClient
from langbot.pkg.utils import image
import langbot_plugin.api.definition.abstract.platform.adapter as abstract_platform_adapter
from langbot_plugin.api.entities.builtin.platform import message as platform_message


def split_string_by_bytes(text: str, limit: int = 2048, encoding: str = 'utf-8') -> list[str]:
    """Split text without cutting a multi-byte character in half."""
    bytes_data = text.encode(encoding)
    total_len = len(bytes_data)
    parts: list[str] = []
    start = 0

    while start < total_len:
        end = min(start + limit, total_len)
        chunk = bytes_data[start:end]
        part = chunk.decode(encoding, errors='ignore')
        part_len = len(part.encode(encoding))
        if part_len == 0 and end < total_len:
            start += 1
            continue
        parts.append(part)
        start += part_len

    return parts


class WecomMessageConverter(abstract_platform_adapter.AbstractMessageConverter):
    @staticmethod
    async def yiri2target(message_chain: platform_message.MessageChain, bot: WecomClient) -> list[dict]:
        content_list: list[dict] = []

        for msg in message_chain:
            if isinstance(msg, platform_message.Source):
                continue
            if isinstance(msg, platform_message.Plain):
                content_list.extend({'type': 'text', 'content': chunk} for chunk in split_string_by_bytes(msg.text))
            elif isinstance(msg, platform_message.Image):
                content_list.append({'type': 'image', 'media_id': await bot.get_media_id(msg)})
            elif isinstance(msg, platform_message.Voice):
                content_list.append({'type': 'voice', 'media_id': await bot.get_media_id(msg)})
            elif isinstance(msg, platform_message.File):
                content_list.append({'type': 'file', 'media_id': await bot.get_media_id(msg)})
            elif isinstance(msg, platform_message.Forward):
                for node in msg.node_list:
                    content_list.extend(await WecomMessageConverter.yiri2target(node.message_chain, bot))
            elif isinstance(msg, platform_message.Quote):
                if msg.id is not None:
                    content_list.append({'type': 'text', 'content': f'[Quote {msg.id}] '})
                if msg.origin:
                    content_list.extend(await WecomMessageConverter.yiri2target(msg.origin, bot))
            elif isinstance(msg, platform_message.At):
                content_list.append({'type': 'text', 'content': f'@{msg.display or msg.target}'})
            elif isinstance(msg, platform_message.AtAll):
                content_list.append({'type': 'text', 'content': '@all'})
            else:
                content_list.append({'type': 'text', 'content': str(msg)})

        return content_list

    @staticmethod
    async def target2yiri_text(message: str | None, message_id: int | str | None = -1) -> platform_message.MessageChain:
        return platform_message.MessageChain(
            [
                platform_message.Source(id=message_id, time=datetime.datetime.now()),
                platform_message.Plain(text=message or ''),
            ]
        )

    @staticmethod
    async def target2yiri_file(event, bot: WecomClient | None = None) -> platform_message.MessageChain:
        media_id = event.media_id
        if not media_id:
            # Nothing to download: say so instead of emitting an empty chain.
            return platform_message.MessageChain(
                [
                    platform_message.Source(id=event.message_id, time=datetime.datetime.now()),
                    platform_message.Unknown(text=f'[File: {event.get("FileName") or ""}]'),
                ]
            )
        name = event.get('FileName') or ''
        try:
            size = int(event.get('FileSize') or 0)
        except (TypeError, ValueError):
            size = 0
        # Inline the bytes the way images inline their PicUrl. Nothing
        # downstream resolves a bare MediaId: `get_file_url` is not exposed by
        # this adapter, and the Runner upload path only reads base64/url/path,
        # so an id-only File reaches the model as "no uploadable content".
        file_base64 = await WecomMessageConverter._download_media_base64(bot, media_id, name)
        return platform_message.MessageChain(
            [
                platform_message.Source(id=event.message_id, time=datetime.datetime.now()),
                platform_message.File(
                    id=media_id,
                    name=name,
                    size=size,
                    base64=file_base64 or '',
                ),
            ]
        )

    @staticmethod
    async def _download_media_base64(bot: WecomClient | None, media_id: str, name: str) -> str | None:
        """Fetch a `MediaId` and wrap it as a data URI, or None on failure."""
        if bot is None:
            return None
        try:
            media_bytes = await bot.download_media_id_to_bytes(media_id)
        except Exception:
            return None
        if not media_bytes:
            return None
        mime = mimetypes.guess_type(name)[0] or 'application/octet-stream'
        return f'data:{mime};base64,' + base64.b64encode(media_bytes).decode('ascii')

    @staticmethod
    async def target2yiri_image(picurl: str, message_id: int | str | None = -1) -> platform_message.MessageChain:
        image_base64, image_format = await image.get_wecom_image_base64(pic_url=picurl)
        return platform_message.MessageChain(
            [
                platform_message.Source(id=message_id, time=datetime.datetime.now()),
                platform_message.Image(url=picurl, base64=f'data:image/{image_format};base64,{image_base64}'),
            ]
        )
