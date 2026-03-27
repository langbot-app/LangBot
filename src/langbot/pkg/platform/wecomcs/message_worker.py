from __future__ import annotations

import json
import logging

from langbot.libs.wecom_customer_service_api.wecomcsevent import WecomCSEvent

from .state_store import WecomCSStateStore


_logger = logging.getLogger("langbot")


class WecomCSMessageWorker:
    """企业微信客服第二层消息 worker。"""

    def __init__(self, client, state_store: WecomCSStateStore | None = None, *, bot_uuid: str = ''):
        self.client = client
        self.state_store = state_store
        self.bot_uuid = bot_uuid

    async def handle_stream_entry(self, stream_fields: dict) -> bool:
        payload = stream_fields.get('payload')
        if not payload:
            return False
        try:
            message_payload = json.loads(payload)
        except json.JSONDecodeError:
            return False
        _logger.debug(
            f'[wecomcs][message-worker] 收到第二层消息: msgid={message_payload.get("msgid")}, open_kfid={message_payload.get("open_kfid")}, external_userid={message_payload.get("external_userid")}'
        )
        return await self.handle_message(message_payload)

    async def handle_message(self, message_payload: dict) -> bool:
        # 中文注释：第二层只负责把消息 payload 恢复成事件对象，然后复用当前 client 的消息派发逻辑。
        event = WecomCSEvent.from_payload(message_payload)
        if not event:
            return False

        if not event.type or not event.user_id or not event.receiver_id:
            return False

        if self.state_store and self.bot_uuid:
            await self.state_store.mark_message_processing(self.bot_uuid, event.receiver_id, event.message_id)

        try:
            await self.client._handle_message(event)
        except Exception as exc:
            if self.state_store and self.bot_uuid:
                await self.state_store.mark_message_failed(
                    self.bot_uuid,
                    event.receiver_id,
                    event.message_id,
                    stage='message_dispatch',
                    error=str(exc),
                )
            raise

        if self.state_store and self.bot_uuid:
            await self.state_store.mark_message_done(self.bot_uuid, event.receiver_id, event.message_id)
        _logger.debug(f'[wecomcs][message-worker] 第二层消息处理完成: msgid={event.message_id}, open_kfid={event.receiver_id}, external_userid={event.user_id}')
        return True
