"""DeerFlow Runner errors."""

from __future__ import annotations


class DeerFlowAPIError(Exception):
    """DeerFlow API request failed."""

    def __init__(
        self,
        message: str = "",
        *,
        operation: str = "",
        status: int = 0,
        body: str = "",
        url: str = "",
        thread_id: str | None = None,
        code: str = "deerflow.api_error",
        retryable: bool = False,
    ) -> None:
        self.message = message
        self.operation = operation
        self.status = status
        self.body = body
        self.url = url
        self.thread_id = thread_id
        self.code = code
        self.retryable = retryable

        if message:
            super().__init__(message)
            return

        text = f"DeerFlow {operation} failed: status={status}, url={url}, body={body}"
        if thread_id is not None:
            text = f"DeerFlow {operation} failed: thread_id={thread_id}, status={status}, url={url}, body={body}"
        self.message = text
        super().__init__(text)


class DeerFlowConfigError(DeerFlowAPIError):
    """DeerFlow runner configuration is invalid."""

    def __init__(self, message: str, code: str = "deerflow.config_invalid"):
        super().__init__(message, code=code)
