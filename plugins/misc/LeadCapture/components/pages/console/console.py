from __future__ import annotations

from langbot_plugin.api.definition.components.page import Page, PageRequest, PageResponse

from main import role_label, stored_text, utc_label

MAX_SESSIONS = 500
CONVERSATION_MESSAGES = 30


def summarize(row: dict) -> dict:
    events = row.get("events") or []
    judges = [event for event in events if event.get("kind") == "judge"]
    last_judge = judges[-1] if judges else {}
    return {
        "key": row["key"],
        "bot": row.get("bot", ""),
        "user": row.get("user", ""),
        "status": row.get("status", "idle"),
        "judgments": len(judges),
        "strong_judgments": sum(1 for event in judges if event.get("strong")),
        "errors": sum(1 for event in events if event.get("kind") == "error"),
        "last_judged_at": last_judge.get("at"),
        "last_strong": last_judge.get("strong"),
        "last_reason": last_judge.get("reason", ""),
        "score": row.get("score", last_judge.get("score")),
        "level": row.get("level", last_judge.get("level", "")),
        "fields": row.get("fields") or {},
        "reason": row.get("reason", ""),
        "contact": row.get("contact", ""),
        "email_status": row.get("email_status", ""),
        "updated_at": row.get("updated_at") or (events[-1]["at"] if events else row.get("asked_at")),
    }


class ConsolePage(Page):
    """Read-only view of every conversation's purchase-intent judgments."""

    async def handle_api(self, request: PageRequest) -> PageResponse:
        plugin = self.plugin
        if request.endpoint == "/sessions":
            rows = sorted(
                (summarize(row) for row in await plugin.list_leads()),
                key=lambda item: item["updated_at"] or 0, reverse=True,
            )
            totals = {
                "sessions": len(rows),
                "asked": sum(1 for row in rows if row["status"] == "asked"),
                "risk": sum(1 for row in rows if row["status"] == "risk"),
                "captured": sum(1 for row in rows if row["status"] == "captured"),
                "emailed": sum(1 for row in rows if row["email_status"] == "sent"),
                "judgments": sum(row["judgments"] for row in rows),
            }
            return PageResponse.ok({"totals": totals, "sessions": rows[:MAX_SESSIONS]})

        if request.endpoint == "/session":
            key = str((request.body or {}).get("key") or "")
            if not key.startswith(plugin.key_prefix()):
                return PageResponse.fail("Unknown session")
            row = await plugin.load(key)
            if row is None:
                return PageResponse.fail("Unknown session")
            conversation, conversation_error = [], ""
            try:
                messages, _ = await plugin.messages_page(row.get("bot", ""), row.get("user", ""), CONVERSATION_MESSAGES)
                conversation = [
                    {"at": utc_label(message.get("timestamp")), "role": role_label(message.get("role")),
                     "text": stored_text(message.get("message_content"))}
                    for message in reversed(messages)
                ]
            except Exception as error:  # noqa: BLE001 - history is optional context for the page
                conversation_error = "permission_denied" if "permission_denied" in str(error) else type(error).__name__
            return PageResponse.ok({
                "session": {**summarize({**row, "key": key}), "events": row.get("events") or []},
                "conversation": conversation,
                "conversation_error": conversation_error,
            })

        return PageResponse.fail(f"Unknown endpoint: {request.method} {request.endpoint}")
