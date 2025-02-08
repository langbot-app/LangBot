from __future__ import annotations

import openai

from . import chatcmpl
from .. import requester
from ....core import app


@requester.requester_class("aliyun-chat-completions")
class AliyunChatCompletions(chatcmpl.OpenAIChatCompletions):
    """Aliyun ChatCompletion API 请求器"""

    client: openai.AsyncClient

    requester_cfg: dict

    def __init__(self, ap: app.Application):
        self.ap = ap

        self.requester_cfg = self.ap.provider_cfg.data['requester']['aliyun-chat-completions']
