from __future__ import annotations

from langbot_plugin.api.definition.components.page import (
    Page,
    PageRequest,
    PageResponse,
)



class LangRAGObservabilityPage(Page):
    """Static Page backend exposing LangRAG telemetry."""

    async def handle_api(self, request: PageRequest) -> PageResponse:
        telemetry = self.plugin.telemetry
        endpoint = (request.endpoint or "").rstrip("/") or "/"
        method = (request.method or "GET").upper()

        try:
            if endpoint in ("/", "/snapshot") and method == "GET":
                return PageResponse.ok(await telemetry.snapshot())

            if endpoint == "/metrics" and method == "GET":
                return PageResponse.ok(
                    {
                        "content_type": "text/plain; version=0.0.4",
                        "body": await telemetry.prometheus(),
                    }
                )

            if endpoint == "/export" and method == "GET":
                return PageResponse.ok(await telemetry.snapshot())

            if endpoint == "/clear" and method in ("POST", "DELETE"):
                await telemetry.clear()
                return PageResponse.ok(await telemetry.snapshot())
        except Exception as exc:
            # Telemetry is readable, never load bearing: a fenced or unreachable
            # state answers with an error the console can display, so the Page
            # never turns a diagnostic into an unhandled plugin failure.
            return PageResponse.fail(f"Telemetry unavailable: {exc}")

        return PageResponse.fail(f"Unknown endpoint: {method} {endpoint}")
