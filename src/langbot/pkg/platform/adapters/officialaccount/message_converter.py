from __future__ import annotations

import datetime

from langbot.libs.official_account_api.oaevent import OAEvent
import langbot_plugin.api.definition.abstract.platform.adapter as abstract_platform_adapter
from langbot_plugin.api.entities.builtin.platform import message as platform_message


class OfficialAccountMessageConverter(abstract_platform_adapter.AbstractMessageConverter):
    @staticmethod
    async def yiri2target(message_chain: platform_message.MessageChain) -> str:
        content_parts: list[str] = []
        for component in message_chain:
            if isinstance(component, platform_message.Source):
                continue
            if isinstance(component, platform_message.Plain):
                content_parts.append(component.text)
            elif isinstance(component, platform_message.At):
                content_parts.append(f'@{component.display or component.target}')
            elif isinstance(component, platform_message.AtAll):
                content_parts.append('@all')
            elif isinstance(component, platform_message.Image):
                content_parts.append('[Image]')
            elif isinstance(component, platform_message.Voice):
                content_parts.append('[Voice]')
            elif isinstance(component, platform_message.File):
                content_parts.append(f'[File: {component.name or component.id or component.url or "file"}]')
            elif isinstance(component, platform_message.Quote):
                if component.id is not None:
                    content_parts.append(f'[Quote {component.id}]')
                if component.origin:
                    content_parts.append(await OfficialAccountMessageConverter.yiri2target(component.origin))
            elif isinstance(component, platform_message.Forward):
                for node in component.node_list:
                    if node.message_chain:
                        content_parts.append(await OfficialAccountMessageConverter.yiri2target(node.message_chain))
            else:
                content_parts.append(str(component))
        return '\n'.join(part for part in content_parts if part)

    @staticmethod
    async def target2yiri(event: OAEvent) -> platform_message.MessageChain:
        timestamp = event.timestamp or int(datetime.datetime.now().timestamp())
        components: list[platform_message.MessageComponent] = [
            platform_message.Source(
                id=event.message_id or f'{event.user_id}:{timestamp}',
                time=datetime.datetime.fromtimestamp(timestamp),
            )
        ]

        if event.type == 'text' and event.message:
            components.append(platform_message.Plain(text=event.message))
        elif event.type == 'image':
            image_kwargs = {}
            if event.picurl:
                image_kwargs['url'] = event.picurl
            if event.media_id:
                image_kwargs['image_id'] = event.media_id
            if image_kwargs:
                components.append(platform_message.Image(**image_kwargs))
        elif event.type == 'voice':
            if event.media_id:
                components.append(platform_message.Voice(voice_id=event.media_id))
            else:
                components.append(platform_message.Unknown(text='[officialaccount voice message without media id]'))
        elif event.type == 'event':
            components.append(platform_message.Unknown(text=f'[officialaccount event: {event.detail_type or "unknown"}]'))
        else:
            components.append(platform_message.Unknown(text=f'[unsupported officialaccount msgtype: {event.type or "unknown"}]'))

        return platform_message.MessageChain(components)
