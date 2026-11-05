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
    ):
        self.message = message
        self.code = code
        self.retryable = retryable
        self.status = status
        super().__init__(message)


class MulticaConfigError(MulticaAPIError):
    """Multica runner configuration is invalid."""

    def __init__(self, message: str, code: str = "multica.config_invalid"):
        super().__init__(message, code=code)
