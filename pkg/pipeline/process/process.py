from __future__ import annotations

from ...core import entities as core_entities
from . import handler
from .handlers import chat, command
from .. import entities
from .. import stage


@stage.stage_class('MessageProcessor')
class Processor(stage.PipelineStage):
    """请求实际处理阶段

    通过命令处理器和聊天处理器处理消息。

    改写：
        - resp_messages
    """

    cmd_handler: handler.MessageHandler

    chat_handler: handler.MessageHandler

    async def initialize(self, pipeline_config: dict):
        self.cmd_handler = command.CommandHandler(self.ap)
        self.chat_handler = chat.ChatMessageHandler(self.ap)

        await self.cmd_handler.initialize()
        await self.chat_handler.initialize()

    async def process(
        self,
        query: core_entities.Query,
        stage_inst_name: str,
    ) -> entities.StageProcessResult:
        """处理"""
        message_text = str(query.message_chain).strip()

        self.ap.logger.info(
            f'处理 {query.launcher_type.value}_{query.launcher_id} 的请求({query.query_id}): {message_text}'
        )

        async def generator():
            cmd_prefix = self.ap.instance_config.data['command']['prefix']

            if any(message_text.startswith(prefix) for prefix in cmd_prefix):
                async for result in self.cmd_handler.handle(query):
                    yield result
            else:
                async for result in self.chat_handler.handle(query):
                    yield result

        return generator()
