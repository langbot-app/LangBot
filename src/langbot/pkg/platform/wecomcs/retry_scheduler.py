from __future__ import annotations

import json
import logging
import time
import uuid

from ...cache.redis_mgr import RedisManager


_logger = logging.getLogger("langbot")


class WecomCSRetryScheduler:
    """企业微信客服简化版延迟重试调度器。"""

    def __init__(
        self,
        redis_mgr: RedisManager,
        *,
        retry_zset_key: str = 'wecomcs:retry',
        retry_backoff_seconds: list[int] | None = None,
        retry_max_attempts: int = 3,
    ):
        self.redis_mgr = redis_mgr
        self.retry_zset_key = retry_zset_key
        self.retry_backoff_seconds = retry_backoff_seconds or [15, 30, 45]
        self.retry_max_attempts = retry_max_attempts

    @staticmethod
    def _normalize_stream_fields(stream_fields: dict[str, str]) -> dict[str, str]:
        # 中文注释：Redis Stream 字段最终都会按字符串保存，这里提前规范化，避免重试回投时类型漂移。
        return {str(key): '' if value is None else str(value) for key, value in dict(stream_fields).items()}

    async def schedule_retry(self, target_stream: str, stream_fields: dict[str, str], retry_count: int = 0, error: str = '') -> bool:
        next_retry_count = retry_count + 1
        if next_retry_count > self.retry_max_attempts:
            return False

        delay_index = min(next_retry_count - 1, len(self.retry_backoff_seconds) - 1)
        delay_seconds = self.retry_backoff_seconds[delay_index]
        retry_at = int(time.time()) + delay_seconds
        payload = {
            'retry_id': str(uuid.uuid4()),
            'target_stream': target_stream,
            'stream_fields': self._normalize_stream_fields(stream_fields),
            'retry_count': next_retry_count,
            'error': error,
        }
        await self.redis_mgr.zadd(self.retry_zset_key, {json.dumps(payload, ensure_ascii=False): retry_at})
        _logger.debug(f'[wecomcs][retry] 安排重试: target_stream={target_stream}, retry_count={next_retry_count}, retry_at={retry_at}, error={error}')
        return True

    async def poll_due_jobs(self, now_ts: int | None = None) -> list[dict]:
        now_ts = int(now_ts or time.time())
        members = await self.redis_mgr.zrangebyscore(self.retry_zset_key, 0, now_ts)
        jobs = []
        for member in members:
            try:
                jobs.append({'member': member, 'payload': json.loads(member)})
            except json.JSONDecodeError:
                await self.redis_mgr.zrem(self.retry_zset_key, member)
        return jobs

    async def replay_due_jobs(self, now_ts: int | None = None) -> int:
        jobs = await self.poll_due_jobs(now_ts=now_ts)
        replayed = 0
        for job in jobs:
            payload = job['payload']
            replay_fields = self._normalize_stream_fields(payload['stream_fields'])
            replay_fields['retry_count'] = str(payload.get('retry_count', 0))
            if payload.get('error'):
                replay_fields['last_error'] = str(payload['error'])
            await self.redis_mgr.xadd(payload['target_stream'], replay_fields)
            await self.redis_mgr.zrem(self.retry_zset_key, job['member'])
            _logger.debug(f'[wecomcs][retry] 回投重试任务: target_stream={payload["target_stream"]}, retry_count={payload.get("retry_count")}, error={payload.get("error", "")}')
            replayed += 1
        return replayed
