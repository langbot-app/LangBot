from __future__ import annotations

from . import handler
from .handlers import chat
from .. import entities
from .. import stage
from ..command_text import command_text_from_chain
import langbot_plugin.api.entities.builtin.pipeline.query as pipeline_query


@stage.stage_class('MessageProcessor')
class Processor(stage.PipelineStage):
    """请求实际处理阶段

    通过命令处理器和聊天处理器处理消息。

    改写：
        - resp_messages
    """

    chat_handler: handler.MessageHandler

    async def initialize(self, pipeline_config: dict):
        self.chat_handler = chat.ChatMessageHandler(self.ap)

        await self.chat_handler.initialize()

    async def process(
        self,
        query: pipeline_query.Query,
        stage_inst_name: str,
    ) -> entities.StageProcessResult:
        """Process"""
        message_text = command_text_from_chain(query.message_chain)

        self.ap.logger.info(
            f'Processing request from {query.launcher_type.value}_{query.launcher_id} ({query.query_id}): {message_text}'
        )

        return self.chat_handler.handle(query)
