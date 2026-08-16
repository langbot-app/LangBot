from __future__ import annotations

import datetime
import typing

from langbot.libs.dingtalk_api.dingtalkevent import DingTalkEvent
import langbot_plugin.api.definition.abstract.platform.adapter as abstract_platform_adapter
from langbot_plugin.api.entities.builtin.platform import message as platform_message


class DingTalkMessageConverter(abstract_platform_adapter.AbstractMessageConverter):
    @staticmethod
    def _format_image_as_markdown(msg: platform_message.Image) -> str:
        if msg.url:
            return f'\n![image]({msg.url})\n'
        if msg.base64:
            if msg.base64.startswith('data:'):
                return f'\n![image]({msg.base64})\n'
            return f'\n![image](data:image/png;base64,{msg.base64})\n'
        return ''

    @staticmethod
    def _component_text_fallback(component: platform_message.MessageComponent) -> str:
        if isinstance(component, platform_message.At):
            return f'@{component.display or component.target}'
        if isinstance(component, platform_message.AtAll):
            return '@所有人'
        if isinstance(component, platform_message.File):
            if component.url:
                return f'\n[{component.name or "file"}]({component.url})\n'
            return f'\n[File]{component.name or component.id or "file"}\n'
        if isinstance(component, platform_message.Voice):
            return component.url or '[Voice]'
        if isinstance(component, platform_message.Face):
            return str(component)
        if isinstance(component, platform_message.Unknown):
            return component.text
        return str(component)

    @staticmethod
    async def yiri2target(
        message_chain: platform_message.MessageChain,
        markdown_enabled: bool = True,
    ) -> tuple[str, bool]:
        content = ''
        at = False
        for msg in message_chain:
            if isinstance(msg, platform_message.Source):
                continue
            if isinstance(msg, platform_message.Plain):
                content += msg.text
            elif isinstance(msg, platform_message.At):
                at = True
                content += DingTalkMessageConverter._component_text_fallback(msg)
            elif isinstance(msg, platform_message.AtAll):
                content += DingTalkMessageConverter._component_text_fallback(msg)
            elif isinstance(msg, platform_message.Image):
                if markdown_enabled:
                    content += DingTalkMessageConverter._format_image_as_markdown(msg)
                else:
                    content += '[Image]'
            elif isinstance(msg, platform_message.File):
                content += DingTalkMessageConverter._component_text_fallback(msg)
            elif isinstance(msg, platform_message.Voice):
                content += DingTalkMessageConverter._component_text_fallback(msg)
            elif isinstance(msg, platform_message.Quote):
                if msg.id is not None:
                    content += f'[引用消息 {msg.id}] '
                if msg.origin:
                    quote_content, quote_at = await DingTalkMessageConverter.yiri2target(msg.origin, markdown_enabled)
                    content += quote_content
                    at = at or quote_at
            elif isinstance(msg, platform_message.Forward):
                for node in msg.node_list:
                    sender = node.sender_name or node.sender_id or ''
                    if sender:
                        content += f'\n[{sender}] '
                    if node.message_chain:
                        forwarded_content, forwarded_at = await DingTalkMessageConverter.yiri2target(
                            node.message_chain, markdown_enabled
                        )
                        content += forwarded_content
                        at = at or forwarded_at
            else:
                content += DingTalkMessageConverter._component_text_fallback(msg)
        return content, at

    @staticmethod
    async def target2yiri(event: DingTalkEvent, bot_name: str) -> platform_message.MessageChain:
        incoming_message = event.incoming_message
        components: list[platform_message.MessageComponent] = [
            platform_message.Source(
                id=getattr(incoming_message, 'message_id', ''),
                time=DingTalkMessageConverter._message_time(incoming_message),
            )
        ]

        for at_user in getattr(incoming_message, 'at_users', []) or []:
            if getattr(at_user, 'dingtalk_id', None) == getattr(incoming_message, 'chatbot_user_id', None):
                components.append(platform_message.At(target=bot_name, display=bot_name))

        rich_content = event.rich_content
        if rich_content:
            for element in rich_content.get('Elements') or []:
                if element.get('Type') == 'text':
                    text = DingTalkMessageConverter._strip_bot_mention(element.get('Content', ''), bot_name)
                    if text.strip():
                        components.append(platform_message.Plain(text=text))
                elif element.get('Type') == 'image' and element.get('Picture'):
                    components.append(platform_message.Image(base64=element['Picture']))
        else:
            if event.content and event.type != 'audio':
                components.append(
                    platform_message.Plain(
                        text=DingTalkMessageConverter._strip_bot_mention(event.content, bot_name),
                    )
                )
            if event.picture:
                components.append(platform_message.Image(base64=event.picture))

        if event.file:
            components.append(platform_message.File(url=event.file, name=event.name or 'file'))
        if event.audio:
            if event.content and event.type == 'audio':
                components.append(platform_message.Plain(text=event.content))
            else:
                components.append(platform_message.Voice(base64=event.audio))

        quote = DingTalkMessageConverter._quote_component(event)
        if quote:
            components.append(quote)

        return platform_message.MessageChain(components)

    @staticmethod
    def _quote_component(event: DingTalkEvent) -> platform_message.Quote | None:
        quote_info = event.quoted_message
        if not quote_info:
            return None
        origin_components: list[platform_message.MessageComponent] = []
        msg_type = quote_info.get('msg_type', '')
        if msg_type == 'file' and quote_info.get('file_url'):
            origin_components.append(
                platform_message.File(url=quote_info['file_url'], name=quote_info.get('file_name', 'file'))
            )
        elif msg_type == 'picture' and quote_info.get('picture'):
            origin_components.append(platform_message.Image(base64=quote_info['picture']))
        elif msg_type == 'audio' and quote_info.get('audio'):
            origin_components.append(platform_message.Voice(base64=quote_info['audio']))
        elif quote_info.get('content'):
            origin_components.append(platform_message.Plain(text=str(quote_info['content'])))

        incoming_message = event.incoming_message
        return platform_message.Quote(
            id=quote_info.get('message_id') or None,
            group_id=getattr(incoming_message, 'conversation_id', None),
            sender_id=quote_info.get('sender_id') or None,
            target_id=getattr(incoming_message, 'conversation_id', None)
            or getattr(incoming_message, 'sender_staff_id', None),
            origin=platform_message.MessageChain(origin_components),
        )

    @staticmethod
    def _strip_bot_mention(text: str, bot_name: str) -> str:
        return text.replace('@' + bot_name, '')

    @staticmethod
    def _message_time(incoming_message: typing.Any) -> datetime.datetime:
        value = getattr(incoming_message, 'create_at', None)
        if isinstance(value, datetime.datetime):
            return value
        if isinstance(value, (int, float)):
            timestamp = float(value)
            if timestamp > 10_000_000_000:
                timestamp = timestamp / 1000
            return datetime.datetime.fromtimestamp(timestamp)
        return datetime.datetime.now()
