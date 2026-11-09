"""Single source of truth for the media of an inbound message.

Every Runner input is derived from one ordered list of media collected from the
platform message chain:

- ``contents`` are what the model sees; each media item is preceded by a text
  marker such as ``[attachment att-1: image photo.jpg]`` at its position.
- ``attachments`` describe the same media one-to-one as metadata only.
- Bytes are read on demand by ref (``read_input_attachment``) or imported into a
  Box. They never travel inside attachment descriptors.
"""

from __future__ import annotations

import asyncio
import base64
import dataclasses
import mimetypes
import os
import typing

import langbot_plugin.api.entities.builtin.platform.message as platform_message
from langbot_plugin.api.entities.builtin.provider import message as provider_message

from ...platform.face_text import face_to_model_text
from ...utils import httpclient

MediaComponent = typing.Union[platform_message.Image, platform_message.Voice, platform_message.File]

MEDIA_TYPES = (platform_message.Image, platform_message.Voice, platform_message.File)

# Bounds every single attachment materialized into Host memory.
MAX_ATTACHMENT_BYTES = 10 * 1024 * 1024
# Bounds the cumulative bytes one run may read through read_input_attachment.
MAX_RUN_READ_BYTES = 50 * 1024 * 1024

ORIGIN_MESSAGE = 'message'
ORIGIN_QUOTE = 'quote'


@dataclasses.dataclass(frozen=True)
class InputMedia:
    """One media component of the current message, addressed by ``ref``."""

    ref: str
    component: MediaComponent
    origin: str = ORIGIN_MESSAGE

    @property
    def kind(self) -> str:
        if isinstance(self.component, platform_message.Image):
            return 'image'
        if isinstance(self.component, platform_message.Voice):
            return 'voice'
        return 'file'

    @property
    def name(self) -> str | None:
        return getattr(self.component, 'name', None) or None

    @property
    def mime_type(self) -> str | None:
        return _data_url_mime(getattr(self.component, 'base64', None)) or (
            mimetypes.guess_type(self.name)[0] if self.name else None
        )

    @property
    def platform_id(self) -> str | None:
        component = self.component
        value = getattr(component, 'image_id', None) or getattr(component, 'voice_id', None)
        if isinstance(component, platform_message.File):
            value = component.id
        return str(value) if value else None

    @property
    def url(self) -> str | None:
        url = getattr(self.component, 'url', None)
        return url if isinstance(url, str) and url.startswith(('http://', 'https://')) else None

    def marker(self) -> str:
        """Text marker that places this media in the input text."""
        label = f'{self.kind} {self.name}' if self.name else self.kind
        return f'[attachment {self.ref}: {label}]'

    def to_attachment(self, *, include_content: bool = False) -> dict[str, typing.Any]:
        """``InputAttachment`` payload for this media.

        ``include_content`` keeps the inline payload for Host-internal transport
        (event envelopes); ``prepare_input_files`` moves it into the run's
        registry before a Runner sees the descriptor.
        """
        size = getattr(self.component, 'size', None)
        attachment = {
            'ref': self.ref,
            'type': self.kind,
            'source': self.origin,
            'name': self.name,
            'mime_type': self.mime_type,
            'size': size if isinstance(size, int) and size > 0 else None,
            'id': self.platform_id,
            'url': self.url,
        }
        if include_content:
            attachment['content'] = getattr(self.component, 'base64', None) or None
        return attachment


@dataclasses.dataclass
class RenderedInput:
    """Runner input derived from a message chain."""

    contents: list[provider_message.ContentElement]
    media: list[InputMedia]
    # Plain text without markers, kept for the user_message_text variable.
    plain_text: str

    @property
    def text(self) -> str:
        return ''.join(item.text or '' for item in self.contents if item.type == 'text')

    def attachments(self, *, include_content: bool = False) -> list[dict[str, typing.Any]]:
        return [media.to_attachment(include_content=include_content) for media in self.media]


def _data_url_mime(value: typing.Any) -> str | None:
    if isinstance(value, str) and value.startswith('data:') and ';base64,' in value:
        return value[5 : value.index(';base64,')] or None
    return None


def render_input(
    chain: typing.Iterable[platform_message.MessageComponent] | None,
    *,
    include_quotes: bool,
    keep_images: bool = True,
    include_other_text: bool = False,
) -> RenderedInput:
    """Render a message chain into model contents and ordered media.

    Args:
        chain: Platform message chain of the current message.
        include_quotes: Render quoted messages and expose their media.
        keep_images: Forward image payloads to the model; otherwise only the
            marker describes the image.
        include_other_text: Render non-media components without a dedicated
            projection (such as mentions) with their string form.
    """
    contents: list[provider_message.ContentElement] = []
    media: list[InputMedia] = []
    plain_parts: list[str] = []

    def add_text(text: str, *, plain: bool = True) -> None:
        if not text:
            return
        contents.append(provider_message.ContentElement.from_text(text))
        if plain:
            plain_parts.append(text)

    def add_media(component: MediaComponent, origin: str) -> None:
        item = InputMedia(ref=f'att-{len(media) + 1}', component=component, origin=origin)
        media.append(item)
        add_text(item.marker(), plain=False)
        payload = component.base64 or None
        url = getattr(component, 'url', None) or None
        if isinstance(component, platform_message.Image):
            if not keep_images:
                plain_parts.append('[Image]')
            elif payload:
                contents.append(provider_message.ContentElement.from_image_base64(payload))
            elif url:
                contents.append(provider_message.ContentElement.from_image_url(url))
            return
        if isinstance(component, platform_message.Voice):
            name = 'voice.silk' if payload else 'voice'
        else:
            name = component.name
        if payload:
            contents.append(provider_message.ContentElement.from_file_base64(payload, name))
        elif url:
            contents.append(provider_message.ContentElement.from_file_url(url, name))

    def render(components: typing.Iterable[platform_message.MessageComponent], origin: str) -> None:
        for component in components:
            # Quoted text stays out of the plain user_message_text variable.
            plain = origin == ORIGIN_MESSAGE
            if isinstance(component, platform_message.Plain):
                add_text(component.text, plain=plain)
            elif isinstance(component, platform_message.Face):
                add_text(face_to_model_text(component), plain=plain)
            elif isinstance(component, MEDIA_TYPES):
                add_media(component, origin)
            elif isinstance(component, platform_message.Quote):
                if include_quotes and origin == ORIGIN_MESSAGE:
                    start = len(contents)
                    sender = f' from {component.sender_id}' if component.sender_id else ''
                    add_text(f'[quoted message{sender}]\n', plain=False)
                    render(component.origin, ORIGIN_QUOTE)
                    if len(contents) == start + 1:
                        # Nothing quoted to show, such as a thread root reference.
                        del contents[start:]
                    else:
                        add_text('\n[/quoted message]', plain=False)
            elif include_other_text and not isinstance(component, platform_message.Source):
                add_text(str(component), plain=plain)

    try:
        components = list(chain or [])
    except TypeError:
        components = []
    render(components, ORIGIN_MESSAGE)
    return RenderedInput(contents=contents, media=media, plain_text=''.join(plain_parts))


def media_by_ref(query: typing.Any) -> dict[str, InputMedia]:
    """Media addressable by ref for one execution query."""
    media = remembered_media(query)
    if media is None:
        media = render_input(getattr(query, 'message_chain', None), include_quotes=True).media
        remember_media(query, media)
    return {item.ref: item for item in media}


def remembered_media(query: typing.Any) -> list[InputMedia] | None:
    """Media list pinned by ``remember_media``, if any."""
    media = getattr(query, '_input_media', None)
    return media if isinstance(media, list) else None


def remember_media(query: typing.Any, media: list[InputMedia]) -> None:
    """Pin the media list the Runner input was rendered from to its query."""
    object.__setattr__(query, '_input_media', list(media))


async def read_component_bytes(
    component: typing.Any,
    *,
    max_bytes: int = MAX_ATTACHMENT_BYTES,
    adapter: typing.Any = None,
) -> tuple[bytes, str] | None:
    """Resolve the bytes of a platform media component.

    Tries inline base64, then an http(s) URL, then a Host-local path supplied by
    the platform adapter, then the adapter's ``get_file_url`` for an ID-only
    component. Returns None when nothing can be resolved within ``max_bytes``.
    """
    payload = getattr(component, 'base64', None)
    if payload:
        mime = _data_url_mime(payload) or 'application/octet-stream'
        data = payload.split(';base64,', 1)[1] if isinstance(payload, str) and ';base64,' in payload else payload
        if not isinstance(data, (str, bytes)) or len(data) > 4 * ((max_bytes + 2) // 3):
            return None
        try:
            decoded = base64.b64decode(data)
        except Exception:
            return None
        return (decoded, mime) if len(decoded) <= max_bytes else None

    url = getattr(component, 'url', None)
    if isinstance(url, str) and url.startswith(('http://', 'https://')):
        return await _download(url, max_bytes)

    path = getattr(component, 'path', None)
    if path:
        try:
            import aiofiles

            if await asyncio.to_thread(os.path.getsize, path) > max_bytes:
                return None
            async with aiofiles.open(path, 'rb') as f:
                data = await f.read(max_bytes + 1)
            return (data, 'application/octet-stream') if len(data) <= max_bytes else None
        except Exception:
            return None

    file_id = (
        getattr(component, 'id', None) or getattr(component, 'image_id', None) or getattr(component, 'voice_id', None)
    )
    get_file_url = getattr(adapter, 'get_file_url', None)
    if file_id and callable(get_file_url):
        try:
            resolved = await get_file_url(str(file_id))
        except Exception:
            return None
        if isinstance(resolved, str) and resolved.startswith(('http://', 'https://')):
            return await _download(resolved, max_bytes)
    return None


async def _download(url: str, max_bytes: int) -> tuple[bytes, str] | None:
    try:
        import httpx

        async with httpx.AsyncClient(
            timeout=30,
            event_hooks=httpclient.httpx_response_limit_hooks(max_bytes),
        ) as client:
            async with client.stream('GET', url) as resp:
                resp.raise_for_status()
                declared_size = resp.headers.get('content-length')
                if declared_size is not None:
                    try:
                        if int(declared_size) > max_bytes:
                            return None
                    except ValueError:
                        pass
                body = bytearray()
                async for chunk in resp.aiter_bytes(chunk_size=64 * 1024):
                    body.extend(chunk)
                    if len(body) > max_bytes:
                        return None
                return bytes(body), resp.headers.get('Content-Type', 'application/octet-stream')
    except Exception:
        return None
