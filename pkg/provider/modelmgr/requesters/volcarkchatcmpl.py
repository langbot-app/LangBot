from __future__ import annotations

import openai

from . import chatcmpl
from .. import requester
from ....core import app


class VolcArkChatCompletions(chatcmpl.OpenAIChatCompletions):
    """火山方舟大模型平台 ChatCompletion API 请求器"""

    client: openai.AsyncClient

    requester_cfg: dict

    def __init__(self, ap: app.Application):
        self.ap = ap

        self.requester_cfg = self.ap.provider_cfg.data['requester']['volcark-chat-completions']
