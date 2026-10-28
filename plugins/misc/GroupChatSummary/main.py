from __future__ import annotations

import asyncio
import json
import logging
import os
import time
from collections import defaultdict
from typing import Any

from langbot_plugin.api.definition.plugin import BasePlugin
from langbot_plugin.api.entities.builtin.platform import message as platform_message
from langbot_plugin.api.entities.builtin.provider import message as provider_message
from langbot_plugin.api.proxies.invocation import (
    bind_invocation,
    current_binding,
    current_config,
)

BUFFERS_KEY = "message_buffers"
WATERMARK_KEY = "auto_summary_watermark"

# Process-cache slot used when no installation binding is available (dedicated
# placement). It maps to the legacy storage keys so existing dedicated installs
# keep reading their own rows.
DEDICATED_SCOPE = "dedicated"

# Written by the SDK worker launcher. A shared worker must always carry a trusted
# invocation binding; without one it must refuse to touch tenant state instead of
# falling back to a binding-less scope shared by every installation.
RUNTIME_PROFILE_ENV = "LANGBOT_PLUGIN_RUNTIME_PROFILE"


def installation_scope(binding) -> str:
    """Return the stable scope token for one installation binding.

    ``runtime_revision`` changes on every worker upgrade, so only the stable
    installation identity triple is used; including it would orphan persisted
    rows and make the revoked binding impossible to release.
    """

    return f"{binding.instance_uuid}:{binding.workspace_uuid}:{binding.installation_uuid}"


def storage_key(scope: str, name: str) -> str:
    """Return the plugin-storage key for one scope.

    Host rows are keyed by ``[instance, workspace, owner_type, owner, key]`` with
    no installation dimension, so the installation scope has to live in the
    plugin's own key. The binding-less dedicated scope keeps the legacy key.
    """

    if scope == DEDICATED_SCOPE:
        return name
    return f"{name}:{scope}"


class _InstallationState:
    """Process-local buffers belonging to exactly one installation binding.

    The same object graph serves every installation of the artifact, so this is
    cached per binding and dropped in ``on_installation_revoked``.
    """

    __slots__ = ("scope", "message_buffer", "auto_summary_watermark", "lock", "loaded")

    def __init__(self, scope: str) -> None:
        self.scope = scope
        # {group_key: [{"sender": str, "text": str, "time": float}, ...]}
        self.message_buffer: dict[str, list[dict[str, Any]]] = defaultdict(list)
        # {group_key: last_auto_summary_index}
        self.auto_summary_watermark: dict[str, int] = {}
        self.lock = asyncio.Lock()
        self.loaded = False


class GroupChatSummary(BasePlugin):
    """Group chat message collector and summarizer.

    Collects messages from group chats and provides LLM-powered summaries
    via commands, tool calls, or automatic triggers. Buffers are kept per
    installation binding and loaded lazily per invocation, so the command, tool
    and listener components sharing this object always see the invoking
    installation's own groups.
    """

    def __init__(self):
        super().__init__()
        self._states: dict[str, _InstallationState] = {}
        self._tasks: dict[str, set[asyncio.Task]] = {}
        self.logger = logging.getLogger(__name__)

    # ------------------------------------------------------------- lifecycle

    async def initialize(self) -> None:
        """Process-wide initialization only.

        Under shared placement this runs once per worker with an empty config and
        no installation context, so tenant buffers are loaded lazily per
        invocation (and per binding) instead.
        """
        return None

    async def on_installation_revoked(self, binding) -> None:
        """Drop the revoked installation's buffers and stop its detached tasks.

        There is no active invocation, so no Host API is available; only the
        process-local cache and task registry keyed by this binding are released.
        """
        scope = installation_scope(binding)
        self._states.pop(scope, None)
        tasks = self._tasks.pop(scope, None) or set()
        for task in tasks:
            task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    async def destroy(self) -> None:
        """Stop every detached task and drop every cached installation (process end)."""
        pending = [task for tasks in self._tasks.values() for task in tasks]
        self._tasks.clear()
        self._states.clear()
        for task in pending:
            task.cancel()
        if pending:
            await asyncio.gather(*pending, return_exceptions=True)

    # ------------------------------------------------------------ state scope

    def _current_scope(self) -> str:
        binding = self.get_installation_binding()
        if binding is not None:
            return installation_scope(binding)
        if os.environ.get(RUNTIME_PROFILE_ENV) == "shared":
            raise RuntimeError(
                "shared invocation has no trusted installation binding; "
                "refusing to read or write tenant state"
            )
        return DEDICATED_SCOPE

    def _state_sync(self) -> _InstallationState:
        scope = self._current_scope()
        st = self._states.get(scope)
        if st is None:
            st = _InstallationState(scope)
            self._states[scope] = st
        return st

    async def _state(self) -> _InstallationState:
        """Return the invoking installation's state, loading it on first use."""
        st = self._state_sync()
        if not st.loaded:
            async with st.lock:
                if not st.loaded:
                    await self._load(st)
                    st.loaded = True
        return st

    async def ensure_loaded(self) -> None:
        """Load the invoking installation's persisted buffers on demand."""
        await self._state()

    @property
    def message_buffer(self) -> dict[str, list[dict[str, Any]]]:
        """Buffers of the invoking installation (empty until loaded)."""
        return self._state_sync().message_buffer

    @property
    def auto_summary_watermark(self) -> dict[str, int]:
        """Auto-summary watermarks of the invoking installation."""
        return self._state_sync().auto_summary_watermark

    async def _load(self, st: _InstallationState) -> None:
        """Load persisted buffers for one installation scope."""
        try:
            data = await self.get_plugin_storage(storage_key(st.scope, BUFFERS_KEY))
            if data:
                loaded = json.loads(data.decode("utf-8"))
                for k, v in loaded.items():
                    st.message_buffer[k] = v
                self.logger.info(
                    f"Loaded message buffers for {len(loaded)} groups "
                    f"(scope={st.scope})"
                )
        except Exception:
            self.logger.info("No persisted message buffers found, starting fresh")

        try:
            data = await self.get_plugin_storage(storage_key(st.scope, WATERMARK_KEY))
            if data:
                st.auto_summary_watermark = json.loads(data.decode("utf-8"))
        except Exception:
            pass

    def _group_key(self, launcher_type: str, launcher_id: str | int) -> str:
        """Generate a unique key for a group."""
        return f"{launcher_type}_{launcher_id}"

    def _get_max_messages(self) -> int:
        config = self.get_config()
        return config.get("max_messages", 500)

    def _get_default_summary_count(self) -> int:
        config = self.get_config()
        return config.get("default_summary_count", 100)

    async def record_message(
        self,
        launcher_type: str,
        launcher_id: str | int,
        sender_id: str | int,
        sender_name: str,
        text: str,
        bot_uuid: str | None = None,
    ) -> None:
        """Record a group message into the buffer.

        Args:
            launcher_type: "group" or "person"
            launcher_id: Group ID
            sender_id: Sender's user ID
            sender_name: Display name of sender
            text: Message text content
            bot_uuid: Bot UUID for auto-summary
        """
        if not text or not text.strip():
            return

        st = await self._state()
        key = self._group_key(launcher_type, launcher_id)
        max_messages = self._get_max_messages()

        st.message_buffer[key].append({
            "sender_id": str(sender_id),
            "sender": sender_name or str(sender_id),
            "text": text.strip(),
            "time": time.time(),
        })

        # Trim buffer if too large
        if len(st.message_buffer[key]) > max_messages:
            st.message_buffer[key] = st.message_buffer[key][-max_messages:]

        # Persist periodically (every 10 messages)
        if len(st.message_buffer[key]) % 10 == 0:
            await self._persist_buffers()

        # Check auto-summary trigger
        config = self.get_config()
        if config.get("auto_summary_enabled", False) and bot_uuid:
            threshold = config.get("auto_summary_threshold", 200)
            watermark = st.auto_summary_watermark.get(key, 0)
            current_count = len(st.message_buffer[key])

            if current_count - watermark >= threshold:
                st.auto_summary_watermark[key] = current_count
                await self._persist_watermark()
                # Fire auto-summary under the invoking binding, tracked for revocation.
                self._spawn_auto_summary(
                    st.scope, key, bot_uuid, launcher_type, str(launcher_id)
                )

    def _spawn_auto_summary(
        self,
        scope: str,
        group_key: str,
        bot_uuid: str,
        target_type: str,
        target_id: str,
    ) -> None:
        """Run one auto-summary bound to the invoking installation.

        The SDK does not track detached work, so the task is recorded under its
        installation scope and cancelled by ``on_installation_revoked``; it
        re-enters an invocation scope carrying the captured config and binding so
        its Host calls cannot escape to another tenant.
        """
        handler = getattr(self, "plugin_runtime_handler", None)
        config = current_config(handler)
        binding = current_binding(handler)

        async def run() -> None:
            with bind_invocation(handler, config=config, binding=binding):
                await self._auto_summarize(
                    group_key, bot_uuid, target_type, target_id
                )

        task = asyncio.create_task(run())
        tasks = self._tasks.setdefault(scope, set())
        tasks.add(task)

        def _discard(_task: asyncio.Task) -> None:
            remaining = self._tasks.get(scope)
            if remaining is None:
                return
            remaining.discard(_task)
            if not remaining:
                self._tasks.pop(scope, None)

        task.add_done_callback(_discard)

    async def _persist_buffers(self) -> None:
        """Persist the invoking installation's message buffers to plugin storage."""
        st = self._state_sync()
        try:
            data = json.dumps(dict(st.message_buffer), ensure_ascii=False)
            await self.set_plugin_storage(
                storage_key(st.scope, BUFFERS_KEY), data.encode("utf-8")
            )
        except Exception as e:
            self.logger.error(f"Failed to persist message buffers: {e}")

    async def _persist_watermark(self) -> None:
        """Persist the invoking installation's auto-summary watermark."""
        st = self._state_sync()
        try:
            data = json.dumps(st.auto_summary_watermark, ensure_ascii=False)
            await self.set_plugin_storage(
                storage_key(st.scope, WATERMARK_KEY), data.encode("utf-8")
            )
        except Exception as e:
            self.logger.error(f"Failed to persist watermark: {e}")

    def get_recent_messages(
        self,
        launcher_type: str,
        launcher_id: str | int,
        count: int | None = None,
        hours: float | None = None,
    ) -> list[dict[str, Any]]:
        """Get recent messages from a group.

        Args:
            launcher_type: "group" or "person"
            launcher_id: Group ID
            count: Number of recent messages (default from config)
            hours: Filter messages from last N hours

        Returns:
            List of message dicts
        """
        key = self._group_key(launcher_type, launcher_id)
        messages = self.message_buffer.get(key, [])

        if hours is not None:
            cutoff = time.time() - hours * 3600
            messages = [m for m in messages if m["time"] >= cutoff]

        if count is not None:
            messages = messages[-count:]
        else:
            default_count = self._get_default_summary_count()
            messages = messages[-default_count:]

        return messages

    def get_message_count(self, launcher_type: str, launcher_id: str | int) -> int:
        """Get the number of stored messages for a group."""
        key = self._group_key(launcher_type, launcher_id)
        return len(self.message_buffer.get(key, []))

    def _get_summary_language(self) -> str:
        config = self.get_config()
        lang = config.get("language", "zh_Hans")
        lang_map = {
            "zh_Hans": "Chinese (Simplified)",
            "en_US": "English",
            "ja_JP": "Japanese",
        }
        return lang_map.get(lang, "Chinese (Simplified)")

    def build_summary_prompt(
        self, messages: list[dict[str, Any]], language: str | None = None
    ) -> str:
        """Build the LLM prompt for summarizing messages.

        Args:
            messages: List of message dicts
            language: Override language for summary

        Returns:
            Formatted prompt string
        """
        if not language:
            language = self._get_summary_language()

        # Format messages into readable text
        lines = []
        for msg in messages:
            ts = time.strftime("%H:%M", time.localtime(msg["time"]))
            lines.append(f"[{ts}] {msg['sender']}: {msg['text']}")

        chat_log = "\n".join(lines)

        prompt = f"""Please summarize the following group chat conversation. 
Focus on:
1. Key topics discussed
2. Important decisions or conclusions
3. Action items or tasks mentioned
4. Notable opinions or disagreements

Output the summary in {language}.
Keep it concise but comprehensive. Use bullet points for clarity.
If there are multiple topics, group them with headers.

---
Chat Log ({len(messages)} messages):
{chat_log}
---"""
        return prompt

    async def generate_summary(
        self,
        launcher_type: str,
        launcher_id: str | int,
        count: int | None = None,
        hours: float | None = None,
    ) -> str:
        """Generate a summary using LLM.

        Args:
            launcher_type: "group" or "person"
            launcher_id: Group ID
            count: Number of messages to summarize
            hours: Summarize messages from last N hours

        Returns:
            Summary text
        """
        await self._state()
        messages = self.get_recent_messages(launcher_type, launcher_id, count, hours)

        if not messages:
            return self._get_no_messages_text()

        if len(messages) < 3:
            return self._get_too_few_messages_text(len(messages))

        prompt = self.build_summary_prompt(messages)

        # Use LLM to generate summary
        try:
            # Use configured model or fall back to first available
            configured_model = self.get_config().get("model")
            if configured_model:
                llm_model_uuid = configured_model
            else:
                llm_models = await self.get_llm_models()
                if not llm_models:
                    return "Error: No LLM model available."
                llm_model_uuid = llm_models[0]

            response = await self.invoke_llm(
                llm_model_uuid=llm_model_uuid,
                messages=[
                    provider_message.Message(
                        role="user",
                        content=[provider_message.ContentElement.from_text(prompt)],
                    )
                ],
            )

            # Extract text from response
            if response.content:
                if isinstance(response.content, str):
                    return response.content
                elif isinstance(response.content, list):
                    parts = []
                    for elem in response.content:
                        if hasattr(elem, "text") and elem.text:
                            parts.append(elem.text)
                    return "\n".join(parts) if parts else "Failed to generate summary."

            return "Failed to generate summary."

        except Exception as e:
            self.logger.error(f"LLM invocation failed: {e}", exc_info=True)
            return f"Error generating summary: {str(e)}"

    async def _auto_summarize(
        self,
        group_key: str,
        bot_uuid: str,
        target_type: str,
        target_id: str,
    ) -> None:
        """Auto-summarize and send to group."""
        try:
            parts = group_key.split("_", 1)
            if len(parts) != 2:
                return

            launcher_type, launcher_id = parts

            summary = await self.generate_summary(
                launcher_type=launcher_type,
                launcher_id=launcher_id,
            )

            config = self.get_config()
            lang = config.get("language", "zh_Hans")
            prefix = "📋 Auto Summary" if lang == "en_US" else "📋 自动总结"

            message_chain = platform_message.MessageChain([
                platform_message.Plain(text=f"{prefix}\n\n{summary}")
            ])

            await self.send_message(
                bot_uuid=bot_uuid,
                target_type=target_type,
                target_id=target_id,
                message_chain=message_chain,
            )
        except Exception as e:
            self.logger.error(f"Auto-summary failed: {e}", exc_info=True)

    def _get_no_messages_text(self) -> str:
        config = self.get_config()
        lang = config.get("language", "zh_Hans")
        if lang == "en_US":
            return "No messages recorded in this group yet."
        elif lang == "ja_JP":
            return "このグループにはまだメッセージが記録されていません。"
        return "当前群聊还没有记录到消息。"

    def _get_too_few_messages_text(self, count: int) -> str:
        config = self.get_config()
        lang = config.get("language", "zh_Hans")
        if lang == "en_US":
            return f"Only {count} messages recorded, too few to summarize meaningfully."
        elif lang == "ja_JP":
            return f"メッセージが {count} 件しか記録されていません。要約するには少なすぎます。"
        return f"仅记录了 {count} 条消息，内容太少无法生成有意义的总结。"

    def __del__(self):
        for tasks in getattr(self, "_tasks", {}).values():
            for task in tasks:
                if not task.done():
                    task.cancel()
        logger = getattr(self, "logger", None)
        if logger is not None:
            logger.info("GroupChatSummary plugin unloaded")
