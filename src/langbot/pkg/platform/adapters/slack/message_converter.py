from __future__ import annotations

import datetime

from langbot.libs.slack_api.slackevent import SlackEvent
from langbot.pkg.utils import image
import langbot_plugin.api.definition.abstract.platform.adapter as abstract_platform_adapter
from langbot_plugin.api.entities.builtin.platform import message as platform_message


class SlackMessageConverter(abstract_platform_adapter.AbstractMessageConverter):
    @staticmethod
    async def yiri2target(message_chain: platform_message.MessageChain) -> str:
        parts: list[str] = []
        for component in message_chain:
            if isinstance(component, platform_message.Source):
                continue
            if isinstance(component, platform_message.Plain):
                parts.append(component.text)
            elif isinstance(component, platform_message.At):
                parts.append(f'<@{component.target}>')
            elif isinstance(component, platform_message.AtAll):
                parts.append('<!channel>')
            elif isinstance(component, platform_message.Image):
                parts.append(component.url or '[Image]')
            elif isinstance(component, platform_message.Voice):
                parts.append(component.url or '[Voice]')
            elif isinstance(component, platform_message.File):
                parts.append(component.url or component.name or component.id or '[File]')
            elif isinstance(component, platform_message.Quote):
                if component.id is not None:
                    parts.append(f'[Quote {component.id}]')
                if component.origin:
                    parts.append(await SlackMessageConverter.yiri2target(component.origin))
            elif isinstance(component, platform_message.Forward):
                for node in component.node_list:
                    if node.message_chain:
                        parts.append(await SlackMessageConverter.yiri2target(node.message_chain))
            else:
                text = str(component)
                if text:
                    parts.append(text)
        return '\n'.join(part for part in parts if part)

    @staticmethod
    async def target2yiri(event: SlackEvent, bot_token: str = '') -> platform_message.MessageChain:
        message_id = event.message_id or event.get('event', {}).get('event_ts') or ''
        components: list[platform_message.MessageComponent] = [
            platform_message.Source(
                id=message_id,
                time=_event_datetime(event),
            )
        ]

        if event.type == 'channel':
            components.append(platform_message.At(target='SlackBot'))

        if event.pic_url:
            try:
                components.append(platform_message.Image(base64=await image.get_slack_image_to_base64(event.pic_url, bot_token)))
            except Exception:
                components.append(platform_message.Image(url=event.pic_url))

        if event.text:
            components.append(platform_message.Plain(text=event.text))

        if len(components) == 1 or (
            len(components) == 2 and isinstance(components[1], platform_message.At)
        ):
            components.append(platform_message.Unknown(text=f'[unsupported slack event: {event.type or "unknown"}]'))

        return platform_message.MessageChain(components)


def _event_datetime(event: SlackEvent) -> datetime.datetime:
    raw_ts = event.get('event', {}).get('ts') or event.get('event', {}).get('event_ts')
    try:
        return datetime.datetime.fromtimestamp(float(raw_ts))
    except (TypeError, ValueError):
        return datetime.datetime.now()
