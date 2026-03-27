from __future__ import annotations

import json
import logging
import time

from .models import WecomCSMessageState


_logger = logging.getLogger('langbot')


class WecomCSMessageStateStore:
    """Store recent WeCom customer service message states in Redis."""

    ACTIVE_STATUSES = {'queued', 'processing', 'done', 'ignored'}

    def __init__(self, redis_mgr = None, ttl_seconds: int = 604800):
        self.redis_mgr = redis_mgr
        self.ttl_seconds = ttl_seconds

    def is_available(self) -> bool:
        return self.redis_mgr is not None and self.redis_mgr.is_available()

    def _key(self, bot_uuid: str, open_kfid: str, msgid: str) -> str:
        return f'wecomcs:msg:{bot_uuid}:{open_kfid}:{msgid}'

    async def get_state(self, bot_uuid: str, open_kfid: str, msgid: str) -> dict | None:
        if not self.is_available():
            return None
        if hasattr(self.redis_mgr, 'get_json'):
            state = await self.redis_mgr.get_json(self._key(bot_uuid, open_kfid, msgid))
        else:
            raw_value = await self.redis_mgr.get(self._key(bot_uuid, open_kfid, msgid))
            state = json.loads(raw_value) if raw_value else None
        if state:
            _logger.debug(
                f'[wecomcs][message-state] 读取消息状态: bot_uuid={bot_uuid}, open_kfid={open_kfid}, msgid={msgid}, process_status={state.get("process_status")}, reply_status={state.get("reply_status")}'
            )
        return state

    async def save_state(self, state: WecomCSMessageState | dict):
        if not self.is_available():
            return
        payload = state.to_dict() if isinstance(state, WecomCSMessageState) else dict(state)
        if hasattr(self.redis_mgr, 'set_json'):
            await self.redis_mgr.set_json(
                self._key(payload['bot_uuid'], payload['open_kfid'], payload['msgid']),
                payload,
                ex=self.ttl_seconds,
            )
        else:
            await self.redis_mgr.set(
                self._key(payload['bot_uuid'], payload['open_kfid'], payload['msgid']),
                json.dumps(payload, ensure_ascii=False),
                ex=self.ttl_seconds,
            )
        _logger.debug(
            f'[wecomcs][message-state] 保存消息状态: bot_uuid={payload.get("bot_uuid")}, open_kfid={payload.get("open_kfid")}, msgid={payload.get("msgid")}, process_status={payload.get("process_status")}, reply_status={payload.get("reply_status")}'
        )

    async def reserve_for_queue(self, bot_uuid: str, open_kfid: str, msg_data: dict) -> bool:
        if not self.is_available():
            return True

        msgid = str(msg_data.get('msgid', '') or '')
        if not msgid:
            return False

        current = await self.get_state(bot_uuid, open_kfid, msgid)
        if current:
            return False

        now_ts = int(time.time())
        content_preview = ''
        text_data = msg_data.get('text') or {}
        if isinstance(text_data, dict):
            content_preview = str(text_data.get('content', '') or '')[:200]

        next_retry_count = int((current or {}).get('retry_count', 0) or 0)
        if current and current.get('process_status') == 'failed':
            next_retry_count += 1

        state = WecomCSMessageState(
            bot_uuid=bot_uuid,
            open_kfid=open_kfid,
            msgid=msgid,
            external_userid=str(msg_data.get('external_userid', '') or ''),
            msgtype=str(msg_data.get('msgtype', '') or ''),
            send_time=int(msg_data.get('send_time', 0) or 0) or None,
            process_status='queued',
            reply_status=str((current or {}).get('reply_status', 'pending') or 'pending'),
            retry_count=next_retry_count,
            last_error_stage='',
            last_error='',
            first_seen_at=int((current or {}).get('first_seen_at', now_ts) or now_ts),
            queued_at=now_ts,
            processing_at=None,
            done_at=None,
            reply_at=int((current or {}).get('reply_at', 0) or 0) or None,
            failed_at=None,
            updated_at=now_ts,
            content_preview=content_preview or str((current or {}).get('content_preview', '') or ''),
        )
        await self.save_state(state)
        return True

    async def update_status(
        self,
        bot_uuid: str,
        open_kfid: str,
        msgid: str,
        *,
        process_status: str | None = None,
        reply_status: str | None = None,
        last_error_stage: str | None = None,
        last_error: str | None = None,
    ) -> dict | None:
        if not self.is_available():
            return None

        current = await self.get_state(bot_uuid, open_kfid, msgid)
        if current is None:
            return None

        now_ts = int(time.time())
        current['updated_at'] = now_ts
        if process_status:
            current['process_status'] = process_status
            if process_status == 'processing':
                current['processing_at'] = now_ts
            elif process_status == 'done':
                current['done_at'] = now_ts
            elif process_status == 'failed':
                current['failed_at'] = now_ts
        if reply_status:
            current['reply_status'] = reply_status
            if reply_status in {'success', 'failed'}:
                current['reply_at'] = now_ts
        if last_error_stage is not None:
            current['last_error_stage'] = last_error_stage
        if last_error is not None:
            current['last_error'] = last_error

        await self.save_state(current)
        return current
