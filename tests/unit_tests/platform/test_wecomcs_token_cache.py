import time

import pytest

from langbot.pkg.platform.wecomcs.token_cache import WecomCSTokenCache


class FakeRedisManager:
    def __init__(self, enabled: bool = True):
        self.enabled = enabled
        self.values: dict[str, dict] = {}
        self.expirations: dict[str, int | None] = {}
        self.deleted_keys: list[str] = []

    def is_available(self) -> bool:
        return self.enabled

    async def get_json(self, key: str):
        return self.values.get(key)

    async def set_json(self, key: str, value: dict, ex: int | None = None):
        self.values[key] = value
        self.expirations[key] = ex

    async def delete(self, key: str):
        self.deleted_keys.append(key)
        self.values.pop(key, None)
        self.expirations.pop(key, None)


@pytest.mark.asyncio
async def test_token_cache_stores_payload_in_redis_with_skew_ttl():
    redis_mgr = FakeRedisManager()
    cache = WecomCSTokenCache(corpid='corp-1', redis_mgr=redis_mgr, refresh_skew_seconds=300)
    fetch_count = 0

    async def fake_fetcher():
        nonlocal fetch_count
        fetch_count += 1
        # 中文注释：模拟企业微信返回 token 与 expires_in，验证 Redis TTL 会扣掉安全缓冲时间。
        return {
            'access_token': 'token-1',
            'expires_in': 7200,
        }

    token = await cache.get_or_refresh(fake_fetcher)

    assert token == 'token-1'
    assert fetch_count == 1
    assert redis_mgr.values['wecomcs:access_token:corp-1']['access_token'] == 'token-1'
    assert redis_mgr.expirations['wecomcs:access_token:corp-1'] == 6900


@pytest.mark.asyncio
async def test_token_cache_reuses_cached_value_without_refetch():
    redis_mgr = FakeRedisManager()
    cache = WecomCSTokenCache(corpid='corp-2', redis_mgr=redis_mgr, refresh_skew_seconds=300)
    fetch_count = 0

    async def fake_fetcher():
        nonlocal fetch_count
        fetch_count += 1
        return {
            'access_token': 'token-2',
            'expires_in': 7200,
        }

    first_token = await cache.get_or_refresh(fake_fetcher)
    second_token = await cache.get_or_refresh(fake_fetcher)

    assert first_token == 'token-2'
    assert second_token == 'token-2'
    assert fetch_count == 1


@pytest.mark.asyncio
async def test_token_cache_invalidate_clears_redis_and_refetches():
    redis_mgr = FakeRedisManager()
    cache = WecomCSTokenCache(corpid='corp-3', redis_mgr=redis_mgr, refresh_skew_seconds=300)
    fetch_count = 0

    async def fake_fetcher():
        nonlocal fetch_count
        fetch_count += 1
        return {
            'access_token': f'token-{fetch_count}',
            'expires_in': 7200,
        }

    first_token = await cache.get_or_refresh(fake_fetcher)
    await cache.invalidate()
    second_token = await cache.get_or_refresh(fake_fetcher)

    assert first_token == 'token-1'
    assert second_token == 'token-2'
    assert redis_mgr.deleted_keys == ['wecomcs:access_token:corp-3']


@pytest.mark.asyncio
async def test_token_cache_falls_back_to_local_memory_when_redis_disabled():
    redis_mgr = FakeRedisManager(enabled=False)
    cache = WecomCSTokenCache(corpid='corp-4', redis_mgr=redis_mgr, refresh_skew_seconds=300)

    async def fake_fetcher():
        return {
            'access_token': 'memory-token',
            'expires_in': 7200,
        }

    token = await cache.get_or_refresh(fake_fetcher)
    cached_token = await cache.get_cached_token()

    assert token == 'memory-token'
    assert cached_token == 'memory-token'
    assert redis_mgr.values == {}


@pytest.mark.asyncio
async def test_token_cache_ignores_expired_payload():
    redis_mgr = FakeRedisManager()
    redis_mgr.values['wecomcs:access_token:corp-5'] = {
        'access_token': 'expired-token',
        'expires_at': int(time.time()) - 1,
    }
    cache = WecomCSTokenCache(corpid='corp-5', redis_mgr=redis_mgr, refresh_skew_seconds=300)

    async def fake_fetcher():
        return {
            'access_token': 'fresh-token',
            'expires_in': 7200,
        }

    token = await cache.get_or_refresh(fake_fetcher)

    assert token == 'fresh-token'


@pytest.mark.asyncio
async def test_token_cache_isolated_by_secret_fingerprint():
    redis_mgr = FakeRedisManager()
    cache_a = WecomCSTokenCache(corpid='corp-6', redis_mgr=redis_mgr, refresh_skew_seconds=300, secret_fingerprint='secret-a')
    cache_b = WecomCSTokenCache(corpid='corp-6', redis_mgr=redis_mgr, refresh_skew_seconds=300, secret_fingerprint='secret-b')

    async def fake_fetcher_a():
        return {
            'access_token': 'token-a',
            'expires_in': 7200,
        }

    async def fake_fetcher_b():
        return {
            'access_token': 'token-b',
            'expires_in': 7200,
        }

    token_a = await cache_a.get_or_refresh(fake_fetcher_a)
    token_b = await cache_b.get_or_refresh(fake_fetcher_b)

    assert token_a == 'token-a'
    assert token_b == 'token-b'
    assert sorted(redis_mgr.values.keys()) == [
        'wecomcs:access_token:corp-6:secret-a',
        'wecomcs:access_token:corp-6:secret-b',
    ]
