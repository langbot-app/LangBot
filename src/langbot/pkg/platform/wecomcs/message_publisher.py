from __future__ import annotations

import json
import logging

from ...cache.redis_mgr import RedisManager
from .sharding import resolve_process_shard
from .stream_keys import build_process_stream_name


_logger = logging.getLogger("langbot")


class WecomCSMessagePublisher:
    """企业微信客服第二层消息发布器。"""

    def __init__(self, redis_mgr: RedisManager, shard_count: int):
        self.redis_mgr = redis_mgr
        self.shard_count = shard_count

    async def publish_message(self, bot_uuid: str, msg_data: dict) -> tuple[str, dict[str, str]]:
        if not self.redis_mgr.is_available():
            raise RuntimeError('Redis is unavailable for message publishing')

        open_kfid = str(msg_data.get('open_kfid', '') or '')
        external_userid = str(msg_data.get('external_userid', '') or '')
        if not open_kfid or not external_userid:
            raise ValueError('open_kfid and external_userid are required')

        shard = resolve_process_shard(bot_uuid, open_kfid, external_userid, self.shard_count)
        stream_name = build_process_stream_name(bot_uuid, shard)
        payload = {
            'job_type': 'message_process',
            'bot_uuid': bot_uuid,
            'open_kfid': open_kfid,
            'external_userid': external_userid,
            'msgid': str(msg_data.get('msgid', '') or ''),
            'msgtype': str(msg_data.get('msgtype', '') or ''),
            'send_time': str(msg_data.get('send_time', '') or ''),
            'payload': json.dumps(msg_data, ensure_ascii=False),
        }
        await self.redis_mgr.xadd(stream_name, payload)
        _logger.debug(f'[wecomcs][message-publisher] 发布message-process: bot_uuid={bot_uuid}, open_kfid={open_kfid}, external_userid={external_userid}, shard={shard}, stream={stream_name}')
        return stream_name, payload
