from __future__ import annotations

import datetime
import html
import re

from langbot.libs.qq_official_api.qqofficialevent import QQOfficialEvent
from langbot.pkg.utils import image
import langbot_plugin.api.definition.abstract.platform.adapter as abstract_platform_adapter
from langbot_plugin.api.entities.builtin.platform import message as platform_message


def _is_base64_data(value: str) -> bool:
    if not value:
        return False
    if value.startswith('data:'):
        return True
    if value.startswith(('http://', 'https://', '/', './', '../')):
        return False
    return bool(re.fullmatch(r'[A-Za-z0-9+/=\s]{20,}', value))


class QQOfficialMessageConverter(abstract_platform_adapter.AbstractMessageConverter):
    @staticmethod
    async def yiri2target(
        message_chain: platform_message.MessageChain,
        target_type: str | None = None,
        *,
        use_markdown: bool = False,
    ) -> list[dict]:
        content_list: list[dict] = []
        text_parts: list[str] = []

        def flush_text() -> None:
            content = ''.join(text_parts)
            if content:
                content_list.append({'type': 'text', 'content': content})
            text_parts.clear()

        for component in message_chain:
            if isinstance(component, platform_message.Source):
                continue
            if isinstance(component, platform_message.Plain):
                text_parts.append(component.text)
                continue
            elif isinstance(component, platform_message.At):
                if target_type == 'group' and not use_markdown:
                    continue
                if target_type in {None, 'group', 'channel'}:
                    target = html.escape(str(component.target), quote=True)
                    text_parts.append(f'<qqbot-at-user id="{target}" />')
                else:
                    text_parts.append(f'@{component.display or component.target}')
                continue
            elif isinstance(component, platform_message.AtAll):
                text_parts.append('<qqbot-at-everyone />' if target_type == 'channel' else '@all')
                continue

            flush_text()
            if isinstance(component, platform_message.Image):
                content_list.append(QQOfficialMessageConverter._media_payload(component, 'image'))
            elif isinstance(component, platform_message.Voice):
                content_list.append(QQOfficialMessageConverter._media_payload(component, 'voice'))
            elif isinstance(component, platform_message.File):
                payload = QQOfficialMessageConverter._media_payload(component, 'file')
                payload['name'] = component.name or component.id or 'file'
                content_list.append(payload)
            elif isinstance(component, platform_message.Quote):
                if component.id is not None:
                    content_list.append({'type': 'text', 'content': f'[Quote {component.id}]'})
                if component.origin:
                    content_list.extend(
                        await QQOfficialMessageConverter.yiri2target(
                            component.origin, target_type, use_markdown=use_markdown
                        )
                    )
            elif isinstance(component, platform_message.Forward):
                for node in component.node_list:
                    if node.message_chain:
                        content_list.extend(
                            await QQOfficialMessageConverter.yiri2target(
                                node.message_chain, target_type, use_markdown=use_markdown
                            )
                        )
            else:
                text = str(component)
                if text:
                    content_list.append({'type': 'text', 'content': text})
        flush_text()
        return content_list

    @staticmethod
    def _media_payload(component, content_type: str) -> dict:
        url = getattr(component, 'url', '') or getattr(component, 'path', '') or None
        b64 = getattr(component, 'base64', '') or None
        if url and not b64 and _is_base64_data(url):
            b64 = url
            url = None
        return {'type': content_type, 'url': url, 'base64': b64}

    @staticmethod
    async def target2yiri(event: QQOfficialEvent) -> platform_message.MessageChain:
        components: list[platform_message.MessageComponent] = [
            platform_message.Source(id=event.d_id or event.id or '', time=_parse_timestamp(event.timestamp)),
        ]

        if event.is_at_bot:
            components.append(platform_message.At(target=event.get('bot_account_id') or 'justbot'))

        if event.attachments:
            try:
                base64_url = await image.get_qq_official_image_base64(
                    pic_url=event.attachments,
                    content_type=event.content_type,
                )
                components.append(platform_message.Image(url=event.attachments, base64=base64_url))
            except Exception:
                components.append(platform_message.Image(url=event.attachments))

        if event.content:
            components.append(platform_message.Plain(text=event.content))

        if len(components) == 1 or (len(components) == 2 and isinstance(components[1], platform_message.At)):
            components.append(platform_message.Unknown(text=f'[unsupported qqofficial event: {event.t or "unknown"}]'))

        return platform_message.MessageChain(components)


def _parse_timestamp(value: str) -> datetime.datetime:
    if not value:
        return datetime.datetime.now()
    try:
        return datetime.datetime.strptime(value, '%Y-%m-%dT%H:%M:%S%z')
    except (TypeError, ValueError):
        return datetime.datetime.now()
