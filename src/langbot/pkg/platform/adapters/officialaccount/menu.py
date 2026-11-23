"""Translate LangBot's custom menu model to and from WeChat menu payloads.

The menu is stored in the bot's adapter config under ``custom_menu``::

    {"buttons": [
        {"id": "a1", "name": "Website", "type": "view", "url": "https://..."},
        {"id": "a2", "name": "Hours", "type": "reply", "text": "9:00-18:00"},
        {"id": "a3", "name": "Ask AI", "type": "ai", "text": "Introduce your products"},
        {"id": "a4", "name": "Orders", "type": "event", "key": "ORDER"},
        {"id": "a5", "name": "App", "type": "miniprogram", "appid": "wx..", "pagepath": "pages/index", "url": "https://..."},
        {"id": "a6", "name": "More", "type": "group", "sub_buttons": [...]},
    ]}

``reply`` and ``ai`` buttons become WeChat ``click`` buttons whose key points
back to the stored button, so the text never has to fit WeChat's 128-byte key.
"""

from __future__ import annotations

import re
import typing

CONFIG_KEY = 'custom_menu'
REPLY_KEY_PREFIX = 'lb:r:'
AI_KEY_PREFIX = 'lb:a:'
RESERVED_KEY_PREFIX = 'lb:'

MAX_TOP_BUTTONS = 3
MAX_SUB_BUTTONS = 5
MAX_TOP_NAME_BYTES = 16
MAX_SUB_NAME_BYTES = 60
MAX_KEY_BYTES = 128
MAX_URL_BYTES = 1024
MAX_TEXT_CHARS = 2000

ACTION_TYPES = ('view', 'miniprogram', 'reply', 'ai', 'event')
_ID_PATTERN = re.compile(r'^[A-Za-z0-9_-]{1,32}$')


class MenuValidationError(ValueError):
    """The stored menu cannot be published; ``path`` names the offending button."""

    def __init__(self, message: str, path: str = ''):
        self.path = path
        super().__init__(f'{path}: {message}' if path else message)


def _byte_len(value: str) -> int:
    return len(value.encode('utf-8'))


def _text(button: dict, field: str) -> str:
    value = button.get(field)
    return value.strip() if isinstance(value, str) else ''


def _check_url(url: str, path: str, field: str = 'url') -> None:
    if not re.match(r'^https?://', url, re.IGNORECASE):
        raise MenuValidationError(f'{field} must start with http:// or https://', path)
    if _byte_len(url) > MAX_URL_BYTES:
        raise MenuValidationError(f'{field} must not exceed {MAX_URL_BYTES} bytes', path)


def _action_to_wechat(button: dict, path: str) -> dict[str, typing.Any]:
    button_id = _text(button, 'id')
    button_type = button.get('type')
    name = _text(button, 'name')
    if button_type == 'view':
        url = _text(button, 'url')
        _check_url(url, path)
        return {'type': 'view', 'name': name, 'url': url}
    if button_type == 'miniprogram':
        appid = _text(button, 'appid')
        pagepath = _text(button, 'pagepath')
        url = _text(button, 'url')
        if not appid or not pagepath:
            raise MenuValidationError('appid and pagepath are required', path)
        # WeChat opens this URL on clients that cannot run the mini program.
        _check_url(url, path, 'url (fallback page)')
        return {'type': 'miniprogram', 'name': name, 'url': url, 'appid': appid, 'pagepath': pagepath}
    if button_type in ('reply', 'ai'):
        text = _text(button, 'text')
        if not text:
            raise MenuValidationError('text is required', path)
        if len(text) > MAX_TEXT_CHARS:
            raise MenuValidationError(f'text must not exceed {MAX_TEXT_CHARS} characters', path)
        if not _ID_PATTERN.match(button_id):
            raise MenuValidationError('id must be 1-32 letters, digits, "_" or "-"', path)
        prefix = REPLY_KEY_PREFIX if button_type == 'reply' else AI_KEY_PREFIX
        return {'type': 'click', 'name': name, 'key': prefix + button_id}
    if button_type == 'event':
        key = _text(button, 'key')
        if not key:
            raise MenuValidationError('key is required', path)
        if key.startswith(RESERVED_KEY_PREFIX):
            raise MenuValidationError(f'key must not start with "{RESERVED_KEY_PREFIX}"', path)
        if _byte_len(key) > MAX_KEY_BYTES:
            raise MenuValidationError(f'key must not exceed {MAX_KEY_BYTES} bytes', path)
        return {'type': 'click', 'name': name, 'key': key}
    raise MenuValidationError(f'unsupported button type: {button_type!r}', path)


def to_wechat(menu: typing.Any) -> dict[str, typing.Any]:
    """Validate a stored menu and build the ``menu/create`` request body."""
    buttons = menu.get('buttons') if isinstance(menu, dict) else None
    if not isinstance(buttons, list) or not buttons:
        raise MenuValidationError('the menu needs at least one button')
    if len(buttons) > MAX_TOP_BUTTONS:
        raise MenuValidationError(f'at most {MAX_TOP_BUTTONS} top-level buttons are allowed')

    result = []
    seen_ids: set[str] = set()

    def check_common(button: typing.Any, path: str, max_name_bytes: int) -> None:
        if not isinstance(button, dict):
            raise MenuValidationError('button must be an object', path)
        name = _text(button, 'name')
        if not name:
            raise MenuValidationError('name is required', path)
        if _byte_len(name) > max_name_bytes:
            raise MenuValidationError(f'name must not exceed {max_name_bytes} bytes', path)
        button_id = _text(button, 'id')
        if button_id:
            if button_id in seen_ids:
                raise MenuValidationError(f'duplicate button id {button_id!r}', path)
            seen_ids.add(button_id)

    for index, button in enumerate(buttons):
        path = f'buttons[{index}]'
        check_common(button, path, MAX_TOP_NAME_BYTES)
        if button.get('type') == 'group':
            sub_buttons = button.get('sub_buttons')
            if not isinstance(sub_buttons, list) or not sub_buttons:
                raise MenuValidationError('a group needs at least one sub button', path)
            if len(sub_buttons) > MAX_SUB_BUTTONS:
                raise MenuValidationError(f'at most {MAX_SUB_BUTTONS} sub buttons are allowed', path)
            subs = []
            for sub_index, sub in enumerate(sub_buttons):
                sub_path = f'{path}.sub_buttons[{sub_index}]'
                check_common(sub, sub_path, MAX_SUB_NAME_BYTES)
                subs.append(_action_to_wechat(sub, sub_path))
            result.append({'name': _text(button, 'name'), 'sub_button': subs})
        else:
            result.append(_action_to_wechat(button, path))
    return {'button': result}


def iter_action_buttons(menu: typing.Any) -> typing.Iterator[dict]:
    buttons = menu.get('buttons') if isinstance(menu, dict) else None
    for button in buttons if isinstance(buttons, list) else []:
        if not isinstance(button, dict):
            continue
        if button.get('type') == 'group':
            for sub in button.get('sub_buttons') or []:
                if isinstance(sub, dict):
                    yield sub
        else:
            yield button


def resolve_click(menu: typing.Any, event_key: str | None) -> tuple[str, str] | None:
    """Map a click ``EventKey`` to ``('reply' | 'ai', text)`` for LangBot-managed buttons."""
    if not event_key:
        return None
    if event_key.startswith(REPLY_KEY_PREFIX):
        button_type, button_id = 'reply', event_key[len(REPLY_KEY_PREFIX) :]
    elif event_key.startswith(AI_KEY_PREFIX):
        button_type, button_id = 'ai', event_key[len(AI_KEY_PREFIX) :]
    else:
        return None
    for button in iter_action_buttons(menu):
        if button.get('type') == button_type and button.get('id') == button_id:
            text = _text(button, 'text')
            return (button_type, text) if text else None
    return None


def from_selfmenu(info: dict[str, typing.Any], new_id: typing.Callable[[], str]) -> tuple[dict, list[str]]:
    """Convert ``get_current_selfmenu_info`` into the stored model.

    Web-console button types without a LangBot equivalent (news, images, voice,
    video) are kept as ``unsupported`` placeholders and reported as warnings so
    the user can replace them before publishing.
    """
    warnings: list[str] = []
    selfmenu = info.get('selfmenu_info') or {}

    def convert(button: dict, path: str) -> dict[str, typing.Any]:
        name = str(button.get('name') or '')
        button_type = button.get('type')
        converted: dict[str, typing.Any] = {'id': new_id(), 'name': name}
        if button_type == 'view':
            converted.update(type='view', url=button.get('url') or '')
        elif button_type == 'text':
            converted.update(type='reply', text=button.get('value') or '')
        elif button_type == 'click':
            key = str(button.get('key') or '')
            converted.update(type='event', key=key)
            if key.startswith(RESERVED_KEY_PREFIX):
                # Published by LangBot earlier; the button text lives in the saved config, not in WeChat.
                warnings.append(f'{path}: LangBot button key {key} needs its text re-entered')
        elif button_type == 'miniprogram':
            converted.update(
                type='miniprogram',
                appid=button.get('appid') or '',
                pagepath=button.get('pagepath') or '',
                url=button.get('url') or '',
            )
        else:
            converted.update(type='unsupported', original_type=str(button_type or ''))
            warnings.append(f'{path}: button type {button_type} is not supported')
        return converted

    buttons = []
    for index, button in enumerate(selfmenu.get('button') or []):
        if not isinstance(button, dict):
            continue
        path = f'buttons[{index}]'
        sub = button.get('sub_button')
        sub_list = sub.get('list') if isinstance(sub, dict) else sub
        if sub_list:
            buttons.append(
                {
                    'id': new_id(),
                    'name': str(button.get('name') or ''),
                    'type': 'group',
                    'sub_buttons': [
                        convert(item, f'{path}.sub_buttons[{sub_index}]')
                        for sub_index, item in enumerate(sub_list)
                        if isinstance(item, dict)
                    ],
                }
            )
        else:
            buttons.append(convert(button, path))
    return {'buttons': buttons}, warnings
