from __future__ import annotations

from ....core import app

from . import chatcmpl
from .. import api


@api.requester_class("deepseek-chat-completions")
class DeepseekChatCompletions(chatcmpl.OpenAIChatCompletions):
    """Deepseek ChatCompletion API 请求器"""

    def __init__(self, ap: app.Application):
        self.requester_cfg = ap.provider_cfg.data['requester']['deepseek-chat-completions']
        self.ap = ap