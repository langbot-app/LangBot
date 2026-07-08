from __future__ import annotations


class DeerFlowAPIError(Exception):
    """DeerFlow API 请求失败"""

    def __init__(
        self,
        *,
        operation: str = '',
        status: int = 0,
        body: str = '',
        url: str = '',
        thread_id: str | None = None,
        message: str = '',
    ) -> None:
        self.operation = operation
        self.status = status
        self.body = body
        self.url = url
        self.thread_id = thread_id

        if message:
            super().__init__(message)
            return

        msg = f'DeerFlow {operation} failed: status={status}, url={url}, body={body}'
        if thread_id is not None:
            msg = f'DeerFlow {operation} failed: thread_id={thread_id}, status={status}, url={url}, body={body}'
        super().__init__(msg)
