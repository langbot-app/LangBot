import pytest

from langbot.pkg.platform.wecomcs.sharding import resolve_process_shard, resolve_pull_shard
from langbot.pkg.platform.wecomcs.state_store import WecomCSStateStore


class FakeRedisManager:
    def __init__(self):
        self.values: dict[str, str] = {}
        self.expirations: dict[str, int | None] = {}

    def is_available(self) -> bool:
        return True

    async def get(self, key: str):
        return self.values.get(key)

    async def set(self, key: str, value: str, ex: int | None = None):
        self.values[key] = value
        self.expirations[key] = ex

    async def delete(self, key: str):
        self.values.pop(key, None)
        self.expirations.pop(key, None)

    async def set_if_not_exists(self, key: str, value: str, ex: int | None = None) -> bool:
        if key in self.values:
            return False
        self.values[key] = value
        self.expirations[key] = ex
        return True


def test_pull_shard_is_stable_for_same_open_kfid():
    shard_a = resolve_pull_shard('bot-1', 'kf-1', 8)
    shard_b = resolve_pull_shard('bot-1', 'kf-1', 8)

    assert shard_a == shard_b
    assert 0 <= shard_a < 8


def test_process_shard_is_stable_for_same_session_key():
    shard_a = resolve_process_shard('bot-1', 'kf-1', 'user-1', 16)
    shard_b = resolve_process_shard('bot-1', 'kf-1', 'user-1', 16)

    assert shard_a == shard_b
    assert 0 <= shard_a < 16


def test_pull_shard_count_must_be_positive():
    with pytest.raises(ValueError):
        resolve_pull_shard('bot-1', 'kf-1', 0)


@pytest.mark.asyncio
async def test_state_store_manages_cursor_lock_and_dedupe():
    redis_mgr = FakeRedisManager()
    store = WecomCSStateStore(redis_mgr)

    assert await store.get_cursor('bot-1', 'kf-1') == ''

    await store.set_cursor('bot-1', 'kf-1', 'cursor-1')
    assert await store.get_cursor('bot-1', 'kf-1') == 'cursor-1'

    assert await store.acquire_pull_lock('bot-1', 'kf-1', 'owner-a', 60) is True
    assert await store.acquire_pull_lock('bot-1', 'kf-1', 'owner-b', 60) is False
    assert await store.release_pull_lock('bot-1', 'kf-1', 'owner-b') is False
    assert await store.release_pull_lock('bot-1', 'kf-1', 'owner-a') is True

    assert await store.mark_message_once('bot-1', 'msg-1', 600) is True
    assert await store.mark_message_once('bot-1', 'msg-1', 600) is False
