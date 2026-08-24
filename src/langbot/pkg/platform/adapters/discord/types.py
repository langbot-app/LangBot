from __future__ import annotations

import typing

import pydantic


class DiscordAdapterConfig(pydantic.BaseModel):
    client_id: str
    token: str
    guild_id: typing.Optional[str] = None
    debug_channel_id: typing.Optional[str] = None
