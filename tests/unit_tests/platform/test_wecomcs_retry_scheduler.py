import pytest

from langbot.pkg.platform.wecomcs.retry_scheduler import WecomCSRetryScheduler


class FakeRedisManager:
    def __init__(self):
        self.zset: dict[str, float] = {}
        self.stream_entries: list[tuple[str, dict[str, str]]] = []

    async def zadd(self, key: str, mapping: dict[str, float]):
        self.zset.update(mapping)
        return 1

    async def zrangebyscore(self, key: str, min_score: float, max_score: float):
        return [member for member, score in self.zset.items() if min_score <= score <= max_score]

    async def zrem(self, key: str, member: str):
        self.zset.pop(member, None)
        return 1

    async def xadd(self, stream: str, fields: dict[str, str], maxlen: int | None = None):
        self.stream_entries.append((stream, fields))
        return '1-0'


@pytest.mark.asyncio
async def test_retry_scheduler_schedules_and_replays_job():
    redis_mgr = FakeRedisManager()
    scheduler = WecomCSRetryScheduler(redis_mgr, retry_backoff_seconds=[15, 30], retry_max_attempts=3)

    scheduled = await scheduler.schedule_retry('wecomcs:pull-trigger:0', {'bot_uuid': 'bot-1'}, retry_count=0, error='boom')

    assert scheduled is True
    assert len(redis_mgr.zset) == 1

    replayed = await scheduler.replay_due_jobs(now_ts=9999999999)

    assert replayed == 1
    assert redis_mgr.stream_entries == [
        (
            'wecomcs:pull-trigger:0',
            {'bot_uuid': 'bot-1', 'retry_count': '1', 'last_error': 'boom'},
        )
    ]
    assert redis_mgr.zset == {}


@pytest.mark.asyncio
async def test_retry_scheduler_stops_after_max_attempts():
    redis_mgr = FakeRedisManager()
    scheduler = WecomCSRetryScheduler(redis_mgr, retry_backoff_seconds=[15], retry_max_attempts=2)

    assert await scheduler.schedule_retry('stream-a', {'foo': 'bar'}, retry_count=0) is True
    assert await scheduler.schedule_retry('stream-a', {'foo': 'bar'}, retry_count=1) is True
    assert await scheduler.schedule_retry('stream-a', {'foo': 'bar'}, retry_count=2) is False
