from __future__ import annotations

import datetime

from langbot.libs.wecom_ai_bot_api.wecombotevent import WecomBotEvent
import langbot_plugin.api.definition.abstract.platform.adapter as abstract_platform_adapter
from langbot_plugin.api.entities.builtin.platform import message as platform_message


class WecomBotMessageConverter(abstract_platform_adapter.AbstractMessageConverter):
    @staticmethod
    async def yiri2target(message_chain: platform_message.MessageChain) -> str:
        content_parts: list[str] = []
        for msg in message_chain:
            if isinstance(msg, platform_message.Source):
                continue
            if isinstance(msg, platform_message.Plain):
                content_parts.append(msg.text)
            elif isinstance(msg, platform_message.At):
                content_parts.append(f'@{msg.display or msg.target}')
            elif isinstance(msg, platform_message.AtAll):
                content_parts.append('@all')
            elif isinstance(msg, platform_message.Image):
                content_parts.append('[Image]')
            elif isinstance(msg, platform_message.Voice):
                content_parts.append('[Voice]')
            elif isinstance(msg, platform_message.File):
                content_parts.append(f'[File: {msg.name or msg.file_id or msg.url or "file"}]')
            elif isinstance(msg, platform_message.Quote):
                if msg.id is not None:
                    content_parts.append(f'[Quote {msg.id}]')
                if msg.origin:
                    content_parts.append(await WecomBotMessageConverter.yiri2target(msg.origin))
            elif isinstance(msg, platform_message.Forward):
                for node in msg.node_list:
                    if node.message_chain:
                        content_parts.append(await WecomBotMessageConverter.yiri2target(node.message_chain))
            else:
                content_parts.append(str(msg))
        return '\n'.join(part for part in content_parts if part)

    @staticmethod
    async def target2yiri(event: WecomBotEvent, bot_name: str = '') -> platform_message.MessageChain:
        components: list[platform_message.MessageComponent] = [
            platform_message.Source(id=event.message_id, time=datetime.datetime.now()),
        ]
        if event.type == 'group' and event.ai_bot_id:
            components.append(platform_message.At(target=event.ai_bot_id))

        if event.content:
            content = event.content
            if bot_name:
                content = content.replace(f'@{bot_name}', '').strip()
            if content:
                components.append(platform_message.Plain(text=content))

        WecomBotMessageConverter._append_images(components, event.images or ([event.picurl] if event.picurl else []))
        WecomBotMessageConverter._append_file(components, event.file)
        WecomBotMessageConverter._append_voice(components, event.voice)
        WecomBotMessageConverter._append_video(components, event.video)
        WecomBotMessageConverter._append_link(components, event.link)
        WecomBotMessageConverter._append_quote(components, event.quote)

        if not any(not isinstance(component, (platform_message.Source, platform_message.At)) for component in components):
            components.append(platform_message.Unknown(text=f'[unsupported wecombot msgtype: {event.msgtype or "unknown"}]'))

        return platform_message.MessageChain(components)

    @staticmethod
    def _append_images(components: list[platform_message.MessageComponent], images: list[str]):
        for image_data in images:
            if image_data:
                components.append(platform_message.Image(base64=image_data))

    @staticmethod
    def _append_file(components: list[platform_message.MessageComponent], file_info: dict | None):
        if not file_info:
            return
        file_url = file_info.get('download_url') or file_info.get('url') or file_info.get('fileurl') or file_info.get('path')
        file_base64 = file_info.get('base64')
        file_name = file_info.get('filename') or file_info.get('name')
        file_size = file_info.get('filesize') or file_info.get('size')
        try:
            kwargs = {}
            if file_url:
                kwargs['url'] = file_url
            if file_base64:
                kwargs['base64'] = file_base64
            if file_name:
                kwargs['name'] = file_name
            if file_size is not None:
                kwargs['size'] = file_size
            if kwargs:
                components.append(platform_message.File(**kwargs))
        except Exception:
            components.append(platform_message.Unknown(text='[file message unsupported]'))

    @staticmethod
    def _append_voice(components: list[platform_message.MessageComponent], voice_info: dict | None):
        if not voice_info:
            return
        voice_payload = voice_info.get('base64') or voice_info.get('url')
        if not voice_payload:
            return
        if voice_info.get('base64') and not voice_payload.startswith('data:'):
            voice_payload = f'data:audio/mpeg;base64,{voice_info.get("base64")}'
        try:
            if voice_payload.startswith('data:'):
                components.append(platform_message.Voice(base64=voice_payload))
            else:
                components.append(platform_message.Voice(url=voice_payload))
        except Exception:
            components.append(platform_message.Unknown(text='[voice message unsupported]'))

    @staticmethod
    def _append_video(components: list[platform_message.MessageComponent], video_info: dict | None):
        if not video_info:
            return
        video_payload = (
            video_info.get('base64')
            or video_info.get('url')
            or video_info.get('download_url')
            or video_info.get('fileurl')
        )
        if not video_payload:
            return
        try:
            components.append(
                platform_message.File(
                    url=video_payload,
                    name=video_info.get('filename') or video_info.get('name') or 'video',
                    size=video_info.get('filesize') or video_info.get('size'),
                )
            )
        except Exception:
            components.append(platform_message.Unknown(text='[video message unsupported]'))

    @staticmethod
    def _append_link(components: list[platform_message.MessageComponent], link: dict | None, prefix: str = ''):
        if not link:
            return
        summary = '\n'.join(
            filter(None, [link.get('title', ''), link.get('description') or link.get('digest', ''), link.get('url', '')])
        )
        if summary:
            components.append(platform_message.Plain(text=f'{prefix}{summary}'))

    @staticmethod
    def _append_quote(components: list[platform_message.MessageComponent], quote_info: dict | None):
        if not quote_info:
            return
        origin: list[platform_message.MessageComponent] = []
        if quote_info.get('content'):
            origin.append(platform_message.Plain(text=quote_info.get('content')))
        WecomBotMessageConverter._append_images(origin, quote_info.get('images') or ([quote_info.get('picurl')] if quote_info.get('picurl') else []))
        WecomBotMessageConverter._append_file(origin, quote_info.get('file'))
        WecomBotMessageConverter._append_voice(origin, quote_info.get('voice'))
        WecomBotMessageConverter._append_video(origin, quote_info.get('video'))
        WecomBotMessageConverter._append_link(origin, quote_info.get('link'))
        if origin:
            components.append(platform_message.Quote(origin=platform_message.MessageChain(origin)))
