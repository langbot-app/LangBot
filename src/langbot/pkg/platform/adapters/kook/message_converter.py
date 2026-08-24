from __future__ import annotations

import datetime
import re

from langbot_plugin.api.entities.builtin.platform import message as platform_message


MENTION_PATTERN = re.compile(r'(\(met\)(?P<met>[^()]+)\(met\)|\(rol\)(?P<role>[^()]+)\(rol\))')


class KookMessageConverter:
    @staticmethod
    async def yiri2target(message_chain: platform_message.MessageChain) -> tuple[str, int]:
        content_parts: list[str] = []
        message_type = 1

        for component in message_chain:
            if isinstance(component, platform_message.Source):
                continue
            if isinstance(component, platform_message.Plain):
                content_parts.append(component.text)
            elif isinstance(component, platform_message.At):
                if component.target:
                    content_parts.append(f'(met){component.target}(met)')
            elif isinstance(component, platform_message.AtAll):
                content_parts.append('(met)all(met)')
            elif isinstance(component, platform_message.Image):
                if component.url:
                    content_parts.append(component.url)
                    message_type = 2
                elif component.image_id:
                    content_parts.append(component.image_id)
                    message_type = 2
            elif isinstance(component, platform_message.File):
                if component.url:
                    content_parts.append(component.url)
                    message_type = 4
            elif isinstance(component, platform_message.Voice):
                if component.url:
                    content_parts.append(component.url)
                    message_type = 8
            elif isinstance(component, platform_message.Forward):
                for node in component.node_list:
                    if node.message_chain:
                        forward_content, _ = await KookMessageConverter.yiri2target(node.message_chain)
                        content_parts.append(forward_content)

        return ''.join(content_parts), message_type

    @staticmethod
    async def target2yiri(kook_message: dict, bot_account_id: str = '') -> platform_message.MessageChain:
        components: list[platform_message.MessageComponent] = []

        msg_id = kook_message.get('msg_id') or kook_message.get('id') or ''
        timestamp = KookMessageConverter._timestamp(kook_message.get('msg_timestamp'))
        if msg_id:
            components.append(platform_message.Source(id=str(msg_id), time=timestamp))

        msg_type = int(kook_message.get('type', 1) or 1)
        content = str(kook_message.get('content') or '')
        extra = kook_message.get('extra') or {}

        if msg_type in (1, 9):
            components.extend(KookMessageConverter._parse_text_components(content, extra, bot_account_id))
        elif msg_type == 2:
            if content:
                components.append(platform_message.Image(url=content))
        elif msg_type == 4:
            attachments = extra.get('attachments') or {}
            components.append(
                platform_message.File(
                    id=str(attachments.get('id') or ''),
                    name=str(attachments.get('name') or 'file'),
                    size=int(attachments.get('size') or 0),
                    url=content,
                )
            )
        elif msg_type == 8:
            attachments = extra.get('attachments') or {}
            components.append(platform_message.Voice(url=content, length=int(attachments.get('duration') or 0)))
        elif msg_type == 10:
            components.append(platform_message.Unknown(text=content or '[KOOK card message]'))
        else:
            components.append(platform_message.Unknown(text=content or f'Unsupported KOOK message type: {msg_type}'))

        if len(components) == 1 and isinstance(components[0], platform_message.Source):
            components.append(platform_message.Plain(text=''))

        return platform_message.MessageChain(components)

    @staticmethod
    def _parse_text_components(
        content: str,
        extra: dict,
        bot_account_id: str,
    ) -> list[platform_message.MessageComponent]:
        components: list[platform_message.MessageComponent] = []
        mention_all = bool(extra.get('mention_all', False))
        mentions = {str(item) for item in extra.get('mention', [])}
        mention_roles = {str(item) for item in extra.get('mention_roles', [])}

        last = 0
        for match in MENTION_PATTERN.finditer(content):
            if match.start() > last:
                components.append(platform_message.Plain(text=content[last : match.start()]))
            met = match.group('met')
            role = match.group('role')
            if met == 'all':
                components.append(platform_message.AtAll())
            elif met:
                components.append(platform_message.At(target=met))
                mentions.discard(str(met))
            elif role:
                mention_roles.discard(str(role))
                if bot_account_id:
                    components.append(platform_message.At(target=bot_account_id))
            last = match.end()

        if last < len(content):
            components.append(platform_message.Plain(text=content[last:]))

        if mention_all and not any(isinstance(item, platform_message.AtAll) for item in components):
            components.insert(0, platform_message.AtAll())
        for mention_id in sorted(mentions):
            components.insert(0, platform_message.At(target=mention_id))
        if mention_roles and bot_account_id:
            components.insert(0, platform_message.At(target=bot_account_id))

        return components

    @staticmethod
    def _timestamp(raw_timestamp) -> datetime.datetime:
        if raw_timestamp is None:
            return datetime.datetime.now()
        timestamp = float(raw_timestamp)
        if timestamp > 10_000_000_000:
            timestamp = timestamp / 1000.0
        return datetime.datetime.fromtimestamp(timestamp)
