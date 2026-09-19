from __future__ import annotations

import pydantic

ADAPTER_NAME = 'qqofficial-omni'


class QQOfficialAdapterConfig(pydantic.BaseModel):
    appid: str
    secret: str
    token: str
    enable_webhook: bool = False
    enable_stream_reply: bool = False
