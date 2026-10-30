from __future__ import annotations

import copy
import time
from typing import Any

from langbot_plugin.api.definition.components.page import Page, PageRequest, PageResponse


class MemoryConsolePage(Page):
    async def handle_api(self, request: PageRequest) -> PageResponse:
        try:
            if request.endpoint == "/summary" and request.method == "GET":
                return PageResponse.ok(await self._summary())
            if request.endpoint == "/derive-scope" and request.method == "POST":
                return PageResponse.ok(self._derive_scope(self._body(request)))
            if request.endpoint == "/profile" and request.method == "POST":
                return PageResponse.ok(await self._profile(self._body(request)))
            if request.endpoint == "/export-profiles" and request.method == "POST":
                return PageResponse.ok(await self._export_profiles(self._body(request)))
            if request.endpoint == "/episodes/list" and request.method == "POST":
                return PageResponse.ok(await self._list_episodes(self._body(request)))
            if request.endpoint == "/episodes/search" and request.method == "POST":
                return PageResponse.ok(await self._search_episodes(self._body(request)))
            if request.endpoint == "/episodes/export" and request.method == "POST":
                return PageResponse.ok(await self._export_episodes(self._body(request)))
            if request.endpoint == "/episodes/status" and request.method == "POST":
                return PageResponse.ok(await self._set_episode_status(self._body(request)))
            if request.endpoint == "/episodes/delete" and request.method == "POST":
                return PageResponse.ok(await self._delete_episode(self._body(request)))
            if request.endpoint == "/audit/list" and request.method == "POST":
                return PageResponse.ok(await self._list_audit(self._body(request)))
            if request.endpoint == "/audit/export" and request.method == "POST":
                return PageResponse.ok(await self._export_audit(self._body(request)))
            if request.endpoint == "/health" and request.method == "POST":
                return PageResponse.ok(await self._health(self._body(request)))
            if request.endpoint == "/injection" and request.method == "POST":
                return PageResponse.ok(await self._injection(self._body(request)))
            if request.endpoint == "/fences/clear" and request.method == "POST":
                return PageResponse.ok(await self._clear_fence(self._body(request)))

            return PageResponse.fail(f"Unknown endpoint: {request.method} {request.endpoint}")
        except ValueError as exc:
            return PageResponse.fail(str(exc))
        except Exception as exc:
            return PageResponse.fail(f"Memory console error: {exc}")

    @property
    def _store(self):
        return self.plugin.memory_store

    @staticmethod
    def _body(request: PageRequest) -> dict[str, Any]:
        if request.body is None:
            return {}
        if not isinstance(request.body, dict):
            raise ValueError("request body must be an object")
        return request.body

    @staticmethod
    def _string(body: dict[str, Any], key: str, default: str = "") -> str:
        value = body.get(key, default)
        if value is None:
            return default
        if not isinstance(value, str):
            raise ValueError(f"{key} must be a string")
        return value.strip()

    @classmethod
    def _required_string(cls, body: dict[str, Any], key: str) -> str:
        value = cls._string(body, key)
        if not value:
            raise ValueError(f"{key} is required")
        return value

    @staticmethod
    def _int(body: dict[str, Any], key: str, default: int, minimum: int, maximum: int) -> int:
        value = body.get(key, default)
        if value is None or value == "":
            return default
        if not isinstance(value, int):
            raise ValueError(f"{key} must be an integer")
        return max(minimum, min(maximum, value))

    @staticmethod
    def _public_profile(profile: dict[str, Any]) -> dict[str, Any]:
        public = copy.deepcopy(profile)
        public.pop("profile_slots", None)
        public.pop("freeform_traits", None)
        public.pop("freeform_preferences", None)
        return public

    def _statuses(self, body: dict[str, Any]) -> list[str] | None:
        raw = body.get("statuses")
        if raw is None:
            return None
        if not isinstance(raw, list):
            raise ValueError("statuses must be a list")
        statuses = []
        for item in raw:
            status = str(item).strip().lower()
            if status not in self._store.EPISODE_STATUSES:
                raise ValueError(
                    "statuses must contain only active, superseded, archived, or deleted"
                )
            statuses.append(status)
        return statuses or None

    async def _summary(self) -> dict[str, Any]:
        store = self._store
        kb_configs = await store.get_kb_configs()
        storage_keys = await self.plugin.get_plugin_storage_keys()
        profile_keys = [key for key in storage_keys if key.startswith(("ps:", "pp:"))]
        kb_entries = [
            {
                "id": kb_id,
                "embedding_model_uuid": str(config.get("embedding_model_uuid", "") or ""),
                "isolation": str(config.get("isolation", "session") or "session"),
                "config": config,
            }
            for kb_id, config in kb_configs.items()
        ]
        return {
            "plugin_config": self.plugin.get_config(),
            "kb_configs": kb_configs,
            "kb_entries": kb_entries,
            "kb_count": len(kb_configs),
            "profile_key_count": len(profile_keys),
            "session_profile_count": len([key for key in profile_keys if key.startswith("ps:")]),
            "speaker_profile_count": len([key for key in profile_keys if key.startswith("pp:")]),
            "fences": await store.list_fences(),
            "scopes": self._profile_scopes(profile_keys, kb_entries[0]["isolation"] if kb_entries else "session"),
        }

    @staticmethod
    def _profile_scopes(profile_keys: list[str], isolation: str) -> list[dict[str, Any]]:
        scopes: dict[str, dict[str, Any]] = {}
        for key in profile_keys:
            if key.startswith("ps:"):
                scope_key = key[3:]
                entry = scopes.setdefault(scope_key, {
                    "scope_key": scope_key,
                    "user_key": MemoryConsolePage._infer_user_key(scope_key, isolation),
                    "has_session_profile": False,
                    "speaker_ids": [],
                    "speaker_count": 0,
                })
                entry["has_session_profile"] = True
                continue

            if key.startswith("pp:"):
                rest = key[3:]
                scope_key, separator, sender_id = rest.rpartition(":")
                if not separator or not scope_key or not sender_id:
                    continue
                entry = scopes.setdefault(scope_key, {
                    "scope_key": scope_key,
                    "user_key": MemoryConsolePage._infer_user_key(scope_key, isolation),
                    "has_session_profile": False,
                    "speaker_ids": [],
                    "speaker_count": 0,
                })
                if sender_id not in entry["speaker_ids"]:
                    entry["speaker_ids"].append(sender_id)
                entry["speaker_count"] = len(entry["speaker_ids"])

        return sorted(scopes.values(), key=lambda item: item["scope_key"])

    @staticmethod
    def _infer_user_key(scope_key: str, isolation: str) -> str:
        if isolation == "session":
            return scope_key
        if ":" in scope_key:
            return f"bot:{scope_key.split(':', 1)[0]}"
        return "global"

    def _derive_scope(self, body: dict[str, Any]) -> dict[str, str]:
        bot_uuid = self._string(body, "bot_uuid")
        session_name = self._required_string(body, "session_name")
        isolation = self._string(body, "isolation", "session") or "session"
        if isolation not in ("session", "bot"):
            raise ValueError("isolation must be session or bot")

        launcher_type, launcher_id = self._store.split_session_name(session_name)
        session_key = self._store.get_session_key(bot_uuid, launcher_type, launcher_id)
        user_key = self._store.get_user_key(session_key, isolation, bot_uuid)
        return {
            "session_key": session_key,
            "user_key": user_key,
            "launcher_type": launcher_type,
            "launcher_id": launcher_id,
            "isolation": isolation,
        }

    async def _profile(self, body: dict[str, Any]) -> dict[str, Any]:
        scope_key = self._required_string(body, "scope_key")
        sender_id = self._string(body, "sender_id")

        session_profile = await self._read_profile(
            self._store._session_profile_key(scope_key)
        )
        speaker_profile = (
            await self._read_profile(self._store._speaker_profile_key(scope_key, sender_id))
            if sender_id
            else None
        )
        return {
            "scope_key": scope_key,
            "sender_id": sender_id,
            "session_profile": self._public_profile(session_profile),
            "speaker_profile": self._public_profile(speaker_profile) if speaker_profile else None,
        }

    async def _read_profile(self, storage_key: str) -> dict[str, Any]:
        profile = await self._store._read_json(storage_key)
        if not profile:
            return {}
        return self._store._normalize_profile(profile)

    async def _export_profiles(self, body: dict[str, Any]) -> dict[str, Any]:
        scope_key = self._required_string(body, "scope_key")
        user_key = self._string(body, "user_key")
        profiles = await self._store.export_profiles_by_scope(scope_key)
        await self._store.append_audit_entry(
            scope_key=scope_key,
            user_key=user_key,
            operation="export_profiles",
            target_type="profile",
            target_id=scope_key,
            summary=f"Exported {len(profiles)} L1 profile entries from memory console",
        )
        return {
            "version": 1,
            "exported_at": self._now(),
            "scope_key": scope_key,
            "user_key": user_key,
            "profiles": profiles,
            "count": len(profiles),
        }

    async def _list_episodes(self, body: dict[str, Any]) -> dict[str, Any]:
        collection_id = self._required_string(body, "collection_id")
        user_key = self._required_string(body, "user_key")
        page = self._int(body, "page", 1, 1, 100000)
        page_size = self._int(body, "page_size", 10, 1, 50)
        offset = (page - 1) * page_size

        episodes, total = await self._store.list_episodes(
            collection_id=collection_id,
            user_key=user_key,
            limit=page_size,
            offset=offset,
            include_statuses=self._statuses(body),
        )
        return {
            "episodes": episodes,
            "total": total,
            "page": page,
            "page_size": page_size,
        }

    async def _search_episodes(self, body: dict[str, Any]) -> dict[str, Any]:
        collection_id = self._required_string(body, "collection_id")
        embedding_model_uuid = self._required_string(body, "embedding_model_uuid")
        user_key = self._required_string(body, "user_key")
        query = self._required_string(body, "query")
        top_k = self._int(body, "top_k", 10, 1, 50)
        importance_min = body.get("importance_min")
        if importance_min in ("", None):
            importance_min = None
        elif not isinstance(importance_min, int) or not 1 <= importance_min <= 5:
            raise ValueError("importance_min must be an integer between 1 and 5")

        episodes = await self._store.search_episodes(
            collection_id=collection_id,
            embedding_model_uuid=embedding_model_uuid,
            query=query,
            user_key=user_key,
            top_k=top_k,
            sender_id=self._string(body, "sender_id"),
            sender_name=self._string(body, "sender_name"),
            time_after=self._string(body, "time_after"),
            time_before=self._string(body, "time_before"),
            importance_min=importance_min,
            source=self._string(body, "source"),
            include_statuses=self._statuses(body),
        )
        return {"episodes": episodes, "count": len(episodes)}

    async def _export_episodes(self, body: dict[str, Any]) -> dict[str, Any]:
        collection_id = self._required_string(body, "collection_id")
        scope_key = self._required_string(body, "scope_key")
        user_key = self._required_string(body, "user_key")
        include_statuses = self._statuses(body)

        exported: list[dict[str, Any]] = []
        offset = 0
        page_size = 100
        while True:
            episodes, total = await self._store.list_episodes(
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

        await self._store.append_audit_entry(
            scope_key=scope_key,
            user_key=user_key,
            operation="export_l2",
            target_type="episode",
            target_id=scope_key,
            summary=f"Exported {len(exported)} L2 episodes from memory console",
            metadata={"collection_id": collection_id, "statuses": include_statuses},
        )
        return {
            "version": 1,
            "exported_at": self._now(),
            "scope_key": scope_key,
            "user_key": user_key,
            "collection_id": collection_id,
            "statuses": include_statuses or [self._store.EPISODE_STATUS_ACTIVE],
            "episodes": exported,
            "count": len(exported),
        }

    async def _set_episode_status(self, body: dict[str, Any]) -> dict[str, Any]:
        collection_id = self._required_string(body, "collection_id")
        embedding_model_uuid = self._required_string(body, "embedding_model_uuid")
        scope_key = self._required_string(body, "scope_key")
        user_key = self._required_string(body, "user_key")
        episode_id = self._required_string(body, "episode_id")
        status = self._required_string(body, "status").lower()
        if status not in self._store.EPISODE_STATUSES:
            raise ValueError("status must be active, superseded, archived, or deleted")

        episode = await self._store.update_episode_status(
            collection_id=collection_id,
            embedding_model_uuid=embedding_model_uuid,
            episode_id=episode_id,
            user_key=user_key,
            status=status,
        )
        if not episode:
            raise ValueError(f"episode not found: {episode_id}")

        operation = "restore" if status == self._store.EPISODE_STATUS_ACTIVE else status
        await self._store.append_audit_entry(
            scope_key=scope_key,
            user_key=user_key,
            operation=operation,
            target_type="episode",
            target_id=episode_id,
            summary=f"Set episode {episode_id} status to {status} from memory console",
            metadata={"collection_id": collection_id, "status": status},
        )
        return {"episode": episode}

    async def _delete_episode(self, body: dict[str, Any]) -> dict[str, Any]:
        collection_id = self._required_string(body, "collection_id")
        scope_key = self._required_string(body, "scope_key")
        user_key = self._required_string(body, "user_key")
        episode_id = self._required_string(body, "episode_id")
        deleted = await self._store.delete_episode_by_id(
            collection_id=collection_id,
            episode_id=episode_id,
            user_key=user_key,
        )
        await self._store.append_audit_entry(
            scope_key=scope_key,
            user_key=user_key,
            operation="delete",
            target_type="episode",
            target_id=episode_id,
            summary=f"Deleted episode {episode_id} from memory console",
            metadata={"collection_id": collection_id, "deleted": deleted},
        )
        return {"episode_id": episode_id, "deleted": deleted}

    async def _list_audit(self, body: dict[str, Any]) -> dict[str, Any]:
        scope_key = self._required_string(body, "scope_key")
        page = self._int(body, "page", 1, 1, 100000)
        page_size = self._int(body, "page_size", 10, 1, 100)
        offset = (page - 1) * page_size
        entries, total = await self._store.list_audit_entries(
            scope_key,
            limit=page_size,
            offset=offset,
        )
        return {
            "entries": entries,
            "total": total,
            "page": page,
            "page_size": page_size,
        }

    async def _export_audit(self, body: dict[str, Any]) -> dict[str, Any]:
        scope_key = self._required_string(body, "scope_key")
        user_key = self._string(body, "user_key")
        entries = await self._store.export_audit_entries(scope_key)
        await self._store.append_audit_entry(
            scope_key=scope_key,
            user_key=user_key,
            operation="audit_export",
            target_type="audit",
            target_id=scope_key,
            summary=f"Exported {len(entries)} audit entries from memory console",
        )
        return {
            "version": 1,
            "exported_at": self._now(),
            "scope_key": scope_key,
            "user_key": user_key,
            "entries": entries,
            "count": len(entries),
        }

    async def _health(self, body: dict[str, Any]) -> dict[str, Any]:
        collection_id = self._required_string(body, "collection_id")
        embedding_model_uuid = self._string(body, "embedding_model_uuid")

        checks: list[dict[str, str]] = []
        statuses: list[str] = []

        def add(check_id: str, status: str, detail: str) -> None:
            checks.append({"id": check_id, "status": status, "detail": detail})
            statuses.append(status)

        kb_configs = await self._store.get_kb_configs()
        if collection_id in kb_configs:
            add("kb_config", "OK", f"memory KB configured: {collection_id}")
            if not embedding_model_uuid:
                embedding_model_uuid = str(
                    kb_configs[collection_id].get("embedding_model_uuid", "") or ""
                )
        else:
            add("kb_config", "ERROR", f"memory KB is not configured: {collection_id}")

        if embedding_model_uuid:
            add("embedding", "OK", f"embedding model configured: {embedding_model_uuid}")
        else:
            add("embedding", "ERROR", "no embedding model configured")

        if collection_id in kb_configs and embedding_model_uuid:
            probe = await self._store.run_metadata_filter_probe(
                collection_id=collection_id,
                embedding_model_uuid=embedding_model_uuid,
            )
            checks.extend(probe.get("checks", []))
            statuses.append(probe.get("status", "WARN"))
        else:
            add(
                "probe",
                "WARN",
                "metadata filter probe skipped because prerequisites failed",
            )

        return {
            "status": self._combine_status(statuses),
            "checks": checks,
            "checked_at": self._now(),
            "note": (
                "Pipeline activation is not verified from the console; run "
                "!memory health in a pipeline to confirm the KB is attached."
            ),
        }

    async def _injection(self, body: dict[str, Any]) -> dict[str, Any]:
        scope_key = self._required_string(body, "scope_key")
        snapshot = await self._store.get_injection_snapshot(scope_key)
        return {"scope_key": scope_key, "snapshot": snapshot}

    async def _clear_fence(self, body: dict[str, Any]) -> dict[str, Any]:
        """Acknowledge reconciliation for the selected memory scope(s).

        A Host write whose outcome was unknown leaves its memory scope fenced, so
        every later write to it fails closed. After the operator has inspected the
        affected records, this is the path back to a writable space / KB. The
        installation-wide scope is only cleared on an explicit request, because it
        blocks every memory scope of the installation.
        """
        identities: list[str | None] = []
        for key in ("scope_key", "collection_id"):
            identity = self._string(body, key)
            if identity and identity not in identities:
                identities.append(identity)
        if bool(body.get("installation")):
            identities.append(None)
        if not identities:
            raise ValueError("scope_key, collection_id, or installation is required")

        for identity in identities:
            await self._store.clear_fence(identity)
        return {"cleared": [identity if identity is not None else "installation" for identity in identities]}

    @staticmethod
    def _combine_status(statuses: list[str]) -> str:
        if not statuses:
            return "WARN"
        rank = {"ERROR": 0, "WARN": 1, "OK": 2}
        return min(statuses, key=lambda s: rank.get(s, 1))

    @staticmethod
    def _now() -> str:
        return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
