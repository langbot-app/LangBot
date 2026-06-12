from __future__ import annotations

import datetime

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
    async def target2yiri_image(picurl: str, message_id: int | str | None = -1) -> platform_message.MessageChain:
        image_base64, image_format = await image.get_wecom_image_base64(pic_url=picurl)
        return platform_message.MessageChain(
            [
                platform_message.Source(id=message_id, time=datetime.datetime.now()),
                platform_message.Image(base64=f'data:image/{image_format};base64,{image_base64}'),
            ]
        )
