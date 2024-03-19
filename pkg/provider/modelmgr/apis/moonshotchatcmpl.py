from __future__ import annotations

from ....core import app

from . import chatcmpl
from .. import api


@api.requester_class("moonshot-chat-completions")
class MoonshotChatCompletions(chatcmpl.OpenAIChatCompletions):
    """Moonshot ChatCompletion API 请求器"""

    def __init__(self, ap: app.Application):
        self.requester_cfg = ap.provider_cfg.data['requester']['moonshot-chat-completions']
        self.ap = ap
