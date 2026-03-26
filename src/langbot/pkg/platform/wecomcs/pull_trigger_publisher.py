from __future__ import annotations

import logging
import xml.etree.ElementTree as ET

from ...cache.redis_mgr import RedisManager
from .sharding import resolve_pull_shard


_logger = logging.getLogger("langbot")


class WecomCSPullTriggerPublisher:
    """企业微信客服 pull-trigger 发布器。"""

    def __init__(self, redis_mgr: RedisManager, shard_count: int):
        self.redis_mgr = redis_mgr
        self.shard_count = shard_count

    async def publish_from_xml(self, bot_uuid: str, xml_msg: str, webhook_received_at: int | None = None) -> tuple[str, dict[str, str]]:
        if isinstance(xml_msg, bytes):
            xml_msg = xml_msg.decode('utf-8')

        root = ET.fromstring(xml_msg)
        callback_token = root.findtext('Token') or ''
        open_kfid = root.findtext('OpenKfId') or ''
        if not callback_token or not open_kfid:
            raise ValueError('Token and OpenKfId are required in callback XML')

        shard = resolve_pull_shard(bot_uuid, open_kfid, self.shard_count)
        stream_name = f'wecomcs:pull-trigger:{shard}'
        payload = {
            'job_type': 'pull_trigger',
            'bot_uuid': bot_uuid,
            'open_kfid': open_kfid,
            'callback_token': callback_token,
            'webhook_received_at': str(int(webhook_received_at or 0)),
        }
        await self.redis_mgr.xadd(stream_name, payload)
        _logger.debug(f'[wecomcs][pull-trigger-publisher] 发布pull-trigger: bot_uuid={bot_uuid}, open_kfid={open_kfid}, shard={shard}, stream={stream_name}')
        return stream_name, payload
