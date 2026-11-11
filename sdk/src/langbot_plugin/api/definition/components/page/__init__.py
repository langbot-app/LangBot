from __future__ import annotations

from typing import Any

import pydantic

from langbot_plugin.api.definition.components.base import BaseComponent


class PageRequest(pydantic.BaseModel):
    """Incoming request to a Page component's handle_api method."""

    endpoint: str
    """API endpoint path (e.g. ``'/entries'``)."""

    method: str
    """HTTP method (``GET``, ``POST``, ``PUT``, ``DELETE``)."""

    body: Any = None
    """Request body (parsed JSON, or ``None``)."""

    # -- extensible fields for future use --

    caller: dict[str, Any] | None = None
    """Caller identity (reserved for future public-facing pages)."""

    headers: dict[str, str] = pydantic.Field(default_factory=dict)
    """Request headers (reserved for future use)."""


class PageResponse(pydantic.BaseModel):
    """Response from a Page component's handle_api method."""

    data: Any = None
    """Response payload (JSON-serializable)."""

    error: str | None = None
    """Error message. If set, the frontend will treat it as a failure."""

    @classmethod
    def ok(cls, data: Any = None) -> PageResponse:
        return cls(data=data)

    @classmethod
    def fail(cls, error: str) -> PageResponse:
        return cls(error=error)


class Page(BaseComponent):
    """The page component.

    Each Page component provides a visual page in the LangBot WebUI sidebar
    and can handle API calls from the frontend via ``handle_api``.
    """

    __kind__ = "Page"

    async def handle_api(self, request: PageRequest) -> PageResponse:
        """Handle an API call from the page frontend.

        Override this method to implement a backend for your page.

        Args:
            request: The incoming request containing endpoint, method, body,
                     and future fields like caller identity.

        Returns:
            A ``PageResponse`` with either data or an error message.
        """
        return PageResponse.fail("Not implemented")
