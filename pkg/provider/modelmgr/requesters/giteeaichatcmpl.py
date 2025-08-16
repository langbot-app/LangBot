from __future__ import annotations


import typing

from . import ppiochatcmpl
from .. import requester
from ....core import entities as core_entities
from ... import entities as llm_entities
from ...tools import entities as tools_entities
import re
import openai.types.chat.chat_completion as chat_completion


class GiteeAIChatCompletions(ppiochatcmpl.PPIOChatCompletions):
    """Gitee AI ChatCompletions API 请求器"""

    default_config: dict[str, typing.Any] = {
        'base_url': 'https://ai.gitee.com/v1',
        'timeout': 120,
    }

