from __future__ import annotations

import json
import logging
from typing import Any

from redis import asyncio as redis_asyncio

if False:  # pragma: no cover
    from ..core import app


_logger = logging.getLogger("langbot")


class RedisManager:
    """Application-level Redis manager."""

    def __init__(self, ap: "app.Application"):
        self.ap = ap
        self.client: redis_asyncio.Redis | None = None
        self.enabled = False
        self.key_prefix = "langbot"

    async def initialize(self):
        redis_config = self.ap.instance_config.data.get("redis", {})
        self.enabled = bool(redis_config.get("enabled", False))
        self.key_prefix = redis_config.get("key_prefix", "langbot")

        if not self.enabled:
            self.ap.logger.info("Redis disabled by config.")
            return

        redis_url = redis_config.get("url", "redis://127.0.0.1:6379/0")
        self.client = redis_asyncio.from_url(redis_url, decode_responses=True)
        await self.client.ping()
        self.ap.logger.info(f"Initialized Redis manager: url={redis_url}")

    def build_key(self, key: str) -> str:
        return f"{self.key_prefix}:{key}"

    def is_available(self) -> bool:
        return self.enabled and self.client is not None

    async def get(self, key: str) -> str | None:
        if not self.is_available():
            return None
        return await self.client.get(self.build_key(key))

    async def set(self, key: str, value: str, ex: int | None = None):
        if not self.is_available():
            return
        await self.client.set(self.build_key(key), value, ex=ex)

    async def delete(self, key: str):
        if not self.is_available():
            return
        await self.client.delete(self.build_key(key))

    async def set_if_not_exists(self, key: str, value: str, ex: int | None = None) -> bool:
        if not self.is_available():
            return False
        return bool(await self.client.set(self.build_key(key), value, ex=ex, nx=True))

    async def xadd(self, stream: str, fields: dict[str, str], maxlen: int | None = None) -> str | None:
        if not self.is_available():
            return None
        if maxlen is None:
            return await self.client.xadd(self.build_key(stream), fields)
        return await self.client.xadd(self.build_key(stream), fields, maxlen=maxlen, approximate=True)

    async def xrange(self, stream: str, min_id: str = '-', max_id: str = '+', count: int | None = None):
        if not self.is_available():
            return []
        return await self.client.xrange(self.build_key(stream), min=min_id, max=max_id, count=count)

    async def xgroup_create(self, stream: str, group: str, id: str = '0', mkstream: bool = True):
        if not self.is_available():
            return
        try:
            await self.client.xgroup_create(self.build_key(stream), group, id=id, mkstream=mkstream)
        except Exception as exc:
            if 'BUSYGROUP' not in str(exc):
                raise

    async def xreadgroup(
        self,
        group: str,
        consumer: str,
        streams: dict[str, str],
        count: int | None = None,
        block_ms: int | None = None,
    ):
        if not self.is_available():
            return []
        mapped_streams = {self.build_key(name): stream_id for name, stream_id in streams.items()}
        return await self.client.xreadgroup(
            groupname=group,
            consumername=consumer,
            streams=mapped_streams,
            count=count,
            block=block_ms,
        )

    async def xack(self, stream: str, group: str, message_id: str):
        if not self.is_available():
            return 0
        return await self.client.xack(self.build_key(stream), group, message_id)

    async def zadd(self, key: str, mapping: dict[str, float]):
        if not self.is_available():
            return 0
        return await self.client.zadd(self.build_key(key), mapping)

    async def zrangebyscore(self, key: str, min_score: float, max_score: float):
        if not self.is_available():
            return []
        return await self.client.zrangebyscore(self.build_key(key), min_score, max_score)

    async def zrem(self, key: str, member: str):
        if not self.is_available():
            return 0
        return await self.client.zrem(self.build_key(key), member)

    async def get_json(self, key: str) -> dict[str, Any] | None:
        raw_value = await self.get(key)
        if not raw_value:
            return None

        try:
            return json.loads(raw_value)
        except json.JSONDecodeError:
            _logger.warning(f"[redis] invalid json payload for key={key}")
            return None

    async def set_json(self, key: str, value: dict[str, Any], ex: int | None = None):
        await self.set(key, json.dumps(value, ensure_ascii=False), ex=ex)

    async def close(self):
        if self.client is None:
            return
        await self.client.aclose()
