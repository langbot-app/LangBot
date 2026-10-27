"""DingTalk A2UI message builders shared by both DingTalk adapters."""

from __future__ import annotations

import json
import typing


A2UI_CATALOG_ID = 'https://dingtalk.com/card/a2ui/catalogs/public/catalog.json'
A2UI_MESSAGE_VERSION = 'v1.0'
A2UI_PROTOCOL_VERSION = '1.0'
LANGBOT_LOGO_URL = 'https://langbot.app/logo-blue.png'
LANGBOT_CARD_URL = 'https://langbot.app?utm_source=dingtalk&utm_medium=bot_card&utm_campaign=langbot'


def binding(path: str) -> dict[str, str]:
    return {'path': path}


def brand_components() -> list[dict[str, typing.Any]]:
    return [
        {
            'id': 'langbot-brand',
            'component': 'Row',
            'children': ['langbot-brand-icon', 'langbot-brand-link'],
            'align': 'center',
            'gap': 4,
        },
        {
            'id': 'langbot-brand-icon',
            'component': 'Image',
            'url': LANGBOT_LOGO_URL,
            'variant': 'icon',
            'fit': 'contain',
            'previewEnabled': False,
        },
        {
            'id': 'langbot-brand-link',
            'component': 'Markdown',
            'content': f'[LangBot]({LANGBOT_CARD_URL})',
        },
    ]


def serialize_messages(messages: typing.Iterable[dict | str]) -> list[str]:
    serialized = [
        message if isinstance(message, str) else json.dumps(message, ensure_ascii=False, separators=(',', ':'))
        for message in messages
    ]
    if not serialized:
        raise ValueError('DingTalk A2UI messages must not be empty')
    return serialized


def create_surface_messages(
    surface_id: str,
    *,
    data: dict[str, typing.Any],
    components: list[dict[str, typing.Any]],
) -> list[dict[str, typing.Any]]:
    return [
        {
            'version': A2UI_MESSAGE_VERSION,
            'createSurface': {
                'surfaceId': surface_id,
                'catalogId': A2UI_CATALOG_ID,
            },
        },
        {
            'version': A2UI_MESSAGE_VERSION,
            'updateDataModel': {
                'surfaceId': surface_id,
                'path': '/',
                'value': data,
            },
        },
        {
            'version': A2UI_MESSAGE_VERSION,
            'updateComponents': {
                'surfaceId': surface_id,
                'components': components,
            },
        },
    ]


def update_surface_messages(
    surface_id: str,
    *,
    data: dict[str, typing.Any] | None = None,
    components: list[dict[str, typing.Any]] | None = None,
) -> list[dict[str, typing.Any]]:
    messages: list[dict[str, typing.Any]] = []
    if data is not None:
        messages.append(
            {
                'version': A2UI_MESSAGE_VERSION,
                'updateDataModel': {
                    'surfaceId': surface_id,
                    'path': '/',
                    'value': data,
                },
            }
        )
    if components is not None:
        messages.append(
            {
                'version': A2UI_MESSAGE_VERSION,
                'updateComponents': {
                    'surfaceId': surface_id,
                    'components': components,
                },
            }
        )
    if not messages:
        raise ValueError('DingTalk A2UI update requires data or components')
    return messages


def text_card_components() -> list[dict[str, typing.Any]]:
    return [
        {
            'id': 'root',
            'component': 'Column',
            'children': ['content', 'langbot-brand'],
            'gap': 8,
        },
        {
            'id': 'content',
            'component': 'Markdown',
            'content': binding('/content'),
        },
        *brand_components(),
    ]


def create_text_card_messages(surface_id: str, content: str = '') -> list[dict[str, typing.Any]]:
    return create_surface_messages(
        surface_id,
        data={'content': content},
        components=text_card_components(),
    )


def update_text_card_messages(surface_id: str, content: str) -> list[dict[str, typing.Any]]:
    return [
        {
            'version': A2UI_MESSAGE_VERSION,
            'updateDataModel': {
                'surfaceId': surface_id,
                'path': '/content',
                'value': content,
            },
        }
    ]
