from __future__ import annotations

from ...core import app, entities as core_entities
from . import handler
from .handlers import chat, command
from .. import entities
from .. import stage, entities, stagemgr
from ...core import entities as core_entities
from ...config import manager as cfg_mgr


@stage.stage_class("MessageProcessor")
class Processor(stage.PipelineStage):

    cmd_handler: handler.MessageHandler

    chat_handler: handler.MessageHandler

    async def initialize(self):
        self.cmd_handler = command.CommandHandler(self.ap)
        self.chat_handler = chat.ChatMessageHandler(self.ap)

        await self.cmd_handler.initialize()
        await self.chat_handler.initialize()

    async def process(
        self,
        query: core_entities.Query,
        stage_inst_name: str,
    ) -> entities.StageProcessResult:
        """处理
        """
        message_text = str(query.message_chain).strip()

        self.ap.logger.info(f"处理 {query.launcher_type.value}_{query.launcher_id} 的请求({query.query_id}): {message_text}")

        if message_text.startswith('!') or message_text.startswith('！'):
            return self.cmd_handler.handle(query)
        else:
            return self.chat_handler.handle(query)
