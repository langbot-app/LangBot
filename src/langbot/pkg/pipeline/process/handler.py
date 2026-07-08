from __future__ import annotations

import abc

from ...core import app
from .. import entities
import langbot_plugin.api.entities.builtin.pipeline.query as pipeline_query
import langbot_plugin.api.entities.builtin.provider.message as provider_message


class MessageHandler(metaclass=abc.ABCMeta):
    ap: app.Application

    def __init__(self, ap: app.Application):
        self.ap = ap

    async def initialize(self):
        pass

    @abc.abstractmethod
    async def handle(
        self,
        query: pipeline_query.Query,
    ) -> entities.StageProcessResult:
        raise NotImplementedError

    def cut_str(self, s: str) -> str:
        """
        Take the first line of the string, up to 20 characters, if there are multiple lines, or more than 20 characters, add an ellipsis
        """
        s0 = s.split('\n')[0]
        if len(s0) > 20 or '\n' in s:
            s0 = s0[:20] + '...'
        return s0

    def format_result_log(
        self,
        result: provider_message.Message | provider_message.MessageChunk,
    ) -> str | None:
        if result.tool_calls:
            tool_names = [tc.function.name for tc in result.tool_calls if tc.function and tc.function.name]
            if tool_names:
                return f'{result.role}: requested tools: {", ".join(tool_names)}'
            return f'{result.role}: requested tool calls'

        content = result.content
        if isinstance(content, str):
            if not content.strip():
                return None

            if result.role == 'tool':
                if content.startswith('err:'):
                    return f'tool error: {self.cut_str(content)}'

            return self.cut_str(result.readable_str())

        if isinstance(content, list) and len(content) == 0:
            return None

        return self.cut_str(result.readable_str())
