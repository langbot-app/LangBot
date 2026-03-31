from __future__ import annotations

import json
import logging
import time
import uuid


_logger = logging.getLogger("langbot")


def _is_valid_timestamp(value) -> bool:
    # Fail closed on coercion ambiguity: only native int is accepted.
    return type(value) is int


def normalize_binding_payload(payload: dict | None) -> dict | None:
    """Normalize conversation binding payload from legacy/new schema to canonical schema."""
    if not isinstance(payload, dict):
        return None

    conversation_id = payload.get("conversation_id")
    if not isinstance(conversation_id, str):
        return None
    normalized_conversation_id = conversation_id.strip()
    if not normalized_conversation_id:
        return None

    created_at = payload.get("created_at")
    last_active_at = payload.get("last_active_at")
    policy_version = payload.get("policy_version")
    if _is_valid_timestamp(created_at) and _is_valid_timestamp(last_active_at) and type(policy_version) is int:
        return {
            "conversation_id": normalized_conversation_id,
            "created_at": created_at,
            "last_active_at": last_active_at,
            "policy_version": policy_version,
        }

    updated_at = payload.get("updated_at")
    if _is_valid_timestamp(updated_at):
        return {
            "conversation_id": normalized_conversation_id,
            "created_at": updated_at,
            "last_active_at": updated_at,
            "policy_version": 1,
        }
    return None


def build_binding_payload(conversation_id: str, now_ts: int, existing_created_at: int | None = None) -> dict:
    """Build canonical binding payload in latest schema."""
    created_at = existing_created_at if _is_valid_timestamp(existing_created_at) else now_ts
    return {
        "conversation_id": conversation_id,
        "created_at": created_at,
        "last_active_at": now_ts,
        "policy_version": 2,
    }


def is_binding_expired(binding: dict, *, now_ts: int, idle_timeout_seconds: int) -> bool:
    """Check whether a normalized binding has exceeded idle timeout."""
    if idle_timeout_seconds <= 0:
        return True

    last_active_at = binding.get("last_active_at") if isinstance(binding, dict) else None
    if not _is_valid_timestamp(last_active_at):
        return True
    return now_ts - last_active_at >= idle_timeout_seconds


class DifyConversationStore:
    """Redis-backed store for Dify conversation bindings."""

    def __init__(
        self,
        redis_mgr,
        idle_timeout_seconds: int = 86400,
        lock_ttl_seconds: int = 10,
        enabled: bool = True,
        ttl_seconds: int | None = None,
    ):
        self.redis_mgr = redis_mgr
        # When both are provided, keep ttl_seconds as compatibility-first alias.
        if ttl_seconds is not None:
            idle_timeout_seconds = ttl_seconds

        self.idle_timeout_seconds = (
            idle_timeout_seconds
            if type(idle_timeout_seconds) is int and idle_timeout_seconds > 0
            else 1
        )
        # Backward-compatible alias for older callsites.
        self.ttl_seconds = self.idle_timeout_seconds
        self.lock_ttl_seconds = (
            lock_ttl_seconds
            if type(lock_ttl_seconds) is int and lock_ttl_seconds > 0
            else 1
        )
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
        return normalize_binding_payload(payload)

    async def _load_binding_payload(self, key: str) -> dict | None:
        if hasattr(self.redis_mgr, "get_json"):
            payload = await self.redis_mgr.get_json(key)
        else:
            raw_payload = await self.redis_mgr.get(key)
            payload = json.loads(raw_payload) if raw_payload else None
        return self._validate_payload(payload)

    async def get_conversation_binding(
        self,
        bot_uuid: str,
        pipeline_uuid: str,
        launcher_type: str,
        launcher_id: str,
    ) -> dict | None:
        if not self.is_available():
            return None

        key = self._conversation_key(bot_uuid, pipeline_uuid, launcher_type, launcher_id)
        try:
            return await self._load_binding_payload(key)
        except Exception as exc:
            _logger.warning("[dify][conversation-store] failed to get conversation binding: %s", exc)
            return None

    async def set_conversation_binding(
        self,
        bot_uuid: str,
        pipeline_uuid: str,
        launcher_type: str,
        launcher_id: str,
        conversation_id: str,
        now_ts: int | None = None,
        created_at: int | None = None,
    ) -> None:
        if not self.is_available():
            return
        if not isinstance(conversation_id, str):
            return

        normalized_conversation_id = conversation_id.strip()
        if not normalized_conversation_id:
            return

        key = self._conversation_key(bot_uuid, pipeline_uuid, launcher_type, launcher_id)
        current_ts = now_ts if _is_valid_timestamp(now_ts) else int(time.time())
        existing_created_at = created_at if _is_valid_timestamp(created_at) else None

        if existing_created_at is None:
            try:
                existing_payload = await self._load_binding_payload(key)
                if (
                    existing_payload is not None
                    and existing_payload["conversation_id"] == normalized_conversation_id
                ):
                    existing_created_at = existing_payload["created_at"]
            except Exception as exc:
                _logger.warning("[dify][conversation-store] failed to load existing conversation binding: %s", exc)

        payload = build_binding_payload(
            conversation_id=normalized_conversation_id,
            now_ts=current_ts,
            existing_created_at=existing_created_at,
        )
        try:
            if hasattr(self.redis_mgr, "set_json"):
                await self.redis_mgr.set_json(key, payload, ex=self.idle_timeout_seconds)
            else:
                await self.redis_mgr.set(
                    key,
                    json.dumps(payload, ensure_ascii=False),
                    ex=self.idle_timeout_seconds,
                )
        except Exception as exc:
            _logger.warning("[dify][conversation-store] failed to set conversation binding: %s", exc)

    async def get_conversation_id(
        self,
        bot_uuid: str,
        pipeline_uuid: str,
        launcher_type: str,
        launcher_id: str,
    ) -> str | None:
        binding = await self.get_conversation_binding(
            bot_uuid,
            pipeline_uuid,
            launcher_type,
            launcher_id,
        )
        if binding is None:
            return None
        return binding["conversation_id"]

    async def set_conversation_id(
        self,
        bot_uuid: str,
        pipeline_uuid: str,
        launcher_type: str,
        launcher_id: str,
        conversation_id: str,
    ):
        await self.set_conversation_binding(
            bot_uuid,
            pipeline_uuid,
            launcher_type,
            launcher_id,
            conversation_id,
        )

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
            if isinstance(current_owner, bytes):
                current_owner = current_owner.decode("utf-8", errors="ignore")
            if current_owner != owner:
                return False
            await self.redis_mgr.delete(key)
            return True
        except Exception as exc:
            _logger.warning("[dify][conversation-store] failed to release lock: %s", exc)
            return False
