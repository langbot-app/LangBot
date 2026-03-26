from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Awaitable, Callable

from ...cache.redis_mgr import RedisManager


_logger = logging.getLogger("langbot")


class WecomCSTokenCache:
    """企业微信客服 access token 缓存。"""

    def __init__(
        self,
        corpid: str,
        redis_mgr: RedisManager | None = None,
        refresh_skew_seconds: int = 300,
        secret_fingerprint: str = '',
    ):
        self.corpid = corpid
        self.redis_mgr = redis_mgr
        self.refresh_skew_seconds = max(0, refresh_skew_seconds)
        # 中文注释：同一个 corpid 下可能存在不同 secret 对应不同 access_token，
        # 这里把 secret 指纹纳入缓存维度，避免 wecomcs / wecom_kf_app 互串 token。
        self.secret_fingerprint = str(secret_fingerprint or '').strip()
        self._token_lock = asyncio.Lock()
        self._local_cache: dict[str, int | str] = {
            "access_token": "",
            "expires_at": 0,
        }

    def _cache_key(self) -> str:
        if self.secret_fingerprint:
            return f"wecomcs:access_token:{self.corpid}:{self.secret_fingerprint}"
        return f"wecomcs:access_token:{self.corpid}"

    def _is_valid_payload(self, payload: dict | None) -> bool:
        # 中文注释：本地和 Redis 都统一按 expires_at 判断，避免只凭是否有字符串误判 token 有效。
        if not payload:
            return False
        access_token = str(payload.get("access_token", "")).strip()
        expires_at = int(payload.get("expires_at", 0) or 0)
        return bool(access_token) and expires_at > int(time.time())

    async def _read_cached_payload(self) -> dict | None:
        if self._is_valid_payload(self._local_cache):
            _logger.debug(f'[wecomcs][token-cache] 本地缓存命中: corpid={self.corpid[:10]}...')
            return dict(self._local_cache)

        if self.redis_mgr and self.redis_mgr.is_available():
            payload = await self.redis_mgr.get_json(self._cache_key())
            if self._is_valid_payload(payload):
                _logger.debug(f'[wecomcs][token-cache] Redis缓存命中: corpid={self.corpid[:10]}...')
                self._local_cache = {
                    "access_token": str(payload["access_token"]),
                    "expires_at": int(payload["expires_at"]),
                }
                return dict(self._local_cache)

        return None

    async def get_cached_token(self) -> str | None:
        payload = await self._read_cached_payload()
        if not payload:
            return None
        return str(payload["access_token"])

    async def get_or_refresh(
        self,
        fetcher: Callable[[], Awaitable[dict]],
        *,
        force_refresh: bool = False,
    ) -> str:
        if not force_refresh:
            cached_token = await self.get_cached_token()
            if cached_token:
                return cached_token

        async with self._token_lock:
            if not force_refresh:
                cached_token = await self.get_cached_token()
                if cached_token:
                    return cached_token

            # 中文注释：fetcher 负责真实请求企业微信接口，缓存层只负责生命周期和存储。
            token_data = await fetcher()
            access_token = str(token_data.get("access_token", "")).strip()
            expires_in = int(token_data.get("expires_in", 7200) or 7200)
            if not access_token:
                raise ValueError("access_token is missing in token_data")

            now = int(time.time())
            expires_at = now + expires_in
            ttl_seconds = max(1, expires_in - self.refresh_skew_seconds)
            payload = {
                "access_token": access_token,
                "expires_at": expires_at,
            }

            _logger.debug(
                f'[wecomcs][token-cache] 刷新token成功: corpid={self.corpid[:10]}..., ttl_seconds={ttl_seconds}, expires_at={expires_at}'
            )
            self._local_cache = payload
            if self.redis_mgr and self.redis_mgr.is_available():
                await self.redis_mgr.set_json(self._cache_key(), payload, ex=ttl_seconds)

            return access_token

    async def invalidate(self):
        _logger.debug(f'[wecomcs][token-cache] 失效token缓存: corpid={self.corpid[:10]}...')
        self._local_cache = {
            "access_token": "",
            "expires_at": 0,
        }
        if self.redis_mgr and self.redis_mgr.is_available():
            await self.redis_mgr.delete(self._cache_key())
