from __future__ import annotations

import typing

import aiocqhttp


TargetMessage = typing.Union[str, list, dict, aiocqhttp.Message]
OneBotResponse = dict[str, typing.Any] | None
