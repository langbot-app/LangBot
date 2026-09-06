"""Explicitly safe Codex failures; never construct messages from upstream bodies."""


class CodexProviderError(ValueError):
    """A known provider failure safe to expose at the HTTP boundary."""

    def __init__(self, message: str, status_code: int = 502, error_code: str = 'codex_upstream_failure'):
        super().__init__(message)
        self.status_code = status_code
        self.error_code = error_code
