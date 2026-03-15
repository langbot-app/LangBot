from __future__ import annotations

import time
from typing import Any, Callable, Optional


class PullStreamPolicy:
    """Encapsulate pull-stream fallback and closure strategy.

    This class is intentionally independent from the transport layer, so that
    merge conflicts in ``api.py`` can be reduced when upstream modifies webhook
    request/response handling.
    """

    def __init__(
        self,
        *,
        stream_sessions,
        generated_content: dict[str, str],
        stream_max_lifetime: float,
        pending_placeholder: str,
        pending_placeholder_delay: float,
        stream_timeout_final_text: str,
        stream_error_final_text: str,
        chunk_factory: Callable[..., Any],
    ) -> None:
        self.stream_sessions = stream_sessions
        self.generated_content = generated_content
        self.stream_max_lifetime = max(1.0, float(stream_max_lifetime))
        self.pending_placeholder = pending_placeholder or ''
        self.pending_placeholder_delay = max(0.0, float(pending_placeholder_delay))
        self.stream_timeout_final_text = stream_timeout_final_text
        self.stream_error_final_text = stream_error_final_text
        self._chunk_factory = chunk_factory

    def create_chunk(self, content: str, is_final: bool = False, reason: str | None = None):
        meta = {'reason': reason} if reason else {}
        return self._chunk_factory(content=content, is_final=is_final, meta=meta)

    def is_stream_lifetime_exceeded(self, session) -> bool:
        if session.finished:
            return False
        return time.time() - session.created_at >= self.stream_max_lifetime

    def resolve_timeout_content(self, session) -> str:
        if session and session.last_chunk:
            return session.last_chunk.content
        return self.stream_timeout_final_text

    async def force_finish_stream(self, stream_id: str, content: str, reason: str):
        if not stream_id:
            return None

        chunk = self.create_chunk(content=content, is_final=True, reason=reason)
        await self.stream_sessions.publish(stream_id, chunk)
        self.stream_sessions.mark_finished(stream_id)

        session = self.stream_sessions.get_session(stream_id)
        if session:
            session.last_chunk = chunk
            session.finished = True
            session.last_access = time.time()

        return chunk

    def resolve_consume_timeout(self, session, default_timeout: float) -> float:
        consume_timeout = default_timeout
        if not session.last_chunk and not session.finished and self.pending_placeholder_delay > 0:
            remaining_delay = self.pending_placeholder_delay - (time.time() - session.created_at)
            if remaining_delay > 0:
                consume_timeout = max(consume_timeout, remaining_delay)
        return consume_timeout

    def pop_cached_content(self, session) -> Optional[str]:
        if not session or not session.msg_id:
            return None
        return self.generated_content.pop(session.msg_id, None)

    def resolve_followup_chunk(self, session, cached_content: Optional[str]):
        if cached_content is not None:
            return self.create_chunk(content=cached_content, is_final=True, reason='cached_final')

        if session and session.last_chunk:
            if 'reason' not in session.last_chunk.meta:
                session.last_chunk.meta['reason'] = 'last_snapshot'
            return session.last_chunk

        if not session:
            return None

        if not self.pending_placeholder:
            return None

        elapsed = time.time() - session.created_at
        if elapsed < self.pending_placeholder_delay:
            return None

        placeholder_chunk = self.create_chunk(
            content=self.pending_placeholder,
            is_final=False,
            reason='pending_placeholder',
        )
        session.last_chunk = placeholder_chunk
        session.last_access = time.time()
        return placeholder_chunk

    def create_missing_session_chunk(self):
        return self.create_chunk(
            content=self.stream_error_final_text,
            is_final=True,
            reason='missing_session',
        )
