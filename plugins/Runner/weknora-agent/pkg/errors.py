"""WeKnora Runner errors."""

from __future__ import annotations


class WeKnoraAPIError(Exception):
    """WeKnora API request failed."""

    def __init__(self, message: str, code: str = "weknora.api_error", retryable: bool = False):
        self.message = message
        self.code = code
        self.retryable = retryable
        super().__init__(message)


class WeKnoraConfigError(WeKnoraAPIError):
    """WeKnora runner configuration is invalid."""

    def __init__(self, message: str, code: str = "weknora.config_invalid"):
        super().__init__(message, code=code)
