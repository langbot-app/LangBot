
from __future__ import annotations

import openai

from . import chatcmpl, modelscopechatcmpl
from .. import requester
from ....core import app

class PPIOChatCompletions(chatcmpl.OpenAIChatCompletions):
    """欧派云 ChatCompletion API 请求器"""

    client: openai.AsyncClient

    requester_cfg: dict

    def __init__(self, ap: app.Application):
        self.ap = ap

        self.requester_cfg = self.ap.provider_cfg.data['requester']['ppio-chat-completions']