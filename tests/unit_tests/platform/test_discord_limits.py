from __future__ import annotations

import pytest

from langbot.pkg.platform.sources import discord


def test_discord_base64_decode_is_bounded(monkeypatch):
    monkeypatch.setattr(discord, '_MAX_DISCORD_MEDIA_BYTES', 4)

    with pytest.raises(ValueError, match='exceeds'):
        discord._decode_discord_base64_limited('A' * 12)
