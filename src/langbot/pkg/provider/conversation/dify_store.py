from __future__ import annotations

import json
import logging
import time
import uuid


_logger = logging.getLogger("langbot")


class DifyConversationStore:
    """Redis-backed store for Dify conversation bindings."""

    def __init__(
        self,
        redis_mgr,
        ttl_seconds: int = 86400,
        lock_ttl_seconds: int = 10,
        enabled: bool = True,
    ):
        self.redis_mgr = redis_mgr
        self.ttl_seconds = ttl_seconds
        self.lock_ttl_seconds = lock_ttl_seconds
        self.enabled = enabled

    def is_available(self) -> bool:
        return (
            self.enabled
            and self.redis_mgr is not None
            and hasattr(self.redis_mgr, "is_available")
            and self.redis_mgr.is_available()
        )

    def _conversation_key(self, bot_uuid: str, pipeline_uuid: str, launcher_type: str, launcher_id: str) -> str:
        return f"dify:conversation:{bot_uuid}:{pipeline_uuid}:{launcher_type}:{launcher_id}"

    def _lock_key(self, bot_uuid: str, pipeline_uuid: str, launcher_type: str, launcher_id: str) -> str:
        return f"dify:conversation_lock:{bot_uuid}:{pipeline_uuid}:{launcher_type}:{launcher_id}"

    @staticmethod
    def _validate_payload(payload: dict | None) -> dict | None:
        if not isinstance(payload, dict):
            return None

        conversation_id = payload.get("conversation_id")
        updated_at = payload.get("updated_at")
        if not isinstance(conversation_id, str) or not conversation_id:
            return None
        if not isinstance(updated_at, int):
            return None

        return payload

    async def get_conversation_id(
        self,
        bot_uuid: str,
        pipeline_uuid: str,
        launcher_type: str,
        launcher_id: str,
    ) -> str | None:
        if not self.is_available():
            return None

        key = self._conversation_key(bot_uuid, pipeline_uuid, launcher_type, launcher_id)
        try:
            if hasattr(self.redis_mgr, "get_json"):
                payload = await self.redis_mgr.get_json(key)
            else:
                raw_payload = await self.redis_mgr.get(key)
                payload = json.loads(raw_payload) if raw_payload else None
            payload = self._validate_payload(payload)
            if payload is None:
                return None
            return payload["conversation_id"]
        except Exception as exc:
            _logger.warning("[dify][conversation-store] failed to get conversation id: %s", exc)
            return None

    async def set_conversation_id(
        self,
        bot_uuid: str,
        pipeline_uuid: str,
        launcher_type: str,
        launcher_id: str,
        conversation_id: str,
    ):
        if not self.is_available():
            return
        if not isinstance(conversation_id, str) or not conversation_id.strip():
            return

        key = self._conversation_key(bot_uuid, pipeline_uuid, launcher_type, launcher_id)
        payload = {
            "conversation_id": conversation_id,
            "updated_at": int(time.time()),
        }
        try:
            if hasattr(self.redis_mgr, "set_json"):
                await self.redis_mgr.set_json(key, payload, ex=self.ttl_seconds)
            else:
                await self.redis_mgr.set(key, json.dumps(payload, ensure_ascii=False), ex=self.ttl_seconds)
        except Exception as exc:
            _logger.warning("[dify][conversation-store] failed to set conversation id: %s", exc)

    async def delete_conversation_id(
        self,
        bot_uuid: str,
        pipeline_uuid: str,
        launcher_type: str,
        launcher_id: str,
    ):
        if not self.is_available():
            return

        key = self._conversation_key(bot_uuid, pipeline_uuid, launcher_type, launcher_id)
        try:
            await self.redis_mgr.delete(key)
        except Exception as exc:
            _logger.warning("[dify][conversation-store] failed to delete conversation id: %s", exc)

    async def acquire_lock(
        self,
        bot_uuid: str,
        pipeline_uuid: str,
        launcher_type: str,
        launcher_id: str,
    ) -> str | None:
        if not self.is_available():
            return None

        owner = uuid.uuid4().hex
        key = self._lock_key(bot_uuid, pipeline_uuid, launcher_type, launcher_id)
        try:
            acquired = await self.redis_mgr.set_if_not_exists(key, owner, ex=self.lock_ttl_seconds)
        except Exception as exc:
            _logger.warning("[dify][conversation-store] failed to acquire lock: %s", exc)
            return None

        if acquired:
            return owner
        return None

    async def release_lock(
        self,
        bot_uuid: str,
        pipeline_uuid: str,
        launcher_type: str,
        launcher_id: str,
        owner: str,
    ) -> bool:
        if not self.is_available() or not owner:
            return False

        key = self._lock_key(bot_uuid, pipeline_uuid, launcher_type, launcher_id)
        try:
            redis_client = getattr(self.redis_mgr, "client", None)
            if redis_client is not None and hasattr(redis_client, "eval"):
                eval_key = self.redis_mgr.build_key(key) if hasattr(self.redis_mgr, "build_key") else key
                lua_script = (
                    "if redis.call('get', KEYS[1]) == ARGV[1] "
                    "then return redis.call('del', KEYS[1]) "
                    "else return 0 end"
                )
                deleted = await redis_client.eval(lua_script, 1, eval_key, owner)
                return bool(deleted)

            current_owner = await self.redis_mgr.get(key)
            if current_owner != owner:
                return False
            await self.redis_mgr.delete(key)
            return True
        except Exception as exc:
            _logger.warning("[dify][conversation-store] failed to release lock: %s", exc)
            return False
