from __future__ import annotations

import copy
import json
import time
import uuid
import logging
from datetime import datetime, timezone
from typing import Any
from langbot_plugin.entities.io.errors import ActionCallError
from store.serialization import FENCE_KEY_PREFIX, BindingWrites, serialized_write

logger = logging.getLogger(__name__)

_SUPERSEDE_TAGS = {"correction", "fact-update", "clarification"}


def _installation_scope(_store, _args, _kwargs):
    """Serialization identity for a write that carries no memory-scope identity.

    ``kb_configs`` is one installation-wide map shared by every memory KB, so its
    read-modify-write must stay on the installation scope; keying it by the
    collection id would let two KBs overwrite each other's entry.
    """
    return None


def _default_profile() -> dict[str, Any]:
    return {
        "name": "",
        "traits": [],
        "preferences": [],
        "notes": "",
        "updated_at": "",
        "profile_slots": {
            "traits": {},
            "preferences": {},
        },
        "freeform_traits": [],
        "freeform_preferences": [],
    }


class MemoryStore:
    """Dual-layer memory store.

    L1 (Core Profile): Binary Storage (JSON) - read/write via plugin storage API.
    L2 (Episodic Memory): vector DB - read/write via plugin vector API.
    """

    _PROFILE_FIELDS = ("name", "traits", "preferences", "notes")
    _STRUCTURED_FIELDS = ("traits", "preferences")
    _MAX_PROFILE_CACHE_SIZE = 256
    _MAX_NOTES_LENGTH = 2000
    _MAX_SLOT_HISTORY = 8
    _RECENT_SLOT_CHANGE_DAYS = 30
    _MAX_AUDIT_ENTRIES_PER_SCOPE = 1000
    _MAX_CANDIDATES_PER_SCOPE = 1000
    CANDIDATE_STATUS_PENDING = "pending"
    CANDIDATE_STATUS_ACCEPTED = "accepted"
    CANDIDATE_STATUS_REJECTED = "rejected"
    CANDIDATE_STATUSES = {
        CANDIDATE_STATUS_PENDING,
        CANDIDATE_STATUS_ACCEPTED,
        CANDIDATE_STATUS_REJECTED,
    }
    EPISODE_STATUS_ACTIVE = "active"
    EPISODE_STATUS_SUPERSEDED = "superseded"
    EPISODE_STATUS_ARCHIVED = "archived"
    EPISODE_STATUS_DELETED = "deleted"
    EPISODE_STATUSES = {
        EPISODE_STATUS_ACTIVE,
        EPISODE_STATUS_SUPERSEDED,
        EPISODE_STATUS_ARCHIVED,
        EPISODE_STATUS_DELETED,
    }

    def __init__(
        self,
        plugin: Any,
        max_profile_traits: int = 20,
        max_profile_preferences: int = 10,
    ):
        self.plugin = plugin
        self._writes = BindingWrites()
        # Explicit limits are retained for standalone legacy/store fixtures only.
        # The actual plugin resolves them through SDK task-local get_config().
        self._default_max_profile_traits = max_profile_traits
        self._default_max_profile_preferences = max_profile_preferences
        # Storage is invocation-bound. Never retain profiles or KB configuration
        # on the singleton: identical keys may belong to different installations.

    @staticmethod
    def _preview_text(value: str, max_len: int = 120) -> str:
        text = value.strip().replace("\n", " ")
        if len(text) <= max_len:
            return text
        return f"{text[:max_len]}..."

    @classmethod
    def normalize_episode_status_value(cls, value: Any) -> str:
        status = str(value or "").strip().lower()
        if status in cls.EPISODE_STATUSES:
            return status
        return cls.EPISODE_STATUS_ACTIVE

    @classmethod
    def episode_status_from_metadata(cls, metadata: dict[str, Any]) -> str:
        return cls.normalize_episode_status_value(metadata.get("status", ""))

    @classmethod
    def normalize_episode_statuses(
        cls,
        include_statuses: list[str] | set[str] | tuple[str, ...] | None,
    ) -> set[str]:
        if include_statuses is None:
            return {cls.EPISODE_STATUS_ACTIVE}
        statuses = {
            cls.normalize_episode_status_value(status)
            for status in include_statuses
        }
        return statuses or {cls.EPISODE_STATUS_ACTIVE}

    @classmethod
    def episode_status_included(
        cls,
        metadata: dict[str, Any],
        include_statuses: list[str] | set[str] | tuple[str, ...] | None = None,
    ) -> bool:
        statuses = cls.normalize_episode_statuses(include_statuses)
        return cls.episode_status_from_metadata(metadata) in statuses

    @staticmethod
    def normalize_retrieval_strategy(value: Any) -> str:
        strategy = str(value or "auto").strip().lower()
        if strategy in {"vector", "hybrid", "auto"}:
            return strategy
        return "auto"

    @staticmethod
    def normalize_vector_weight(value: Any) -> float:
        try:
            return max(0.0, min(1.0, float(value)))
        except (TypeError, ValueError):
            return 0.7

    @staticmethod
    def _metadata_exact_match_score(query: str, item_id: str, metadata: dict[str, Any]) -> float:
        needle = query.strip().lower()
        if not needle:
            return 0.0
        score = 0.0
        if needle == str(item_id or "").strip().lower():
            score += 2.0
        for field in ("sender_id", "sender_name"):
            value = str(metadata.get(field, "") or "").strip().lower()
            if value and needle == value:
                score += 1.2
        tags = {
            tag.strip().lower()
            for tag in str(metadata.get("tags", "") or "").split(",")
            if tag.strip()
        }
        if needle in tags:
            score += 1.2
        content = str(metadata.get("content", "") or "").lower()
        if needle and needle in content:
            score += 0.6
        return score

    # ======================== common helpers ========================

    @staticmethod
    def has_profile_data(profile: dict[str, Any]) -> bool:
        return any(
            profile.get(f) for f in ("name", "traits", "preferences", "notes")
        )

    @staticmethod
    def format_profile_text(profile: dict[str, Any]) -> str:
        """Compact profile text for tool return values."""
        parts = []
        if profile.get("name"):
            parts.append(f"Name: {profile['name']}")
        if profile.get("traits"):
            parts.append(f"Traits: {', '.join(profile['traits'])}")
        if profile.get("preferences"):
            parts.append(f"Preferences: {', '.join(profile['preferences'])}")
        for hint in MemoryStore._format_recent_slot_change_hints(profile, max_items=2):
            parts.append(hint)
        if profile.get("notes"):
            parts.append(f"Notes: {profile['notes']}")
        return "\n".join(parts)

    @staticmethod
    def _now_timestamp() -> str:
        return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

    @staticmethod
    def normalize_timestamp(value: str) -> str:
        text = str(value).strip()
        if not text:
            raise ValueError("timestamp cannot be empty")

        try:
            dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
        except ValueError as exc:
            raise ValueError(
                f"invalid timestamp '{text}'. Use ISO-8601 such as 2026-03-14T00:00:00Z"
            ) from exc

        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        else:
            dt = dt.astimezone(timezone.utc)
        return dt.strftime("%Y-%m-%dT%H:%M:%SZ")

    @classmethod
    def normalize_optional_timestamp(cls, value: str) -> str:
        text = str(value).strip()
        if not text:
            return ""
        return cls.normalize_timestamp(text)

    @staticmethod
    def _normalize_slot_key(value: str) -> str:
        return "_".join(str(value).strip().lower().split())

    @staticmethod
    def _normalize_text_list(values: Any) -> list[str]:
        if not isinstance(values, list):
            return []
        normalized: list[str] = []
        seen: set[str] = set()
        for item in values:
            text = str(item).strip()
            if not text or text in seen:
                continue
            seen.add(text)
            normalized.append(text)
        return normalized

    @classmethod
    def _normalize_slot_group(cls, raw_group: Any) -> dict[str, dict[str, Any]]:
        if not isinstance(raw_group, dict):
            return {}

        normalized: dict[str, dict[str, Any]] = {}
        for raw_key, raw_slot in raw_group.items():
            slot_key = cls._normalize_slot_key(str(raw_key))
            if not slot_key or not isinstance(raw_slot, dict):
                continue

            value = str(raw_slot.get("value", "") or "").strip()
            updated_at = str(raw_slot.get("updated_at", "") or "")
            history_items = raw_slot.get("history", [])
            history: list[dict[str, str]] = []
            if isinstance(history_items, list):
                for item in history_items:
                    if not isinstance(item, dict):
                        continue
                    hist_value = str(item.get("value", "") or "").strip()
                    if not hist_value:
                        continue
                    history.append({
                        "value": hist_value,
                        "timestamp": str(item.get("timestamp", "") or ""),
                        "status": str(item.get("status", "") or "superseded"),
                        "reason": str(item.get("reason", "") or ""),
                    })

            confidence = raw_slot.get("confidence")
            if isinstance(confidence, (int, float)):
                confidence_value: float | None = max(0.0, min(1.0, float(confidence)))
            else:
                confidence_value = None

            if not value and not history:
                continue

            normalized[slot_key] = {
                "value": value,
                "updated_at": updated_at,
                "history": history[-cls._MAX_SLOT_HISTORY:],
                "confidence": confidence_value,
            }

        return normalized

    def _profile_field_limit(self, field: str) -> int:
        config = self.plugin.get_config() if hasattr(self.plugin, "get_config") else {}
        return (
            config.get("max_profile_traits", self._default_max_profile_traits)
            if field == "traits"
            else config.get("max_profile_preferences", self._default_max_profile_preferences)
        )

    def _compose_field_values(
        self,
        profile: dict[str, Any],
        field: str,
    ) -> list[str]:
        slot_group = profile.get("profile_slots", {}).get(field, {})
        slot_values: list[str] = []
        if isinstance(slot_group, dict):
            slot_entries = sorted(
                slot_group.values(),
                key=lambda slot: str(slot.get("updated_at", "") or ""),
                reverse=True,
            )
            for slot in slot_entries:
                current_value = str(slot.get("value", "") or "").strip()
                if current_value and current_value not in slot_values:
                    slot_values.append(current_value)

        freeform_key = f"freeform_{field}"
        values = list(slot_values)
        for item in profile.get(freeform_key, []):
            if item not in values:
                values.append(item)

        return values[:self._profile_field_limit(field)]

    def _normalize_profile(self, profile: Any) -> dict[str, Any]:
        raw_profile = profile if isinstance(profile, dict) else {}
        normalized = _default_profile()

        normalized["name"] = str(raw_profile.get("name", "") or "").strip()
        normalized["notes"] = str(raw_profile.get("notes", "") or "")[:self._MAX_NOTES_LENGTH]
        normalized["updated_at"] = str(raw_profile.get("updated_at", "") or "")

        for field in self._STRUCTURED_FIELDS:
            freeform_key = f"freeform_{field}"
            source_values = raw_profile.get(freeform_key)
            if source_values is None:
                source_values = raw_profile.get(field, [])
            normalized[freeform_key] = self._normalize_text_list(source_values)[
                : self._profile_field_limit(field)
            ]

        raw_slots = raw_profile.get("profile_slots", {})
        normalized["profile_slots"] = {
            "traits": self._normalize_slot_group(
                raw_slots.get("traits") if isinstance(raw_slots, dict) else {}
            ),
            "preferences": self._normalize_slot_group(
                raw_slots.get("preferences") if isinstance(raw_slots, dict) else {}
            ),
        }

        for field in self._STRUCTURED_FIELDS:
            normalized[field] = self._compose_field_values(normalized, field)

        return normalized

    @classmethod
    def _append_slot_history(
        cls,
        slot: dict[str, Any],
        value: str,
        timestamp: str,
        status: str,
        reason: str,
    ) -> None:
        text = str(value).strip()
        if not text:
            return

        history = slot.get("history", [])
        if not isinstance(history, list):
            history = []

        history.append({
            "value": text,
            "timestamp": timestamp,
            "status": status,
            "reason": reason,
        })
        slot["history"] = history[-cls._MAX_SLOT_HISTORY:]

    def _clear_slot_group_current_values(
        self,
        profile: dict[str, Any],
        field: str,
        reason: str,
    ) -> None:
        now = self._now_timestamp()
        slot_group = profile.get("profile_slots", {}).get(field, {})
        if not isinstance(slot_group, dict):
            return
        for slot in slot_group.values():
            current_value = str(slot.get("value", "") or "").strip()
            if not current_value:
                continue
            self._append_slot_history(
                slot,
                current_value,
                str(slot.get("updated_at", "") or now),
                "superseded",
                reason,
            )
            slot["value"] = ""
            slot["updated_at"] = now

    def _remove_matching_slot_values(
        self,
        profile: dict[str, Any],
        field: str,
        value: str,
    ) -> None:
        target = str(value).strip()
        if not target:
            return
        now = self._now_timestamp()
        slot_group = profile.get("profile_slots", {}).get(field, {})
        if not isinstance(slot_group, dict):
            return
        for slot in slot_group.values():
            current_value = str(slot.get("value", "") or "").strip()
            if current_value != target:
                continue
            self._append_slot_history(
                slot,
                current_value,
                str(slot.get("updated_at", "") or now),
                "removed",
                "freeform_remove",
            )
            slot["value"] = ""
            slot["updated_at"] = now

    def _update_structured_slot(
        self,
        profile: dict[str, Any],
        field: str,
        action: str,
        value: str,
        fact_key: str,
        previous_value: str = "",
    ) -> None:
        slot_group = profile.setdefault("profile_slots", {}).setdefault(field, {})
        slot_key = self._normalize_slot_key(fact_key)
        if not slot_key:
            return

        slot = slot_group.setdefault(slot_key, {
            "value": "",
            "updated_at": "",
            "history": [],
            "confidence": None,
        })
        current_value = str(slot.get("value", "") or "").strip()
        current_updated_at = str(slot.get("updated_at", "") or "")
        new_value = str(value).strip()
        previous_text = str(previous_value).strip()
        now = self._now_timestamp()

        if action == "remove":
            if current_value:
                self._append_slot_history(
                    slot,
                    current_value,
                    current_updated_at or now,
                    "removed",
                    "explicit_remove",
                )
            slot["value"] = ""
            slot["updated_at"] = now
            return

        if not new_value:
            return

        if not current_value and previous_text and previous_text != new_value:
            self._append_slot_history(
                slot,
                previous_text,
                now,
                "superseded",
                "provided_previous_value",
            )

        if current_value and current_value != new_value:
            self._append_slot_history(
                slot,
                current_value,
                current_updated_at or now,
                "superseded",
                "profile_update",
            )

        if current_value != new_value:
            slot["value"] = new_value
            slot["updated_at"] = now
        elif not current_updated_at:
            slot["updated_at"] = now

    @classmethod
    def _slot_updated_within_days(
        cls,
        slot: dict[str, Any],
        max_days: int,
    ) -> bool:
        updated_at = str(slot.get("updated_at", "") or "")
        if not updated_at:
            return False
        try:
            ts = datetime.fromisoformat(updated_at.replace("Z", "+00:00"))
            now = datetime.now(timezone.utc)
            age_days = max(0.0, (now - ts).total_seconds() / 86400.0)
        except (ValueError, TypeError):
            return False
        return age_days <= max_days

    @classmethod
    def _format_recent_slot_change_hints(
        cls,
        profile: dict[str, Any],
        max_items: int = 2,
    ) -> list[str]:
        slot_root = profile.get("profile_slots", {})
        if not isinstance(slot_root, dict):
            return []

        changes: list[tuple[str, str, str, str, str]] = []
        for field in cls._STRUCTURED_FIELDS:
            slot_group = slot_root.get(field, {})
            if not isinstance(slot_group, dict):
                continue
            for slot_key, slot in slot_group.items():
                history = slot.get("history", [])
                current_value = str(slot.get("value", "") or "").strip()
                if not current_value or not isinstance(history, list) or not history:
                    continue
                if not cls._slot_updated_within_days(
                    slot, cls._RECENT_SLOT_CHANGE_DAYS,
                ):
                    continue
                previous_value = str(history[-1].get("value", "") or "").strip()
                if not previous_value or previous_value == current_value:
                    continue
                changes.append((
                    str(slot.get("updated_at", "") or ""),
                    field,
                    slot_key,
                    current_value,
                    previous_value,
                ))

        changes.sort(key=lambda item: item[0], reverse=True)
        hints: list[str] = []
        for _updated_at, field, slot_key, current_value, previous_value in changes[:max_items]:
            label = "Preference" if field == "preferences" else "Trait"
            hints.append(
                f"Recent {label.lower()} update ({slot_key}): now {current_value}; previously {previous_value}"
            )
        return hints

    # ======================== key helpers ========================

    @staticmethod
    def get_session_key(
        bot_uuid: str,
        launcher_type_value: str,
        launcher_id: Any,
    ) -> str:
        session_id = f"{launcher_type_value}_{launcher_id}"
        if not bot_uuid:
            return session_id
        return f"{bot_uuid}:{session_id}"

    @staticmethod
    def get_user_key(session_key: str, isolation: str, bot_uuid: str = "") -> str:
        if isolation == "session":
            return session_key
        if bot_uuid:
            return f"bot:{bot_uuid}"
        return "global"

    @classmethod
    def get_scope_key(
        cls,
        bot_uuid: str,
        launcher_type_value: str,
        launcher_id: Any,
        isolation: str,
    ) -> str:
        session_key = cls.get_session_key(bot_uuid, launcher_type_value, launcher_id)
        return cls.get_user_key(session_key, isolation, bot_uuid)

    @staticmethod
    def split_session_name(session_name: str) -> tuple[str, str]:
        launcher_type, sep, launcher_id = session_name.partition("_")
        if not sep:
            return session_name, ""
        return launcher_type, launcher_id

    @classmethod
    def get_scope_key_from_session_name(
        cls,
        bot_uuid: str,
        session_name: str,
        isolation: str,
    ) -> str:
        launcher_type, launcher_id = cls.split_session_name(session_name)
        return cls.get_scope_key(bot_uuid, launcher_type, launcher_id, isolation)

    async def resolve_user_context(
        self, session: Any, bot_uuid: str = ""
    ) -> tuple[str, str, str | None, str, dict[str, Any]]:
        """Derive session_key, user_key, kb_id, isolation from a session.

        Returns (session_key, user_key, kb_id_or_None, isolation, kb_config).
        kb_id is None and kb_config is {} when no KB is configured.
        """
        kb_id, config = None, {}
        kb = await self.get_kb_config()
        if kb:
            kb_id, config = kb
        isolation = config.get("isolation", "session")
        session_key = self.get_session_key(
            bot_uuid, session.launcher_type.value, session.launcher_id
        )
        user_key = self.get_user_key(session_key, isolation, bot_uuid)
        logger.info(
            "[LongTermMemory] resolved user context: session_key=%s user_key=%s kb_id=%s isolation=%s",
            session_key,
            user_key,
            kb_id,
            isolation,
        )
        return session_key, user_key, kb_id, isolation, config

    async def resolve_user_key(self, session: Any, bot_uuid: str = "") -> str:
        """Derive user_key from a session object (lightweight, no kb_id/config)."""
        kb = await self.get_kb_config()
        isolation = kb[1].get("isolation", "session") if kb else "session"
        session_key = self.get_session_key(
            bot_uuid, session.launcher_type.value, session.launcher_id
        )
        return self.get_user_key(session_key, isolation, bot_uuid)

    # ======================== KB config persistence ========================

    _KB_CONFIGS_KEY = "kb_configs"

    @serialized_write(scope=_installation_scope)
    async def save_kb_config(self, kb_id: str, config: dict[str, Any]) -> None:
        configs = await self._read_json(self._KB_CONFIGS_KEY) or {}
        configs[kb_id] = config
        await self._write_json(self._KB_CONFIGS_KEY, configs, None)

    @serialized_write(scope=_installation_scope, allow_fenced=True)
    async def remove_kb_config(self, kb_id: str) -> None:
        configs = await self._read_json(self._KB_CONFIGS_KEY) or {}
        configs.pop(kb_id, None)
        await self._write_json(self._KB_CONFIGS_KEY, configs, None)
        # Unregistering the KB deletes the fenced object, so whatever its last
        # ambiguous write was is moot and the collection starts unfenced.
        await self._writes.clear_fence(self.plugin, kb_id)

    async def get_kb_configs(self) -> dict[str, dict[str, Any]]:
        return await self._read_json(self._KB_CONFIGS_KEY) or {}

    async def get_kb_config(self) -> tuple[str, dict[str, Any]] | None:
        """Return (kb_id, config) for the single registered KB, or None."""
        configs = await self.get_kb_configs()
        if configs:
            kb_id = next(iter(configs))
            return kb_id, configs[kb_id]
        return None

    # ======================== L1: profile (Binary Storage) ========================

    def _session_profile_key(self, scope_key: str) -> str:
        return f"ps:{scope_key}"

    def _speaker_profile_key(self, scope_key: str, sender_id: str) -> str:
        return f"pp:{scope_key}:{sender_id}"

    @staticmethod
    def _audit_key(scope_key: str) -> str:
        return f"audit:{scope_key}"

    @staticmethod
    def _candidate_key(scope_key: str) -> str:
        return f"candidates:{scope_key}"

    async def _read_json(self, key: str) -> Any:
        try:
            data = await self.plugin.get_plugin_storage(key)
        except (KeyError, ActionCallError) as exc:
            if isinstance(exc, ActionCallError):
                message = str(exc)
                # RPC hops can prepend the exception name more than once.
                while message.startswith("ActionCallError: "):
                    message = message.removeprefix("ActionCallError: ")
                if message != f"Storage with key {key} not found":
                    raise
            logger.debug("storage key %s not found", key)
            return None
        if not data:
            return None
        try:
            return json.loads(data.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError) as e:
            raise ValueError(f"storage key {key} contains corrupt JSON") from e

    async def _write_json(self, key: str, obj: Any, scope: str | None) -> None:
        """Persist one JSON record; an unknown Host write outcome fences *scope*."""
        data = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        await self._writes.mutate(
            self.plugin,
            scope,
            lambda: self.plugin.set_plugin_storage(key, data),
            f"Host set_plugin_storage outcome unknown for {key}",
        )

    def is_fenced(self, identity: str | None = None) -> bool:
        """Whether one memory scope currently requires reconciliation."""
        return self._writes.is_fenced(self._writes.binding(self.plugin), identity)

    async def clear_fence(self, identity: str | None = None) -> None:
        """Acknowledge reconciliation for one memory scope after an ambiguous write."""
        await self._writes.clear_fence(self.plugin, identity)

    async def list_fences(self) -> list[dict[str, Any]]:
        """The persisted fence records for this installation, best effort."""
        try:
            keys = await self.plugin.get_plugin_storage_keys()
        except Exception:
            logger.warning("Could not list persisted fences", exc_info=True)
            return []
        records: list[dict[str, Any]] = []
        for key in keys:
            if not key.startswith(FENCE_KEY_PREFIX):
                continue
            try:
                marker = json.loads(await self.plugin.get_plugin_storage(key))
            except Exception:
                marker = None
            if isinstance(marker, dict):
                records.append({
                    "scope": str(marker.get("scope", "") or ""),
                    "reason": str(marker.get("reason", "") or ""),
                })
        return records

    def release_binding(self, binding) -> None:
        """Drop process-local lock/fence state for one revoked installation."""
        self._writes.release_binding(binding)
        logger.info("[LongTermMemory] released process-local state for %r", binding)

    @serialized_write
    async def append_audit_entry(
        self,
        scope_key: str,
        operation: str,
        target_type: str,
        target_id: str,
        summary: str,
        *,
        user_key: str = "",
        sender_id: str = "",
        sender_name: str = "",
        query_id: int | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Append a scoped audit entry to plugin storage."""
        entry = {
            "audit_id": uuid.uuid4().hex[:12],
            "operation": operation,
            "scope_key": scope_key,
            "user_key": user_key,
            "sender_id": sender_id,
            "sender_name": sender_name,
            "target_type": target_type,
            "target_id": target_id,
            "summary": self._preview_text(summary, 240),
            "timestamp": self._now_timestamp(),
            "query_id": query_id,
            "metadata": metadata or {},
        }
        key = self._audit_key(scope_key)
        entries = await self._read_json(key)
        if not isinstance(entries, list):
            entries = []
        entries.append(entry)
        entries = entries[-self._MAX_AUDIT_ENTRIES_PER_SCOPE:]
        await self._write_json(key, entries, scope_key)
        return entry

    async def list_audit_entries(
        self,
        scope_key: str,
        limit: int = 10,
        offset: int = 0,
    ) -> tuple[list[dict[str, Any]], int]:
        entries = await self._read_json(self._audit_key(scope_key))
        if not isinstance(entries, list):
            entries = []
        ordered = list(reversed(entries))
        return ordered[offset: offset + limit], len(ordered)

    async def export_audit_entries(self, scope_key: str) -> list[dict[str, Any]]:
        entries = await self._read_json(self._audit_key(scope_key))
        if not isinstance(entries, list):
            return []
        return list(entries)

    # ==================== injection snapshot ====================

    @staticmethod
    def _injection_snapshot_key(scope_key: str) -> str:
        return f"inj:{scope_key}"

    @serialized_write
    async def save_injection_snapshot(
        self,
        scope_key: str,
        snapshot: dict[str, Any],
    ) -> None:
        """Persist the latest memory-injection snapshot for a scope.

        Only the most recent snapshot per scope is retained (overwrite), so the
        memory console can show "what the bot actually remembered last turn"
        without depending on log scraping or the live query lifecycle.
        """
        await self._write_json(self._injection_snapshot_key(scope_key), snapshot, scope_key)

    async def get_injection_snapshot(self, scope_key: str) -> dict[str, Any] | None:
        snapshot = await self._read_json(self._injection_snapshot_key(scope_key))
        if not isinstance(snapshot, dict):
            return None
        return snapshot

    @serialized_write
    async def append_memory_candidate(
        self,
        scope_key: str,
        user_key: str,
        candidate_type: str,
        payload: dict[str, Any],
        reason: str,
        *,
        sender_id: str = "",
        sender_name: str = "",
        query_id: int | None = None,
    ) -> dict[str, Any]:
        candidate_type = str(candidate_type or "").strip().lower()
        if candidate_type not in {"l1_profile", "l2_episode", "ignore"}:
            raise ValueError("candidate_type must be l1_profile, l2_episode, or ignore")
        entry = {
            "candidate_id": uuid.uuid4().hex[:12],
            "scope_key": scope_key,
            "user_key": user_key,
            "candidate_type": candidate_type,
            "status": self.CANDIDATE_STATUS_PENDING,
            "payload": copy.deepcopy(payload),
            "reason": self._preview_text(reason, 240),
            "sender_id": sender_id,
            "sender_name": sender_name,
            "query_id": query_id,
            "created_at": self._now_timestamp(),
            "updated_at": self._now_timestamp(),
        }
        key = self._candidate_key(scope_key)
        entries = await self._read_json(key)
        if not isinstance(entries, list):
            entries = []
        entries.append(entry)
        entries = entries[-self._MAX_CANDIDATES_PER_SCOPE:]
        await self._write_json(key, entries, scope_key)
        return entry

    async def list_memory_candidates(
        self,
        scope_key: str,
        *,
        limit: int = 10,
        offset: int = 0,
        include_statuses: list[str] | set[str] | tuple[str, ...] | None = None,
    ) -> tuple[list[dict[str, Any]], int]:
        statuses = {
            str(status or "").strip().lower()
            for status in (include_statuses or [self.CANDIDATE_STATUS_PENDING])
        }
        statuses = statuses & self.CANDIDATE_STATUSES
        if not statuses:
            statuses = {self.CANDIDATE_STATUS_PENDING}
        entries = await self._read_json(self._candidate_key(scope_key))
        if not isinstance(entries, list):
            entries = []
        filtered = [entry for entry in reversed(entries) if entry.get("status") in statuses]
        return filtered[offset: offset + limit], len(filtered)

    async def get_memory_candidate(
        self,
        scope_key: str,
        candidate_id: str,
    ) -> dict[str, Any] | None:
        entries = await self._read_json(self._candidate_key(scope_key))
        if not isinstance(entries, list):
            return None
        for entry in entries:
            if entry.get("candidate_id") == candidate_id:
                return copy.deepcopy(entry)
        return None

    @serialized_write
    async def _update_memory_candidate(
        self,
        scope_key: str,
        candidate_id: str,
        status: str,
    ) -> dict[str, Any] | None:
        status = str(status or "").strip().lower()
        if status not in self.CANDIDATE_STATUSES:
            raise ValueError("candidate status must be pending, accepted, or rejected")
        key = self._candidate_key(scope_key)
        entries = await self._read_json(key)
        if not isinstance(entries, list):
            return None
        updated: dict[str, Any] | None = None
        for entry in entries:
            if entry.get("candidate_id") != candidate_id:
                continue
            entry["status"] = status
            entry["updated_at"] = self._now_timestamp()
            updated = entry
            break
        if updated is None:
            return None
        await self._write_json(key, entries, scope_key)
        return updated

    async def reject_memory_candidate(
        self,
        scope_key: str,
        candidate_id: str,
    ) -> dict[str, Any] | None:
        return await self._update_memory_candidate(
            scope_key,
            candidate_id,
            self.CANDIDATE_STATUS_REJECTED,
        )

    @serialized_write
    async def accept_memory_candidate(
        self,
        scope_key: str,
        candidate_id: str,
        *,
        collection_id: str,
        embedding_model_uuid: str,
        user_key: str,
        bot_uuid: str = "",
    ) -> dict[str, Any] | None:
        key = self._candidate_key(scope_key)
        entries = await self._read_json(key)
        if not isinstance(entries, list):
            return None

        candidate = None
        for entry in entries:
            if entry.get("candidate_id") == candidate_id:
                candidate = entry
                break
        if not candidate:
            return None
        if candidate.get("status") != self.CANDIDATE_STATUS_PENDING:
            raise ValueError("candidate is not pending")

        payload = candidate.get("payload", {})
        result: dict[str, Any]
        candidate_type = candidate.get("candidate_type")
        if candidate_type == "l2_episode":
            episode = await self.add_episode(
                collection_id=collection_id,
                embedding_model_uuid=embedding_model_uuid,
                user_key=user_key,
                content=str(payload.get("content", "") or ""),
                tags=self._normalize_text_list(payload.get("tags", [])),
                importance=int(payload.get("importance", 2) or 2),
                source="candidate",
                sender_id=str(candidate.get("sender_id", "") or ""),
                sender_name=str(candidate.get("sender_name", "") or ""),
                bot_uuid=bot_uuid,
            )
            result = {"type": "episode", "episode": episode}
        elif candidate_type == "l1_profile":
            target_scope = str(payload.get("target_scope", "speaker") or "speaker")
            field = str(payload.get("field", "notes") or "notes")
            action = str(payload.get("action", "add") or "add")
            value = str(payload.get("value", "") or "")
            fact_key = str(payload.get("fact_key", "") or "")
            previous_value = str(payload.get("previous_value", "") or "")
            if target_scope == "session":
                profile = await self.update_session_profile_field(
                    scope_key,
                    field,
                    action,
                    value,
                    fact_key,
                    previous_value,
                )
            else:
                profile = await self.update_speaker_profile_field(
                    scope_key,
                    str(candidate.get("sender_id", "") or ""),
                    field,
                    action,
                    value,
                    fact_key,
                    previous_value,
                )
            result = {"type": "profile", "profile": profile}
        else:
            result = {"type": "ignore"}

        candidate["status"] = self.CANDIDATE_STATUS_ACCEPTED
        candidate["updated_at"] = self._now_timestamp()
        candidate["accepted_result"] = result
        await self._write_json(key, entries, scope_key)
        return candidate

    async def _load_profile_by_storage_key(self, storage_key: str) -> dict[str, Any]:
        profile = await self._read_json(storage_key)
        if not profile:
            profile = _default_profile()
        return self._normalize_profile(profile)

    async def _save_profile_by_storage_key(
        self, storage_key: str, profile: dict[str, Any], scope_key: str
    ) -> dict[str, Any]:
        profile = self._normalize_profile(profile)
        profile["updated_at"] = self._now_timestamp()
        await self._write_json(storage_key, profile, scope_key)
        return profile

    async def load_session_profile(self, scope_key: str) -> dict[str, Any]:
        return await self._load_profile_by_storage_key(
            self._session_profile_key(scope_key)
        )

    async def load_speaker_profile(
        self, scope_key: str, sender_id: str
    ) -> dict[str, Any]:
        if not sender_id:
            return _default_profile()
        return await self._load_profile_by_storage_key(
            self._speaker_profile_key(scope_key, sender_id)
        )

    @serialized_write
    async def _update_profile_field_by_storage_key(
        self,
        storage_key: str,
        field: str,
        action: str,
        value: str,
        fact_key: str = "",
        previous_value: str = "",
        *,
        scope_key: str,
    ) -> dict[str, Any]:
        profile = copy.deepcopy(
            await self._load_profile_by_storage_key(storage_key)
        )

        if field == "name":
            profile["name"] = value
        elif field in self._STRUCTURED_FIELDS:
            freeform_key = f"freeform_{field}"
            items: list[str] = self._normalize_text_list(profile.get(freeform_key, []))
            if fact_key:
                slot_key = self._normalize_slot_key(fact_key)
                old_slot = profile.get("profile_slots", {}).get(field, {}).get(slot_key, {})
                old_slot_value = str(old_slot.get("value", "") or "").strip()
                self._update_structured_slot(
                    profile,
                    field,
                    action,
                    value,
                    fact_key,
                    previous_value,
                )
                new_slot = profile.get("profile_slots", {}).get(field, {}).get(slot_key, {})
                new_slot_value = str(new_slot.get("value", "") or "").strip()
                profile[freeform_key] = [
                    item for item in items
                    if item not in {
                        old_slot_value,
                        new_slot_value,
                        str(previous_value).strip(),
                    }
                ]
            elif action == "add":
                if value not in items:
                    items.append(value)
                    items = items[-self._profile_field_limit(field):]
                profile[freeform_key] = items
            elif action == "remove":
                profile[freeform_key] = [i for i in items if i != value]
                self._remove_matching_slot_values(profile, field, value)
            elif action == "set":
                profile[freeform_key] = [value]
                self._clear_slot_group_current_values(
                    profile, field, "field_set_reset",
                )
            profile[field] = self._compose_field_values(profile, field)
        elif field == "notes":
            if action == "set":
                profile["notes"] = value[:self._MAX_NOTES_LENGTH]
            elif action == "add":
                existing = profile.get("notes", "")
                new_notes = f"{existing}; {value}" if existing else value
                if len(new_notes) > self._MAX_NOTES_LENGTH:
                    new_notes = new_notes[:self._MAX_NOTES_LENGTH]
                    logger.warning(
                        "notes for %s truncated to %d chars",
                        storage_key, self._MAX_NOTES_LENGTH,
                    )
                profile["notes"] = new_notes
            elif action == "remove":
                profile["notes"] = ""

        profile = await self._save_profile_by_storage_key(storage_key, profile, scope_key)
        return profile

    async def update_session_profile_field(
        self,
        scope_key: str,
        field: str,
        action: str,
        value: str,
        fact_key: str = "",
        previous_value: str = "",
    ) -> dict[str, Any]:
        return await self._update_profile_field_by_storage_key(
            self._session_profile_key(scope_key),
            field,
            action,
            value,
            fact_key,
            previous_value,
            scope_key=scope_key,
        )

    async def update_speaker_profile_field(
        self,
        scope_key: str,
        sender_id: str,
        field: str,
        action: str,
        value: str,
        fact_key: str = "",
        previous_value: str = "",
    ) -> dict[str, Any]:
        return await self._update_profile_field_by_storage_key(
            self._speaker_profile_key(scope_key, sender_id),
            field,
            action,
            value,
            fact_key,
            previous_value,
            scope_key=scope_key,
        )

    @serialized_write
    async def clear_session_profile(self, scope_key: str) -> None:
        await self._save_profile_by_storage_key(
            self._session_profile_key(scope_key), _default_profile(), scope_key
        )

    @serialized_write
    async def clear_speaker_profile(self, scope_key: str, sender_id: str) -> None:
        await self._save_profile_by_storage_key(
            self._speaker_profile_key(scope_key, sender_id), _default_profile(), scope_key
        )

    async def export_profiles_by_scope(
        self, scope_key: str
    ) -> list[dict[str, Any]]:
        """Export L1 profiles that belong to *scope_key*.

        Only profiles whose storage key matches the given scope_key are
        returned, preventing cross-session / cross-user data leakage.

        Returns a list of dicts, each containing type, scope_key,
        optional sender_id, and profile data.
        """
        keys: list[str] = await self.plugin.get_plugin_storage_keys()
        profiles: list[dict[str, Any]] = []

        session_storage_key = self._session_profile_key(scope_key)
        speaker_prefix = f"pp:{scope_key}:"

        for key in keys:
            if key == session_storage_key:
                profile = self._normalize_profile(await self._read_json(key))
                if profile and self.has_profile_data(profile):
                    entry: dict[str, Any] = {
                        "type": "session",
                        "scope_key": scope_key,
                        "profile": copy.deepcopy(profile),
                    }
                    profiles.append(entry)

            elif key.startswith(speaker_prefix):
                sender_id = key[len(speaker_prefix):]
                if not sender_id:
                    continue
                profile = self._normalize_profile(await self._read_json(key))
                if profile and self.has_profile_data(profile):
                    entry = {
                        "type": "speaker",
                        "scope_key": scope_key,
                        "sender_id": sender_id,
                        "profile": copy.deepcopy(profile),
                    }
                    profiles.append(entry)

        return profiles

    # ======================== L2: episodes (ChromaDB vector) ========================

    _SUPERSEDE_IMPORTANCE_FACTOR = 0.1  # multiplied onto old importance

    @serialized_write
    async def _auto_supersede(
        self,
        collection_id: str,
        embedding_model_uuid: str,
        query_vector: list[float],
        user_key: str,
        new_episode_id: str,
        similarity_threshold: float = 0.85,
        max_candidates: int = 5,
    ) -> int:
        """Find similar older episodes and mark them as superseded.

        Superseding means re-upserting the old vector with:
        - importance reduced by _SUPERSEDE_IMPORTANCE_FACTOR
        - 'superseded_by' metadata field set to new_episode_id
        - 'status' metadata field set to 'superseded'

        Returns the number of superseded episodes.
        """
        filters: dict[str, Any] = {"user_key": user_key}
        results = await self.plugin.vector_search(
            collection_id=collection_id,
            query_vector=query_vector,
            top_k=max_candidates + 1,  # +1 because the new episode itself may appear
            filters=filters,
        )

        superseded = 0
        for r in results:
            rid = r.get("id", "")
            if rid == new_episode_id:
                continue
            meta = r.get("metadata", {})
            # Already superseded — skip
            if (
                meta.get("superseded_by")
                or self.episode_status_from_metadata(meta)
                != self.EPISODE_STATUS_ACTIVE
            ):
                continue

            # Check similarity: distance is cosine distance (lower = more similar)
            distance = r.get("distance", 1.0)
            similarity = 1.0 - distance
            if similarity < similarity_threshold:
                continue

            # Re-upsert with reduced importance and superseded_by marker
            old_importance = int(meta.get("importance", "2"))
            new_importance = max(
                1,
                int(old_importance * self._SUPERSEDE_IMPORTANCE_FACTOR),
            )
            meta["importance"] = str(new_importance)
            meta["superseded_by"] = new_episode_id
            meta["status"] = self.EPISODE_STATUS_SUPERSEDED

            # We need the original vector; re-embed from content
            old_content = meta.get("content", "")
            if not old_content:
                continue
            old_vectors = await self.plugin.invoke_embedding(
                embedding_model_uuid,
                [old_content],
            )

            await self._writes.mutate(
                self.plugin,
                collection_id,
                lambda: self.plugin.vector_upsert(
                    collection_id=collection_id,
                    vectors=old_vectors,
                    ids=[rid],
                    metadata=[meta],
                    documents=[old_content],
                ),
                "Host vector_upsert outcome unknown",
            )
            superseded += 1
            logger.info(
                "[LongTermMemory] auto_supersede: episode %s superseded by %s (similarity=%.3f, importance %s->%s)",
                rid,
                new_episode_id,
                similarity,
                old_importance,
                new_importance,
            )

        return superseded

    @serialized_write
    async def add_episode(
        self,
        collection_id: str,
        embedding_model_uuid: str,
        user_key: str,
        content: str,
        tags: list[str] | None = None,
        importance: int = 2,
        source: str = "agent",
        sender_id: str = "",
        sender_name: str = "",
        bot_uuid: str = "",
    ) -> dict[str, Any]:
        """Store an episodic memory into vector DB."""
        episode_id = uuid.uuid4().hex[:12]
        timestamp = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        importance = max(1, min(5, importance))
        tags = tags or []
        logger.info(
            "[LongTermMemory] add_episode: collection_id=%s user_key=%s sender_id=%s importance=%s tags=%s content_len=%s",
            collection_id,
            user_key,
            sender_id,
            importance,
            tags,
            len(content),
        )

        metadata = {
            "content": content,
            "tags": ",".join(tags),
            "importance": str(importance),
            "timestamp": timestamp,
            "user_key": user_key,
            "source": source,
            "sender_id": sender_id,
            "sender_name": sender_name,
            "bot_uuid": bot_uuid,
            "status": self.EPISODE_STATUS_ACTIVE,
        }

        vectors = await self.plugin.invoke_embedding(embedding_model_uuid, [content])

        await self._writes.mutate(
            self.plugin,
            collection_id,
            lambda: self.plugin.vector_upsert(
                collection_id=collection_id,
                vectors=vectors,
                ids=[episode_id],
                metadata=[metadata],
                documents=[content],
            ),
            "Host vector_upsert outcome unknown",
        )
        logger.info(
            "[LongTermMemory] add_episode stored: collection_id=%s episode_id=%s timestamp=%s",
            collection_id,
            episode_id,
            timestamp,
        )

        # Auto-supersede: when the new episode is a correction / fact-update /
        # clarification, search for similar older episodes in the same scope and
        # mark them as superseded by lowering their importance.
        if _SUPERSEDE_TAGS & set(tags):
            try:
                await self._auto_supersede(
                    collection_id=collection_id,
                    embedding_model_uuid=embedding_model_uuid,
                    query_vector=vectors[0],
                    user_key=user_key,
                    new_episode_id=episode_id,
                    similarity_threshold=0.85,
                )
            except Exception:
                logger.warning(
                    "[LongTermMemory] auto_supersede failed for episode %s, skipping",
                    episode_id,
                    exc_info=True,
                )

        return {
            "id": episode_id,
            "content": content,
            "tags": tags,
            "importance": importance,
            "timestamp": timestamp,
            "user_key": user_key,
            "sender_id": sender_id,
            "sender_name": sender_name,
            "source": source,
            "status": self.EPISODE_STATUS_ACTIVE,
        }

    async def search_episodes(
        self,
        collection_id: str,
        embedding_model_uuid: str,
        query: str,
        user_key: str | None = None,
        top_k: int = 5,
        sender_id: str = "",
        sender_name: str = "",
        time_after: str = "",
        time_before: str = "",
        importance_min: int | None = None,
        source: str = "",
        include_statuses: list[str] | set[str] | tuple[str, ...] | None = None,
        retrieval_strategy: str = "auto",
        vector_weight: float | None = None,
        exact_match_boost: bool = True,
    ) -> list[dict[str, Any]]:
        """Search episodic memories via vector similarity."""
        if not query.strip():
            return []
        logger.info(
            "[LongTermMemory] search_episodes: collection_id=%s user_key=%s sender_id=%s sender_name=%s top_k=%s source=%s importance_min=%s time_after=%s time_before=%s statuses=%s strategy=%s query_len=%s",
            collection_id,
            user_key,
            sender_id,
            sender_name,
            top_k,
            source,
            importance_min,
            time_after,
            time_before,
            sorted(self.normalize_episode_statuses(include_statuses)),
            self.normalize_retrieval_strategy(retrieval_strategy),
            len(query),
        )

        vectors = await self.plugin.invoke_embedding(embedding_model_uuid, [query])
        query_vector = vectors[0]

        filters = {}
        if user_key:
            filters["user_key"] = user_key
        if sender_id:
            filters["sender_id"] = sender_id
        if sender_name:
            filters["sender_name"] = sender_name
        if source:
            filters["source"] = source
        if time_after or time_before:
            time_filter: dict[str, str] = {}
            if time_after:
                time_filter["$gte"] = self.normalize_timestamp(time_after)
            if time_before:
                time_filter["$lte"] = self.normalize_timestamp(time_before)
            filters["timestamp"] = time_filter
        if importance_min is not None:
            # importance is stored as a string ("1"-"5") in vector DB metadata;
            # string comparison works correctly for single-digit values in this range.
            filters["importance"] = {"$gte": str(importance_min)}

        # ChromaDB requires $and wrapper when there are multiple filter conditions
        if len(filters) > 1:
            filters = {"$and": [{k: v} for k, v in filters.items()]}

        exact_episode = None
        if exact_match_boost and user_key:
            exact_episode = await self.get_episode_by_id(
                collection_id=collection_id,
                episode_id=query.strip(),
                user_key=user_key,
            )

        fetch_k = max(top_k, top_k * 4, 50)
        strategy = self.normalize_retrieval_strategy(retrieval_strategy)
        normalized_weight = self.normalize_vector_weight(vector_weight)
        search_kwargs = {
            "collection_id": collection_id,
            "query_vector": query_vector,
            "top_k": fetch_k,
            "filters": filters if filters else None,
        }
        if strategy in {"auto", "hybrid"}:
            try:
                results = await self.plugin.vector_search(
                    **search_kwargs,
                    search_type="hybrid",
                    query_text=query,
                    vector_weight=normalized_weight,
                )
            except Exception:
                if strategy == "hybrid":
                    logger.warning(
                        "[LongTermMemory] hybrid search failed; falling back to vector search",
                        exc_info=True,
                    )
                else:
                    logger.info(
                        "[LongTermMemory] auto hybrid search unavailable; falling back to vector search",
                        exc_info=True,
                    )
                results = await self.plugin.vector_search(**search_kwargs)
        else:
            results = await self.plugin.vector_search(**search_kwargs)
        logger.info(
            "[LongTermMemory] search_episodes completed: collection_id=%s raw_result_count=%s filters=%s",
            collection_id,
            len(results),
            filters if filters else None,
        )

        seen_ids: set[str] = set()
        episodes = []
        if exact_episode and self.episode_status_included(
            exact_episode.get("metadata", {}),
            include_statuses,
        ):
            exact_episode["score"] = 1.0
            exact_episode["_exact_match_score"] = 2.0
            episodes.append(exact_episode)
            seen_ids.add(exact_episode["id"])

        for r in results:
            rid = r.get("id", "")
            if rid in seen_ids:
                continue
            meta = r.get("metadata", {})
            if not self.episode_status_included(meta, include_statuses):
                continue
            exact_score = (
                self._metadata_exact_match_score(query, rid, meta)
                if exact_match_boost
                else 0.0
            )
            episodes.append({
                "id": rid,
                "content": meta.get("content", ""),
                "tags": meta.get("tags", "").split(",") if meta.get("tags") else [],
                "importance": int(meta.get("importance", "2")),
                "timestamp": meta.get("timestamp", ""),
                "sender_id": meta.get("sender_id", ""),
                "sender_name": meta.get("sender_name", ""),
                "source": meta.get("source", ""),
                "status": self.episode_status_from_metadata(meta),
                "superseded_by": meta.get("superseded_by", ""),
                "score": r.get("score"),
                "_exact_match_score": exact_score,
            })
            if len(episodes) >= top_k:
                break

        if exact_match_boost:
            episodes.sort(
                key=lambda ep: (
                    float(ep.get("_exact_match_score", 0.0)),
                    float(ep.get("score") or 0.0),
                ),
                reverse=True,
            )
        for ep in episodes:
            ep.pop("_exact_match_score", None)
        return episodes[:top_k]

    @serialized_write
    async def delete_episodes_by_user(
        self, collection_id: str, user_key: str
    ) -> int:
        """Delete all episodes for a user_key."""
        return await self._writes.mutate(
            self.plugin,
            collection_id,
            lambda: self.plugin.vector_delete(
                collection_id=collection_id,
                filters={"user_key": user_key},
            ),
            "Host vector_delete outcome unknown",
        )

    async def list_episodes(
        self,
        collection_id: str,
        user_key: str,
        limit: int = 20,
        offset: int = 0,
        include_statuses: list[str] | set[str] | tuple[str, ...] | None = None,
    ) -> tuple[list[dict[str, Any]], int]:
        """List episodic memories for a user with pagination.

        Returns:
            Tuple of (episodes, total).
        """
        filters: dict[str, Any] = {"user_key": user_key}
        target_count = offset + limit
        batch_size = max(limit * 4, 50)
        raw_offset = 0
        raw_total = -1
        scanned_all = False
        included: list[dict[str, Any]] = []

        while len(included) < target_count:
            result = await self.plugin.vector_list(
                collection_id=collection_id,
                filters=filters,
                limit=batch_size,
                offset=raw_offset,
            )
            items = result.get("items", [])
            raw_total = result.get("total", raw_total)
            if not items:
                scanned_all = True
                break

            for item in items:
                meta = item.get("metadata", {})
                if not self.episode_status_included(meta, include_statuses):
                    continue
                included.append({
                    "id": item.get("id", ""),
                    "content": meta.get("content", "") or item.get("document", ""),
                    "tags": meta.get("tags", "").split(",") if meta.get("tags") else [],
                    "importance": int(meta.get("importance", "2")),
                    "timestamp": meta.get("timestamp", ""),
                    "sender_id": meta.get("sender_id", ""),
                    "sender_name": meta.get("sender_name", ""),
                    "source": meta.get("source", ""),
                    "status": self.episode_status_from_metadata(meta),
                    "superseded_by": meta.get("superseded_by", ""),
                })

            raw_offset += len(items)
            if raw_total >= 0 and raw_offset >= raw_total:
                scanned_all = True
                break
            if len(items) < batch_size:
                scanned_all = True
                break

        episodes = included[offset:target_count]
        filtered_total = len(included) if scanned_all else -1
        return episodes, filtered_total

    @staticmethod
    def _episode_matches_bulk_filters(
        episode: dict[str, Any],
        *,
        sender_id: str = "",
        tag: str = "",
        before: str = "",
        include_statuses: list[str] | set[str] | tuple[str, ...] | None = None,
    ) -> bool:
        if sender_id and episode.get("sender_id") != sender_id:
            return False
        if tag and tag not in set(episode.get("tags", [])):
            return False
        if before and str(episode.get("timestamp", "") or "") >= before:
            return False
        if not MemoryStore.episode_status_included(
            {"status": episode.get("status", "")},
            include_statuses,
        ):
            return False
        return True

    async def export_episodes_by_user(
        self,
        collection_id: str,
        user_key: str,
        *,
        include_statuses: list[str] | set[str] | tuple[str, ...] | None = None,
    ) -> list[dict[str, Any]]:
        """Export all L2 episodes for a single user_key scope."""
        exported: list[dict[str, Any]] = []
        offset = 0
        page_size = 100
        while True:
            episodes, total = await self.list_episodes(
                collection_id=collection_id,
                user_key=user_key,
                limit=page_size,
                offset=offset,
                include_statuses=include_statuses,
            )
            exported.extend(episodes)
            if not episodes:
                break
            offset += len(episodes)
            if total >= 0 and offset >= total:
                break
            if len(episodes) < page_size:
                break
        return exported

    @serialized_write
    async def import_episodes_for_user(
        self,
        collection_id: str,
        embedding_model_uuid: str,
        user_key: str,
        episodes: list[dict[str, Any]],
        *,
        bot_uuid: str = "",
    ) -> list[dict[str, Any]]:
        """Import L2 episodes into the current user_key scope.

        Any user_key in the input is intentionally ignored so imported data
        cannot overwrite or leak into another scope.
        """
        imported: list[dict[str, Any]] = []
        for raw in episodes:
            if not isinstance(raw, dict):
                raise ValueError("each imported episode must be an object")

            content = str(raw.get("content", "") or "").strip()
            if not content:
                raise ValueError("imported episode content cannot be empty")

            tags = self._normalize_text_list(raw.get("tags", []))
            importance_raw = raw.get("importance", 2)
            try:
                importance = int(importance_raw)
            except (TypeError, ValueError) as exc:
                raise ValueError("importance must be an integer from 1 to 5") from exc
            importance = max(1, min(5, importance))

            timestamp = self.normalize_optional_timestamp(
                str(raw.get("timestamp", "") or "")
            ) or self._now_timestamp()
            status = self.normalize_episode_status_value(raw.get("status", "active"))
            source = str(raw.get("source", "") or "import").strip() or "import"
            sender_id = str(raw.get("sender_id", "") or "").strip()
            sender_name = str(raw.get("sender_name", "") or "").strip()
            superseded_by = str(raw.get("superseded_by", "") or "").strip()
            imported_episode_id = str(
                raw.get("id", "") or raw.get("episode_id", "") or ""
            ).strip()
            episode_id = uuid.uuid4().hex[:12]

            metadata = {
                "content": content,
                "tags": ",".join(tags),
                "importance": str(importance),
                "timestamp": timestamp,
                "user_key": user_key,
                "source": source,
                "sender_id": sender_id,
                "sender_name": sender_name,
                "bot_uuid": bot_uuid,
                "status": status,
            }
            if superseded_by:
                metadata["superseded_by"] = superseded_by
            if imported_episode_id:
                metadata["imported_episode_id"] = imported_episode_id

            vectors = await self.plugin.invoke_embedding(embedding_model_uuid, [content])
            await self._writes.mutate(
                self.plugin,
                collection_id,
                lambda: self.plugin.vector_upsert(
                    collection_id=collection_id,
                    vectors=vectors,
                    ids=[episode_id],
                    metadata=[metadata],
                    documents=[content],
                ),
                "Host vector_upsert outcome unknown",
            )
            imported.append({
                "id": episode_id,
                "imported_episode_id": imported_episode_id,
                "content": content,
                "tags": tags,
                "importance": importance,
                "timestamp": timestamp,
                "user_key": user_key,
                "sender_id": sender_id,
                "sender_name": sender_name,
                "source": source,
                "status": status,
                "superseded_by": superseded_by,
            })

        return imported

    @serialized_write
    async def delete_episodes_by_filters(
        self,
        collection_id: str,
        user_key: str,
        *,
        sender_id: str = "",
        tag: str = "",
        before: str = "",
        include_statuses: list[str] | set[str] | tuple[str, ...] | None = None,
    ) -> tuple[int, list[str]]:
        """Delete scoped L2 episodes matching explicit management filters."""
        normalized_before = self.normalize_optional_timestamp(before) if before else ""
        candidates = await self.export_episodes_by_user(
            collection_id=collection_id,
            user_key=user_key,
            include_statuses=include_statuses,
        )
        matched_ids = [
            episode["id"]
            for episode in candidates
            if self._episode_matches_bulk_filters(
                episode,
                sender_id=sender_id,
                tag=tag,
                before=normalized_before,
                include_statuses=include_statuses,
            )
        ]
        deleted = 0
        for episode_id in matched_ids:
            deleted += await self.delete_episode_by_id(
                collection_id=collection_id,
                episode_id=episode_id,
                user_key=user_key,
            )
        return deleted, matched_ids

    @staticmethod
    def _age_days(timestamp: str, now: datetime | None = None) -> float | None:
        text = str(timestamp or "").strip()
        if not text:
            return None
        try:
            ts = datetime.fromisoformat(text.replace("Z", "+00:00"))
        except (TypeError, ValueError):
            return None
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        now_dt = now or datetime.now(timezone.utc)
        return max(0.0, (now_dt - ts.astimezone(timezone.utc)).total_seconds() / 86400.0)

    @staticmethod
    def _summarize_consolidation_candidates(candidates: list[dict[str, Any]]) -> str:
        if not candidates:
            return ""

        tag_counts: dict[str, int] = {}
        sender_counts: dict[str, int] = {}
        for episode in candidates:
            for tag in episode.get("tags", []):
                tag_counts[tag] = tag_counts.get(tag, 0) + 1
            sender = episode.get("sender_name") or episode.get("sender_id") or ""
            if sender:
                sender_counts[sender] = sender_counts.get(sender, 0) + 1

        top_tags = sorted(tag_counts.items(), key=lambda item: item[1], reverse=True)[:5]
        top_senders = sorted(sender_counts.items(), key=lambda item: item[1], reverse=True)[:3]
        parts = [f"Consolidated {len(candidates)} older or hidden memory episodes."]
        if top_tags:
            parts.append(
                "Top tags: " + ", ".join(f"{tag} ({count})" for tag, count in top_tags)
            )
        if top_senders:
            parts.append(
                "Speakers: "
                + ", ".join(f"{sender} ({count})" for sender, count in top_senders)
            )
        return " ".join(parts)

    async def preview_consolidation(
        self,
        collection_id: str,
        user_key: str,
        *,
        min_age_days: int = 7,
        max_candidates: int = 20,
        apply_profile_updates: bool = False,
    ) -> dict[str, Any]:
        """Build a no-write consolidation preview for one user_key scope."""
        max_candidates = max(1, min(100, int(max_candidates or 20)))
        min_age_days = max(0, int(min_age_days or 0))
        episodes = await self.export_episodes_by_user(
            collection_id=collection_id,
            user_key=user_key,
            include_statuses=sorted(self.EPISODE_STATUSES),
        )

        candidates: list[dict[str, Any]] = []
        archive_ids: list[str] = []
        risk_notes: list[str] = []
        now = datetime.now(timezone.utc)
        for episode in episodes:
            status = episode.get("status", self.EPISODE_STATUS_ACTIVE)
            importance = int(episode.get("importance", 2) or 2)
            age_days = self._age_days(str(episode.get("timestamp", "") or ""), now)
            reasons: list[str] = []
            if status == self.EPISODE_STATUS_SUPERSEDED:
                reasons.append("already superseded")
            elif status == self.EPISODE_STATUS_ARCHIVED:
                reasons.append("already archived")
            elif (
                status == self.EPISODE_STATUS_ACTIVE
                and age_days is not None
                and age_days >= min_age_days
                and importance <= 2
            ):
                reasons.append(f"active low-importance memory older than {min_age_days} days")

            if not reasons:
                continue

            candidate = dict(episode)
            candidate["consolidation_reasons"] = reasons
            candidate["age_days"] = age_days
            candidates.append(candidate)
            if status != self.EPISODE_STATUS_ARCHIVED:
                archive_ids.append(episode["id"])
            if len(candidates) >= max_candidates:
                break

        if len(episodes) > len(candidates):
            risk_notes.append(
                f"Preview limited to {len(candidates)} candidate(s) from {len(episodes)} scoped episodes."
            )
        if not apply_profile_updates:
            risk_notes.append("Profile update application is disabled by default.")
        if archive_ids:
            risk_notes.append("Run will archive selected active/superseded episodes in this scope only.")

        summary_episode = ""
        if len(candidates) >= 2:
            summary_episode = self._summarize_consolidation_candidates(candidates)

        return {
            "candidate_episode_ids": [episode["id"] for episode in candidates],
            "candidates": candidates,
            "summary_episode": summary_episode,
            "profile_updates": [] if not apply_profile_updates else [],
            "episodes_to_archive": archive_ids,
            "risk_notes": risk_notes,
            "min_age_days": min_age_days,
            "max_candidates": max_candidates,
        }

    @serialized_write
    async def apply_consolidation(
        self,
        collection_id: str,
        embedding_model_uuid: str,
        user_key: str,
        *,
        min_age_days: int = 7,
        max_candidates: int = 20,
        apply_profile_updates: bool = False,
    ) -> dict[str, Any]:
        """Apply scoped consolidation by writing a summary and archiving candidates."""
        preview = await self.preview_consolidation(
            collection_id=collection_id,
            user_key=user_key,
            min_age_days=min_age_days,
            max_candidates=max_candidates,
            apply_profile_updates=apply_profile_updates,
        )
        archived: list[str] = []
        for episode_id in preview["episodes_to_archive"]:
            episode = await self.update_episode_status(
                collection_id=collection_id,
                embedding_model_uuid=embedding_model_uuid,
                episode_id=episode_id,
                user_key=user_key,
                status=self.EPISODE_STATUS_ARCHIVED,
            )
            if episode:
                archived.append(episode_id)

        summary = None
        if preview.get("summary_episode"):
            summary = await self.add_episode(
                collection_id=collection_id,
                embedding_model_uuid=embedding_model_uuid,
                user_key=user_key,
                content=preview["summary_episode"],
                tags=["consolidation", "summary"],
                importance=2,
                source="consolidation",
            )

        return {
            "preview": preview,
            "archived_episode_ids": archived,
            "summary_episode": summary,
            "profile_updates_applied": [],
        }

    @serialized_write
    async def delete_episode_by_id(
        self,
        collection_id: str,
        episode_id: str,
        user_key: str,
    ) -> int:
        """Delete a single episode by its ID, scoped to user_key for safety."""
        filters: dict[str, Any] = {
            "$and": [
                {"user_key": user_key},
            ]
        }
        return await self._writes.mutate(
            self.plugin,
            collection_id,
            lambda: self.plugin.vector_delete(
                collection_id=collection_id,
                file_ids=[episode_id],
                filters=filters,
            ),
            "Host vector_delete outcome unknown",
        )

    def _episode_from_vector_item(self, item: dict[str, Any]) -> dict[str, Any]:
        meta = item.get("metadata", {})
        return {
            "id": item.get("id", ""),
            "content": meta.get("content", "") or item.get("document", ""),
            "tags": meta.get("tags", "").split(",") if meta.get("tags") else [],
            "importance": int(meta.get("importance", "2")),
            "timestamp": meta.get("timestamp", ""),
            "sender_id": meta.get("sender_id", ""),
            "sender_name": meta.get("sender_name", ""),
            "source": meta.get("source", ""),
            "status": self.episode_status_from_metadata(meta),
            "superseded_by": meta.get("superseded_by", ""),
            "metadata": meta,
        }

    async def get_episode_by_id(
        self,
        collection_id: str,
        episode_id: str,
        user_key: str,
    ) -> dict[str, Any] | None:
        """Find a single episode by ID within the current user_key scope."""
        offset = 0
        batch_size = 100
        while True:
            result = await self.plugin.vector_list(
                collection_id=collection_id,
                filters={"user_key": user_key},
                limit=batch_size,
                offset=offset,
            )
            items = result.get("items", [])
            for item in items:
                if item.get("id") == episode_id:
                    return self._episode_from_vector_item(item)
            if not items or len(items) < batch_size:
                return None
            total = result.get("total", -1)
            offset += len(items)
            if total >= 0 and offset >= total:
                return None

    @serialized_write
    async def update_episode_status(
        self,
        collection_id: str,
        embedding_model_uuid: str,
        episode_id: str,
        user_key: str,
        status: str,
    ) -> dict[str, Any] | None:
        """Update an episode lifecycle status while preserving metadata."""
        normalized_status = self.normalize_episode_status_value(status)
        episode = await self.get_episode_by_id(
            collection_id=collection_id,
            episode_id=episode_id,
            user_key=user_key,
        )
        if not episode:
            return None

        meta = dict(episode.get("metadata", {}))
        content = episode.get("content", "")
        meta["content"] = content
        meta["status"] = normalized_status
        if normalized_status == self.EPISODE_STATUS_ACTIVE:
            meta.pop("superseded_by", None)

        vectors = await self.plugin.invoke_embedding(embedding_model_uuid, [content])
        await self._writes.mutate(
            self.plugin,
            collection_id,
            lambda: self.plugin.vector_upsert(
                collection_id=collection_id,
                vectors=vectors,
                ids=[episode_id],
                metadata=[meta],
                documents=[content],
            ),
            "Host vector_upsert outcome unknown",
        )
        updated = dict(episode)
        updated["status"] = normalized_status
        updated["metadata"] = meta
        updated["superseded_by"] = meta.get("superseded_by", "")
        return updated

    # ======================== formatting ========================

    @staticmethod
    def format_profile_prompt(
        profile: dict[str, Any],
        title: str = "## Memory (Profile)",
    ) -> str:
        if not MemoryStore.has_profile_data(profile):
            return ""

        parts: list[str] = []
        parts.append(title)

        if profile.get("name"):
            parts.append(f"- Name: {profile['name']}")
        if profile.get("traits"):
            parts.append(f"- Traits: {', '.join(profile['traits'])}")
        if profile.get("preferences"):
            parts.append(f"- Preferences: {', '.join(profile['preferences'])}")
        for hint in MemoryStore._format_recent_slot_change_hints(profile, max_items=3):
            parts.append(f"- {hint}")
        if profile.get("notes"):
            parts.append(f"- Notes: {profile['notes']}")
        if profile.get("updated_at"):
            parts.append(f"- Last updated: {profile['updated_at']}")

        return "\n".join(parts)

    # ======================== health probe ========================

    @staticmethod
    def _worse_status(current: str, candidate: str) -> str:
        rank = {"ERROR": 0, "WARN": 1, "OK": 2}
        return min(current, candidate, key=lambda s: rank.get(s, 1))

    @serialized_write
    async def run_metadata_filter_probe(
        self,
        collection_id: str,
        embedding_model_uuid: str,
    ) -> dict[str, Any]:
        """Probe whether the vector backend honours ``user_key`` metadata filters.

        Writes two temporary records under different ``user_key`` values, then
        verifies that search / list / delete with a scoped filter never leaks the
        other record. Returns a structured result so both the ``!memory health``
        command and the memory console can render it. The probe always cleans up
        its temporary records.
        """
        probe_id = uuid.uuid4().hex[:10]
        id_a = f"ltm-health-{probe_id}-a"
        id_b = f"ltm-health-{probe_id}-b"
        user_a = f"ltm-health:{probe_id}:a"
        user_b = f"ltm-health:{probe_id}:b"
        text_a = f"LongTermMemory health probe {probe_id} alpha"
        text_b = f"LongTermMemory health probe {probe_id} beta"
        ids = [id_a, id_b]

        checks: list[dict[str, str]] = []
        status = "OK"

        def add(check_id: str, check_status: str, detail: str) -> None:
            nonlocal status
            checks.append({"id": check_id, "status": check_status, "detail": detail})
            status = self._worse_status(status, check_status)

        try:
            vectors = await self.plugin.invoke_embedding(
                embedding_model_uuid,
                [text_a, text_b],
            )
            timestamp = self._now_timestamp()
            await self._writes.mutate(
                self.plugin,
                collection_id,
                lambda: self.plugin.vector_upsert(
                    collection_id=collection_id,
                    vectors=vectors,
                    ids=ids,
                    metadata=[
                        {
                            "content": text_a,
                            "user_key": user_a,
                            "source": "health_probe",
                            "timestamp": timestamp,
                        },
                        {
                            "content": text_b,
                            "user_key": user_b,
                            "source": "health_probe",
                            "timestamp": timestamp,
                        },
                    ],
                    documents=[text_a, text_b],
                ),
                "Host vector_upsert outcome unknown",
            )
            add("write", "OK", "wrote temporary metadata probe records")

            search_results = await self.plugin.vector_search(
                collection_id=collection_id,
                query_vector=vectors[0],
                top_k=5,
                filters={"user_key": user_a},
            )
            search_ids = {item.get("id") for item in search_results}
            if id_b in search_ids:
                add("search", "ERROR", "vector_search filter leaked another user_key result")
            elif id_a in search_ids:
                add("search", "OK", "vector_search respects user_key metadata filter")
            else:
                add("search", "WARN", "vector_search filter did not return its own probe record")

            try:
                listed = await self.plugin.vector_list(
                    collection_id=collection_id,
                    filters={"user_key": user_a},
                    limit=10,
                    offset=0,
                )
                list_ids = {item.get("id") for item in listed.get("items", [])}
                if id_b in list_ids:
                    add("list", "ERROR", "vector_list filter leaked another user_key result")
                elif id_a in list_ids:
                    add("list", "OK", "vector_list respects user_key metadata filter")
                else:
                    add("list", "WARN", "vector_list did not return its own probe record")
            except Exception as exc:
                add("list", "WARN", f"vector_list probe failed: {exc}")

            try:
                deleted = await self._writes.mutate(
                    self.plugin,
                    collection_id,
                    lambda: self.plugin.vector_delete(
                        collection_id=collection_id,
                        filters={"user_key": user_a},
                    ),
                    "Host vector_delete outcome unknown",
                )
                if deleted == 1:
                    add("delete", "OK", "vector_delete respects user_key metadata filter")
                elif deleted == 0:
                    add("delete", "WARN", "vector_delete filter did not delete its own probe record")
                else:
                    add("delete", "ERROR", "vector_delete filter deleted more probe records than expected")
            except Exception as exc:
                add("delete", "WARN", f"vector_delete filter probe failed: {exc}")
        except Exception as exc:
            add("probe", "ERROR", f"metadata filter probe failed: {exc}")
        finally:
            for episode_id in ids:
                try:
                    await self._writes.mutate(
                        self.plugin,
                        collection_id,
                        lambda: self.plugin.vector_delete(
                            collection_id=collection_id,
                            file_ids=[episode_id],
                        ),
                        "Host vector_delete outcome unknown",
                    )
                except Exception as exc:
                    add("cleanup", "WARN", f"failed to clean probe record {episode_id}: {exc}")

        return {"status": status, "checks": checks}
