from ...i18n import t


class RequesterError(Exception):
    """Base class for all Requester errors."""

    def __init__(
        self,
        message: str,
        *,
        code: str = 'provider_error',
        status_code: int | None = None,
        retryable: bool = False,
        retry_after: float | None = None,
        request_id: str | None = None,
        phase: str | None = None,
    ):
        super().__init__(t('Model request failed') + ': ' + message)
        self.code = code
        self.status_code = status_code
        self.retryable = retryable
        self.retry_after = retry_after
        self.request_id = request_id
        self.phase = phase

    def as_dict(self) -> dict:
        """Machine-readable diagnostics without upstream bodies or credentials."""
        return {
            key: getattr(self, key)
            for key in ('code', 'status_code', 'retryable', 'retry_after', 'request_id', 'phase')
        }
