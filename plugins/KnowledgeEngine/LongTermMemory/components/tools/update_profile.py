from __future__ import annotations

import logging
from typing import Any

from langbot_plugin.api.definition.components.tool.tool import Tool
from langbot_plugin.api.entities.builtin.provider import session as provider_session
from langbot_plugin.api.proxies.query_based_api import QueryBasedAPIProxy

logger = logging.getLogger(__name__)


class UpdateProfile(Tool):
    @staticmethod
    def _preview_text(value: str, max_len: int = 80) -> str:
        text = value.strip().replace("\n", " ")
        if len(text) <= max_len:
            return text
        return f"{text[:max_len]}..."

    @staticmethod
    def _normalize_scope(scope: Any) -> str:
        if scope is None or scope == "":
            return ""
        if not isinstance(scope, str):
            return "__invalid__"
        scope = scope.strip().lower()
        if scope in ("session", "speaker"):
            return scope
        return "__invalid__"

    @staticmethod
    def _infer_scope(field: str, explicit_scope: str) -> str:
        if explicit_scope:
            return explicit_scope
        # Default to speaker-scoped profiles for stable person facts,
        # and session-scoped notes for shared conversational context.
        if field in ("name", "traits", "preferences"):
            return "speaker"
        return "session"

    @staticmethod
    def _normalize_fact_key(value: Any) -> str:
        if value is None or value == "":
            return ""
        if not isinstance(value, str):
            return "__invalid__"
        return " ".join(value.strip().split())

    async def call(
        self,
        params: dict[str, Any],
        session: provider_session.Session,
        query_id: int,
    ) -> str:
        store = self.plugin.memory_store

        field = params.get("field", "")
        action = params.get("action", "")
        value = params.get("value", "")
        scope = self._normalize_scope(params.get("scope", ""))
        fact_key = self._normalize_fact_key(params.get("fact_key", ""))
        previous_value = params.get("previous_value", "")
        logger.info(
            "[LongTermMemory] update_profile called: query_id=%s field=%s action=%s scope=%s fact_key=%s has_previous_value=%s",
            query_id,
            field,
            action,
            scope,
            fact_key,
            bool(previous_value),
        )

        if not all([field, action, value]):
            return "Error: field, action, and value are all required."

        if field not in ("name", "traits", "preferences", "notes"):
            return f"Error: invalid field '{field}'."

        if action not in ("set", "add", "remove"):
            return f"Error: invalid action '{action}'."

        if scope == "__invalid__":
            return "Error: invalid scope. Use 'session' or 'speaker'."

        if fact_key == "__invalid__":
            return "Error: fact_key must be a string."

        if fact_key and field not in ("traits", "preferences"):
            return "Error: fact_key is only supported for 'traits' and 'preferences'."

        if previous_value is None:
            previous_value = ""
        if not isinstance(previous_value, str):
            return "Error: previous_value must be a string."

        api = QueryBasedAPIProxy(
            query_id=query_id,
            plugin_runtime_handler=self.plugin.plugin_runtime_handler,
        )
        bot_uuid = await api.get_bot_uuid()
        query_vars = await api.get_query_vars()
        sender_id = str(query_vars.get("sender_id", "") or "")
        sender_name = str(query_vars.get("sender_name", "") or "")

        session_key, user_key, kb_id, _isolation, _ = await store.resolve_user_context(
            session, bot_uuid
        )
        if not kb_id:
            return "Error: no memory knowledge base configured. Create one first."

        pipeline_kbs = await api.list_pipeline_knowledge_bases()
        if not any(kb.get("uuid") == kb_id for kb in pipeline_kbs):
            return "Error: memory knowledge base is not configured for the current pipeline."

        target_scope = self._infer_scope(field, scope)
        logger.info(
            "[LongTermMemory] update_profile resolved scope: query_id=%s target_scope=%s session_key=%s sender_id=%s value_len=%s",
            query_id,
            target_scope,
            session_key,
            sender_id,
            len(str(value)),
        )

        if target_scope == "speaker":
            if not sender_id:
                return "Error: current speaker is unavailable."
            profile = await store.update_speaker_profile_field(
                scope_key=session_key,
                sender_id=sender_id,
                field=field,
                action=action,
                value=value,
                fact_key=fact_key,
                previous_value=previous_value.strip(),
            )
        else:
            profile = await store.update_session_profile_field(
                scope_key=session_key,
                field=field,
                action=action,
                value=value,
                fact_key=fact_key,
                previous_value=previous_value.strip(),
            )

        logger.info(
            "[LongTermMemory] update_profile stored: query_id=%s target_scope=%s field=%s action=%s session_key=%s",
            query_id,
            target_scope,
            field,
            action,
            session_key,
        )
        target_id = session_key if target_scope == "session" else f"{session_key}:{sender_id}"
        await store.append_audit_entry(
            scope_key=session_key,
            user_key=user_key,
            operation="update_profile",
            target_type=f"{target_scope}_profile",
            target_id=target_id,
            summary=(
                f"{action} {target_scope} profile {field}"
                f"{f' ({fact_key})' if fact_key else ''}: {self._preview_text(str(value))}"
            ),
            sender_id=sender_id,
            sender_name=sender_name,
            query_id=query_id,
            metadata={
                "field": field,
                "action": action,
                "target_scope": target_scope,
                "fact_key": fact_key,
                "has_previous_value": bool(previous_value),
            },
        )

        return (
            f"{target_scope.capitalize()} profile updated.\n"
            + store.format_profile_text(profile)
        )
