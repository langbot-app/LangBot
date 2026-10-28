from __future__ import annotations

from langbot_plugin.api.definition.components.page import Page, PageRequest, PageResponse

from ..observability import get_telemetry


class ParserObservabilityPage(Page):
    """Backend endpoints for the static parser observability page.

    Records are scoped to the installation binding of the current invocation
    (``PageRequest`` carries no binding; the task-local SDK binding does). The
    page therefore only ever exposes the calling installation's telemetry.
    """

    async def handle_api(self, request: PageRequest) -> PageResponse:
        endpoint = (request.endpoint or "").rstrip("/") or "/"
        method = (request.method or "POST").upper()

        telemetry = get_telemetry(self.get_installation_binding())

        if endpoint == "/snapshot" and method in {"GET", "POST"}:
            return PageResponse.ok(telemetry.snapshot())

        if endpoint == "/clear" and method in {"POST", "DELETE"}:
            telemetry.clear()
            return PageResponse.ok(telemetry.snapshot())

        return PageResponse.fail(f"Unsupported endpoint: {method} {endpoint}")
