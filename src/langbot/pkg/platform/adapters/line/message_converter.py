from __future__ import annotations

import base64
import datetime
import typing

import langbot_plugin.api.definition.abstract.platform.adapter as abstract_platform_adapter
from langbot_plugin.api.entities.builtin.platform import message as platform_message
from linebot.v3.messaging import ImageMessage, TextMessage
from linebot.v3.webhooks import (
    AudioMessageContent,
    FileMessageContent,
    ImageMessageContent,
    LocationMessageContent,
    MessageEvent,
    StickerMessageContent,
    TextMessageContent,
    UserMentionee,
    VideoMessageContent,
)

from langbot.pkg.platform.adapters.line.errors import NotSupportedError
from langbot.pkg.platform.adapters.line.types import MAX_LINE_MEDIA_BYTES, MAX_TEXT_LENGTH

# LINE stores inbound images as JPEG and the Blob API does not return the media type.
IMAGE_MIME = 'image/jpeg'


def _validate_media(content: bytes) -> bytes:
    """Reject inbound media above the LINE download cap."""
    if len(content) > MAX_LINE_MEDIA_BYTES:
        raise ValueError(f'LINE media exceeds the {MAX_LINE_MEDIA_BYTES}-byte limit')
    return content


def _split_text(text: str) -> list[str]:
    """Split a text body into LINE-sized chunks so long answers still send."""
    return [text[index : index + MAX_TEXT_LENGTH] for index in range(0, len(text), MAX_TEXT_LENGTH)]


def _message_datetime(event: MessageEvent) -> datetime.datetime:
    try:
        return datetime.datetime.fromtimestamp(float(event.timestamp) / 1000.0)
    except (AttributeError, TypeError, ValueError):
        return datetime.datetime.now()


def _text_components(text: str, mention: typing.Any, bot_account_id: str) -> list[platform_message.MessageComponent]:
    """Map LINE mention positions onto At components, as the legacy adapter does."""
    if not mention or not mention.mentionees:
        return [platform_message.Plain(text=text)] if text else []
    components: list[platform_message.MessageComponent] = []
    segments = sorted(
        (mentionee.index, mentionee.index + mentionee.length, mentionee) for mentionee in mention.mentionees
    )
    cursor = 0
    for start, end, mentionee in segments:
        if start < cursor:
            start, end = cursor, min(end, len(text))
        if start < cursor or end <= start or end > len(text):
            continue
        if start > cursor:
            components.append(platform_message.Plain(text=text[cursor:start]))
        token = text[start:end]
        if isinstance(mentionee, UserMentionee):
            target = bot_account_id if mentionee.is_self else (mentionee.user_id or token)
        else:
            target = token
        components.append(platform_message.At(target=str(target), display=token.lstrip('@')))
        cursor = end
    if cursor < len(text):
        components.append(platform_message.Plain(text=text[cursor:]))
    return components


async def _download_content(blob_api: typing.Any, message_id: str) -> bytes:
    """Fetch inbound media through the LINE Blob API without blocking the event loop."""
    import asyncio

    if blob_api is None:
        raise NotSupportedError('line:media_download')
    return await asyncio.to_thread(blob_api.get_message_content, message_id)


class LineMessageConverter(abstract_platform_adapter.AbstractMessageConverter):
    """Convert between LangBot message chains and LINE Messaging API messages."""

    @staticmethod
    async def yiri2target(message_chain: platform_message.MessageChain) -> list[typing.Any]:
        """Build the LINE message array for one push/reply request."""
        messages: list[typing.Any] = []
        for component in message_chain:
            if isinstance(component, platform_message.Source):
                continue
            if isinstance(component, platform_message.Plain):
                messages.extend(TextMessage(text=chunk) for chunk in _split_text(component.text or ''))
            elif isinstance(component, platform_message.At):
                messages.append(TextMessage(text=f'@{component.display or component.target}'))
            elif isinstance(component, platform_message.AtAll):
                messages.append(TextMessage(text='@All'))
            elif isinstance(component, platform_message.Image):
                url = component.url or ''
                if not url:
                    # LINE fetches outgoing images from a public URL; inline base64 is not supported.
                    raise NotSupportedError('send_message:line_image_requires_public_url')
                messages.append(ImageMessage(original_content_url=url, preview_image_url=url))
            elif isinstance(component, platform_message.Quote):
                if component.origin:
                    messages.extend(await LineMessageConverter.yiri2target(component.origin))
            elif isinstance(component, platform_message.Forward):
                for node in component.node_list:
                    if node.message_chain:
                        messages.extend(await LineMessageConverter.yiri2target(node.message_chain))
            elif isinstance(component, platform_message.Unknown):
                if component.text:
                    messages.extend(TextMessage(text=chunk) for chunk in _split_text(component.text))
            else:
                raise NotSupportedError(f'send_message:line_unsupported_component:{type(component).__name__}')
        return messages

    @staticmethod
    async def target2yiri(
        event: MessageEvent,
        blob_api: typing.Any = None,
        bot_account_id: str = '',
    ) -> platform_message.MessageChain:
        """Build a LangBot message chain from a LINE message event."""
        message = event.message
        components: list[platform_message.MessageComponent] = [
            platform_message.Source(
                id=str(getattr(message, 'id', '') or event.webhook_event_id), time=_message_datetime(event)
            )
        ]
        if isinstance(message, TextMessageContent):
            components.extend(_text_components(message.text, getattr(message, 'mention', None), bot_account_id))
        elif isinstance(message, ImageMessageContent):
            encoded = base64.b64encode(_validate_media(await _download_content(blob_api, message.id))).decode('ascii')
            components.append(platform_message.Image(base64=f'data:{IMAGE_MIME};base64,{encoded}'))
        elif isinstance(message, AudioMessageContent):
            encoded = base64.b64encode(_validate_media(await _download_content(blob_api, message.id))).decode('ascii')
            components.append(platform_message.Voice(base64=encoded, length=int(getattr(message, 'duration', 0) or 0)))
        elif isinstance(message, VideoMessageContent):
            components.append(platform_message.Unknown(text='[video]'))
        elif isinstance(message, StickerMessageContent):
            components.append(platform_message.Unknown(text='[sticker]'))
        elif isinstance(message, FileMessageContent):
            components.append(platform_message.Unknown(text=f'[file] {getattr(message, "file_name", "")}'.strip()))
        elif isinstance(message, LocationMessageContent):
            components.append(
                platform_message.Unknown(
                    text=f'[location] {getattr(message, "title", "")} {getattr(message, "address", "")}'.strip()
                )
            )
        else:
            components.append(platform_message.Unknown(text=f'[unsupported line message: {type(message).__name__}]'))
        if len(components) == 1:
            components.append(platform_message.Unknown(text=f'[unsupported line message: {type(message).__name__}]'))
        return platform_message.MessageChain(components)
