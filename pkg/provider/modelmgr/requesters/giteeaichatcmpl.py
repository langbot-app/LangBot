from __future__ import annotations


import typing

from . import ppiochatcmpl


class GiteeAIChatCompletions(ppiochatcmpl.PPIOChatCompletions):
    """Gitee AI ChatCompletions API 请求器"""

    default_config: dict[str, typing.Any] = {
        'base_url': 'https://ai.gitee.com/v1',
        'timeout': 120,
    }
