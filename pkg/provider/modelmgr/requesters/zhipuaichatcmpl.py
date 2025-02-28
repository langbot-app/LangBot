from __future__ import annotations

import openai

from ....core import app
from . import chatcmpl
from .. import requester


class ZhipuAIChatCompletions(chatcmpl.OpenAIChatCompletions):
    """智谱AI ChatCompletion API 请求器"""

    client: openai.AsyncClient

    requester_cfg: dict

    def __init__(self, ap: app.Application):
        self.ap = ap

        self.requester_cfg = self.ap.provider_cfg.data['requester']['zhipuai-chat-completions']
