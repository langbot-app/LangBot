"""Host-only receipt times, kept outside plugin payloads and persisted events."""

from collections import deque
from contextvars import ContextVar
import time


class RunnerStreamReceipts:
    def __init__(self, context):
        self.context = context
        self.arrivals: deque[float] = deque()
        self.receiving_at: float | None = None
        self.seq_id: int | None = None
        self.deadline_at = None
        self.deadline = None
        self.remaining()

    def has_pending(self):
        return bool(self.arrivals) or self.receiving_at is not None

    def remaining(self):
        value = (self.context.get('runtime') or {}).get('deadline_at')
        try:
            value = float(value) if value is not None else None
        except (TypeError, ValueError):
            value = None
        if value != self.deadline_at:
            if value is None:
                self.deadline = None
            elif self.deadline is None:
                self.deadline = time.monotonic() + value - time.time()
            else:
                # Interaction extensions adjust the original monotonic deadline.
                self.deadline += value - self.deadline_at
            self.deadline_at = value
        return None if self.deadline is None else self.deadline - time.monotonic()


current_runner_receipts: ContextVar[RunnerStreamReceipts | None] = ContextVar('runner_receipts', default=None)
receiving_runner_frame: ContextVar[tuple[RunnerStreamReceipts, float] | None] = ContextVar(
    'receiving_runner_frame', default=None
)
