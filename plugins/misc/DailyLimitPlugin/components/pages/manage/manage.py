from __future__ import annotations

from langbot_plugin.api.definition.components.page import Page, PageRequest, PageResponse


class ManagePage(Page):
    """Management UI backend for the Daily Limit plugin.

    Endpoints (called from index.html via the Page SDK ``langbot.api``):

      GET    /state                  -> full snapshot (settings + sessions)
      PUT    /settings  {..}         -> update global settings / new-session default
      PUT    /session   {id, limit}  -> set per-session limit override (null = use default)
      POST   /reset     {id}         -> reset one session's counter to 0
      POST   /reset-all              -> reset every session's counter
      DELETE /session   {id}         -> stop tracking a session (removes the row)
    """

    async def handle_api(self, request: PageRequest) -> PageResponse:
        plugin = self.plugin
        body = request.body or {}
        ep, method = request.endpoint, request.method

        if ep == "/state" and method == "GET":
            return PageResponse.ok(await plugin.snapshot())

        if ep == "/settings" and method == "PUT":
            await plugin.update_settings(body)
            return PageResponse.ok(await plugin.snapshot())

        if ep == "/session" and method == "PUT":
            session_id = body.get("id", "")
            if not await plugin.set_session_limit(session_id, body.get("limit")):
                return PageResponse.fail("session not found")
            return PageResponse.ok(await plugin.snapshot())

        if ep == "/session" and method == "DELETE":
            if not await plugin.delete_session(body.get("id", "")):
                return PageResponse.fail("session not found")
            return PageResponse.ok(await plugin.snapshot())

        if ep == "/reset" and method == "POST":
            if not await plugin.reset_session(body.get("id", "")):
                return PageResponse.fail("session not found")
            return PageResponse.ok(await plugin.snapshot())

        if ep == "/reset-all" and method == "POST":
            n = await plugin.reset_all()
            return PageResponse.ok({**(await plugin.snapshot()), "reset_count": n})

        return PageResponse.fail(f"Unknown endpoint: {method} {ep}")
