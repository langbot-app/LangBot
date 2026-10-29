from __future__ import annotations

from typing import Any

from langbot_plugin.api.definition.components.tool.tool import Tool
from langbot_plugin.api.entities.builtin.provider import session as provider_session


class SummarizeGroupChat(Tool):
    """LLM tool for summarizing group chat messages.

    The LLM can call this tool when a user asks for a chat summary.
    """

    async def call(
        self,
        params: dict[str, Any],
        session: provider_session.Session,
        query_id: int,
    ) -> str:
        """Generate a group chat summary.

        Args:
            params: {
                "count": (optional) Number of messages to summarize,
                "hours": (optional) Summarize messages from last N hours
            }
            session: Current session
            query_id: Query ID

        Returns:
            Summary text
        """
        if session.launcher_type.value != "group":
            return "This tool can only be used in group chats."

        count = params.get("count")
        hours = params.get("hours")

        if count is not None:
            try:
                count = int(count)
                if count <= 0:
                    return "Message count must be positive."
                if count > 1000:
                    count = 1000
            except (ValueError, TypeError):
                return "Invalid count parameter."

        if hours is not None:
            try:
                hours = float(hours)
                if hours <= 0:
                    return "Hours must be positive."
            except (ValueError, TypeError):
                return "Invalid hours parameter."

        await self.plugin.ensure_loaded()
        msg_count = self.plugin.get_message_count(
            session.launcher_type.value, session.launcher_id
        )

        if msg_count == 0:
            return self.plugin._get_no_messages_text()

        summary = await self.plugin.generate_summary(
            launcher_type=session.launcher_type.value,
            launcher_id=session.launcher_id,
            count=count,
            hours=hours,
        )

        return summary
