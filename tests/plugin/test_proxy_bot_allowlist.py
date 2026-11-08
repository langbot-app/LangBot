from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

HANDLER = ROOT / 'src/langbot/pkg/plugin/handler.py'
PERMS = ROOT / 'src/langbot/pkg/api/application/plugin_permissions.py'
CONSTS = ROOT / 'src/langbot/pkg/utils/constants.py'

GUARD = 'bot_uuid != constants.WEBSOCKET_PROXY_BOT_UUID'


def _code(path: Path) -> str:
    """Source with comment-only lines stripped, so prose cannot satisfy a check."""
    return re.sub(r'(?m)^\s*#.*$', '', path.read_text(encoding='utf-8'))


def _action(path: Path, name: str) -> str:
    src = _code(path)
    start = src.index(f'PluginToRuntimeAction.{name}')
    return src[start:]


def test_constant_is_declared():
    assert "WEBSOCKET_PROXY_BOT_UUID = 'websocket-proxy-bot'" in _code(CONSTS)


def test_send_message_lets_the_proxy_bot_through():
    body = _action(HANDLER, 'SEND_MESSAGE')
    assert GUARD in body


def test_get_bot_info_lets_the_proxy_bot_through():
    body = _action(HANDLER, 'GET_BOT_INFO')
    assert GUARD in body


def test_permission_check_skips_the_unknown_bot_lookup():
    assert "if data.get('bot_uuid') and data['bot_uuid'] != constants.WEBSOCKET_PROXY_BOT_UUID:" in _code(PERMS)


def test_allowlist_covers_every_bot_uuid_guard():
    """Only the two bot-scoped lookups may carry it; model lookups must not."""
    src = _code(HANDLER)
    assert src.count(GUARD) == 2
