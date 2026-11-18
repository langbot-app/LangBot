"""Multica Runner errors."""

from __future__ import annotations


class MulticaAPIError(Exception):
    """A Multica API request failed."""

    def __init__(
        self,
        message: str,
        code: str = "multica.api_error",
        retryable: bool = False,
        status: int | None = None,
        unsent: bool = False,
    ):
        self.message = message
        self.code = code
        self.retryable = retryable
        self.status = status
        # True when the request never reached the server, so even a POST is safe to resend.
        self.unsent = unsent
        super().__init__(message)


class MulticaConfigError(MulticaAPIError):
    """Multica runner configuration is invalid."""

    def __init__(self, message: str, code: str = "multica.config_invalid"):
        super().__init__(message, code=code)
