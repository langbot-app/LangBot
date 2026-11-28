"""Parse QQ Official face markup without changing unrecognized user text.

QQ Official can deliver a face as an XML-like token inside the message text,
rather than as a separate event field. Preserve the original wire text on
QQOfficialEvent; converters use this helper only to construct MessageChain.
"""

from __future__ import annotations

import base64
import binascii
import json
import re

from langbot_plugin.api.entities.builtin.platform import message as platform_message


# Bound the payload before base64/JSON decoding. Unknown or malformed tags are
# kept verbatim in Plain instead of being silently deleted.
_FACE_MARKUP = re.compile(r'<faceType=\d{1,2},faceId="([^"]{0,32})",ext="([^"]{1,2048})">')
_FACE_TEXT_MAX_LENGTH = 80


def _face_from_markup(match: re.Match[str]) -> platform_message.Face | None:
    encoded = match.group(2)
    try:
        decoded = base64.b64decode(encoded + '=' * (-len(encoded) % 4), validate=True)
        metadata = json.loads(decoded.decode('utf-8'))
    except (ValueError, UnicodeError, binascii.Error, json.JSONDecodeError):
        return None

    if not isinstance(metadata, dict) or not isinstance(metadata.get('text'), str):
        return None

    name = ' '.join(metadata['text'].split())
    if name.startswith('[') and name.endswith(']'):
        name = name[1:-1].strip()
    if not name or len(name) > _FACE_TEXT_MAX_LENGTH:
        return None

    # The SDK's Face.face_type is "face"/"dice"/"rps", not QQ's numeric
    # faceType. Do not conflate those two unrelated enum namespaces.
    native_id = match.group(1)
    face_id = int(native_id) if native_id.isdecimal() else 0
    return platform_message.Face(face_id=face_id, face_name=name)


def parse_qqofficial_face_components(text: str | None) -> list[platform_message.MessageComponent]:
    """Split ordinary text and recognizable QQ face tags in original order.

    Preserves all non-face and malformed input byte-for-byte as Plain text.
    Raw event content remains available to platform-specific plugin handlers.
    """
    if not text:
        return [platform_message.Plain(text='')]

    components: list[platform_message.MessageComponent] = []
    cursor = 0
    for match in _FACE_MARKUP.finditer(text):
        face = _face_from_markup(match)
        if face is None:
            continue
        if match.start() > cursor:
            components.append(platform_message.Plain(text=text[cursor : match.start()]))
        components.append(face)
        cursor = match.end()

    if cursor < len(text):
        components.append(platform_message.Plain(text=text[cursor:]))
    return components or [platform_message.Plain(text=text)]
