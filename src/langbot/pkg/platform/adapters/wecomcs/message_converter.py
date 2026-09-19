from __future__ import annotations

import datetime

from langbot.libs.wecom_customer_service_api.api import WecomCSClient
import langbot_plugin.api.definition.abstract.platform.adapter as abstract_platform_adapter
from langbot_plugin.api.entities.builtin.platform import message as platform_message
from langbot_plugin.api.entities.builtin.platform.errors import NotSupportedError


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


class WecomCSMessageConverter(abstract_platform_adapter.AbstractMessageConverter):
    @staticmethod
    async def yiri2target(message_chain: platform_message.MessageChain, bot: WecomCSClient) -> list[dict]:
        content_list: list[dict] = []

        for msg in message_chain:
            if isinstance(msg, platform_message.Source):
                continue
            if isinstance(msg, platform_message.Plain):
                content_list.extend({'type': 'text', 'content': chunk} for chunk in split_string_by_bytes(msg.text))
            elif isinstance(msg, platform_message.Image):
                content_list.append({'type': 'image', 'media_id': await bot.get_media_id(msg)})
            elif isinstance(msg, platform_message.Forward):
                for node in msg.node_list:
                    content_list.extend(await WecomCSMessageConverter.yiri2target(node.message_chain, bot))
            elif isinstance(msg, platform_message.Quote):
                if msg.id is not None:
                    content_list.append({'type': 'text', 'content': f'[Quote {msg.id}] '})
                if msg.origin:
                    content_list.extend(await WecomCSMessageConverter.yiri2target(msg.origin, bot))
            elif isinstance(msg, platform_message.At):
                content_list.append({'type': 'text', 'content': f'@{msg.display or msg.target}'})
            elif isinstance(msg, platform_message.AtAll):
                content_list.append({'type': 'text', 'content': '@all'})
            elif isinstance(msg, (platform_message.Voice, platform_message.File, platform_message.Face)):
                raise NotSupportedError(f'wecomcs_send_component:{msg.type}')
            else:
                content_list.append({'type': 'text', 'content': str(msg)})

        return content_list

    @staticmethod
    async def target2yiri(event: dict) -> platform_message.MessageChain:
        message_id = event.get('msgid') or ''
        timestamp = event.get('send_time') or event.get('sendtime') or datetime.datetime.now().timestamp()
        components: list[platform_message.MessageComponent] = [
            platform_message.Source(id=message_id, time=datetime.datetime.fromtimestamp(float(timestamp))),
        ]

        msgtype = event.get('msgtype')
        if msgtype == 'text':
            components.append(platform_message.Plain(text=(event.get('text') or {}).get('content', '')))
        elif msgtype == 'image':
            components.append(platform_message.Image(base64=event.get('picurl') or ''))
        elif msgtype == 'file':
            file_data = event.get('file') or {}
            components.append(
                platform_message.File(
                    id=file_data.get('media_id'),
                    name=file_data.get('filename') or file_data.get('file_name') or '',
                    size=file_data.get('file_size') or 0,
                )
            )
        elif msgtype == 'voice':
            voice_data = event.get('voice') or {}
            components.append(platform_message.Voice(voice_id=voice_data.get('media_id') or ''))
        else:
            components.append(platform_message.Unknown(text=f'[unsupported wecomcs msgtype: {msgtype or "unknown"}]'))

        return platform_message.MessageChain(components)
