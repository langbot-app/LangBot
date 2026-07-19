"""Telegram platform-specific type definitions."""

from __future__ import annotations

from enum import Enum


class TelegramChatType(str, Enum):
    """Telegram chat type."""
    PRIVATE = "private"
    GROUP = "group"
    SUPERGROUP = "supergroup"
    CHANNEL = "channel"
