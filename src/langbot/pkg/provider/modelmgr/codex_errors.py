"""Explicitly safe Codex failures; never construct messages from upstream bodies."""

from ...i18n import t
from .errors import RequesterError


class CodexProviderError(ValueError):
    """A known provider failure safe to expose at the HTTP boundary."""

    def __init__(self, message: str, status_code: int = 502, error_code: str = 'codex_upstream_failure'):
        ValueError.__init__(self, t(message))
        self.code = error_code
        self.retryable = status_code in (500, 502, 503, 504)
        self.retry_after = None
        self.request_id = None
        self.phase = None
        self.status_code = status_code
        self.error_code = error_code

    as_dict = RequesterError.as_dict
