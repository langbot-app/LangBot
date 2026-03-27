import json

import pytest

from langbot.pkg.provider.conversation.dify_store import DifyConversationStore


class FakeRedisManager:
    def __init__(self, enabled: bool = True, fail_methods: set[str] | None = None):
        self.enabled = enabled
        self.fail_methods = fail_methods or set()
        self.values: dict[str, str] = {}
        self.expirations: dict[str, int | None] = {}
        self.client = _FakeRedisClient(self)

    def is_available(self) -> bool:
        return self.enabled

    def _maybe_raise(self, method_name: str):
        if method_name in self.fail_methods:
            raise RuntimeError(f"forced redis failure in {method_name}")

    async def get(self, key: str):
        self._maybe_raise("get")
        return self.values.get(key)

    async def set(self, key: str, value: str, ex: int | None = None):
        self._maybe_raise("set")
        self.values[key] = value
        self.expirations[key] = ex

    async def delete(self, key: str):
        self._maybe_raise("delete")
        self.values.pop(key, None)
        self.expirations.pop(key, None)

    async def set_if_not_exists(self, key: str, value: str, ex: int | None = None) -> bool:
        self._maybe_raise("set_if_not_exists")
        if key in self.values:
            return False
        self.values[key] = value
        self.expirations[key] = ex
        return True

    async def get_json(self, key: str):
        raw_value = await self.get(key)
        if not raw_value:
            return None
        return json.loads(raw_value)

    async def set_json(self, key: str, value: dict, ex: int | None = None):
        await self.set(key, json.dumps(value, ensure_ascii=False), ex=ex)


class _FakeRedisClient:
    def __init__(self, redis_mgr: FakeRedisManager):
        self.redis_mgr = redis_mgr
        self.switch_owner_once: dict[str, str] = {}

    async def eval(self, script: str, numkeys: int, *keys_and_args):
        del script
        del numkeys
        key = str(keys_and_args[0])
        owner = str(keys_and_args[1])

        if key in self.switch_owner_once:
            self.redis_mgr.values[key] = self.switch_owner_once.pop(key)

        if self.redis_mgr.values.get(key) == owner:
            self.redis_mgr.values.pop(key, None)
            self.redis_mgr.expirations.pop(key, None)
            return 1
        return 0


@pytest.mark.asyncio
async def test_conversation_id_round_trip_and_ttl():
    redis_mgr = FakeRedisManager()
    store = DifyConversationStore(redis_mgr, ttl_seconds=321)

    await store.set_conversation_id("bot-1", "pipe-1", "private", "launcher-1", "conv-1")

    key = "dify:conversation:bot-1:pipe-1:private:launcher-1"
    assert redis_mgr.expirations[key] == 321

    payload = json.loads(redis_mgr.values[key])
    assert payload["conversation_id"] == "conv-1"
    assert isinstance(payload["updated_at"], int)

    assert await store.get_conversation_id("bot-1", "pipe-1", "private", "launcher-1") == "conv-1"


@pytest.mark.asyncio
async def test_invalid_payload_is_ignored():
    redis_mgr = FakeRedisManager()
    store = DifyConversationStore(redis_mgr)

    key = "dify:conversation:bot-1:pipe-1:private:launcher-1"

    redis_mgr.values[key] = "not-json"
    assert await store.get_conversation_id("bot-1", "pipe-1", "private", "launcher-1") is None

    redis_mgr.values[key] = json.dumps({"conversation_id": "conv-1"})
    assert await store.get_conversation_id("bot-1", "pipe-1", "private", "launcher-1") is None

    redis_mgr.values[key] = json.dumps({"conversation_id": "conv-1", "updated_at": "123"})
    assert await store.get_conversation_id("bot-1", "pipe-1", "private", "launcher-1") is None

    redis_mgr.values[key] = json.dumps({"conversation_id": "", "updated_at": 123})
    assert await store.get_conversation_id("bot-1", "pipe-1", "private", "launcher-1") is None


@pytest.mark.asyncio
async def test_delete_behavior():
    redis_mgr = FakeRedisManager()
    store = DifyConversationStore(redis_mgr)

    await store.set_conversation_id("bot-1", "pipe-1", "private", "launcher-1", "conv-1")
    await store.delete_conversation_id("bot-1", "pipe-1", "private", "launcher-1")

    key = "dify:conversation:bot-1:pipe-1:private:launcher-1"
    assert key not in redis_mgr.values
    assert await store.get_conversation_id("bot-1", "pipe-1", "private", "launcher-1") is None


@pytest.mark.asyncio
async def test_blank_conversation_id_is_not_persisted():
    redis_mgr = FakeRedisManager()
    store = DifyConversationStore(redis_mgr)

    await store.set_conversation_id("bot-1", "pipe-1", "private", "launcher-1", "")
    await store.set_conversation_id("bot-1", "pipe-1", "private", "launcher-1", "   ")

    key = "dify:conversation:bot-1:pipe-1:private:launcher-1"
    assert key not in redis_mgr.values
    assert await store.get_conversation_id("bot-1", "pipe-1", "private", "launcher-1") is None


@pytest.mark.asyncio
async def test_graceful_behavior_when_disabled_or_unavailable_or_redis_failures():
    redis_mgr = FakeRedisManager()
    disabled_store = DifyConversationStore(redis_mgr, enabled=False)
    unavailable_store = DifyConversationStore(FakeRedisManager(enabled=False))

    assert disabled_store.is_available() is False
    assert unavailable_store.is_available() is False

    assert await disabled_store.get_conversation_id("b", "p", "t", "l") is None
    await disabled_store.set_conversation_id("b", "p", "t", "l", "c")
    await disabled_store.delete_conversation_id("b", "p", "t", "l")
    assert await disabled_store.acquire_lock("b", "p", "t", "l") is None
    assert await disabled_store.release_lock("b", "p", "t", "l", "owner") is False

    failing_get_store = DifyConversationStore(FakeRedisManager(fail_methods={"get"}))
    assert await failing_get_store.get_conversation_id("b", "p", "t", "l") is None
    assert await failing_get_store.release_lock("b", "p", "t", "l", "owner") is False

    failing_set_store = DifyConversationStore(FakeRedisManager(fail_methods={"set"}))
    await failing_set_store.set_conversation_id("b", "p", "t", "l", "c")

    failing_delete_store = DifyConversationStore(FakeRedisManager(fail_methods={"delete"}))
    await failing_delete_store.delete_conversation_id("b", "p", "t", "l")

    failing_lock_store = DifyConversationStore(FakeRedisManager(fail_methods={"set_if_not_exists"}))
    assert await failing_lock_store.acquire_lock("b", "p", "t", "l") is None


@pytest.mark.asyncio
async def test_lock_acquire_release_owner_and_lock_ttl():
    redis_mgr = FakeRedisManager()
    store = DifyConversationStore(redis_mgr, lock_ttl_seconds=9)

    owner = await store.acquire_lock("bot-1", "pipe-1", "private", "launcher-1")
    assert owner is not None

    lock_key = "dify:conversation_lock:bot-1:pipe-1:private:launcher-1"
    assert redis_mgr.values[lock_key] == owner
    assert redis_mgr.expirations[lock_key] == 9

    second_owner = await store.acquire_lock("bot-1", "pipe-1", "private", "launcher-1")
    assert second_owner is None

    released_by_other = await store.release_lock("bot-1", "pipe-1", "private", "launcher-1", "other-owner")
    assert released_by_other is False
    assert lock_key in redis_mgr.values

    released = await store.release_lock("bot-1", "pipe-1", "private", "launcher-1", owner)
    assert released is True
    assert lock_key not in redis_mgr.values


@pytest.mark.asyncio
async def test_release_lock_does_not_delete_new_owner_lock_on_owner_switch():
    redis_mgr = FakeRedisManager()
    store = DifyConversationStore(redis_mgr)

    lock_key = "dify:conversation_lock:bot-1:pipe-1:private:launcher-1"
    redis_mgr.values[lock_key] = "old-owner"
    redis_mgr.client.switch_owner_once[lock_key] = "new-owner"

    released = await store.release_lock("bot-1", "pipe-1", "private", "launcher-1", "old-owner")

    assert released is False
    assert redis_mgr.values.get(lock_key) == "new-owner"


@pytest.mark.asyncio
async def test_key_boundary_isolation_by_pipeline_and_launcher_dimensions():
    redis_mgr = FakeRedisManager()
    store = DifyConversationStore(redis_mgr)

    await store.set_conversation_id("bot-1", "pipe-1", "private", "launcher-1", "conv-a")
    await store.set_conversation_id("bot-2", "pipe-1", "private", "launcher-1", "conv-e")
    await store.set_conversation_id("bot-1", "pipe-2", "private", "launcher-1", "conv-b")
    await store.set_conversation_id("bot-1", "pipe-1", "group", "launcher-1", "conv-c")
    await store.set_conversation_id("bot-1", "pipe-1", "private", "launcher-2", "conv-d")

    assert await store.get_conversation_id("bot-1", "pipe-1", "private", "launcher-1") == "conv-a"
    assert await store.get_conversation_id("bot-2", "pipe-1", "private", "launcher-1") == "conv-e"
    assert await store.get_conversation_id("bot-1", "pipe-2", "private", "launcher-1") == "conv-b"
    assert await store.get_conversation_id("bot-1", "pipe-1", "group", "launcher-1") == "conv-c"
    assert await store.get_conversation_id("bot-1", "pipe-1", "private", "launcher-2") == "conv-d"

    assert len(redis_mgr.values) == 5
