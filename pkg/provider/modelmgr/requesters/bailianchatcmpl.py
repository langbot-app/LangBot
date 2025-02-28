from __future__ import annotations

import openai

from . import chatcmpl
from .. import requester
from ....core import app


class BailianChatCompletions(chatcmpl.OpenAIChatCompletions):
    """阿里云百炼大模型平台 ChatCompletion API 请求器"""

    client: openai.AsyncClient

    requester_cfg: dict

    def __init__(self, ap: app.Application):
        self.ap = ap

        self.requester_cfg = self.ap.provider_cfg.data['requester']['bailian-chat-completions']
