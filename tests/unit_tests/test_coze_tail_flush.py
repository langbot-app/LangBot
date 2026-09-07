from __future__ import annotations

"""Regression tests for the stream tail-flush in CozeAPIRunner._chat_messages_chunk.

Self-hosted Coze does not emit a terminating 'done' event, so ``is_final`` can
stay False for the whole stream. The runner only flushes on a ``message_idx % 8
== 0`` boundary, so a stream whose length is not a multiple of 8 used to lose its
tail. These tests mirror the emission rules and assert that no tail is dropped
and that content is never re-sent twice.
"""


def _emulate_stream_chunks(deltas: list[str], done_at: int | None) -> list[tuple[str, bool]]:
    """Replicate CozeAPIRunner._chat_messages_chunk emission rules.

    deltas: per-delta content strings.
    done_at: index (0-based) of the delta carrying the 'done' event, or None.
    """
    message_idx = 1
    is_final = False
    full_content = ''
    flushed_content_len = 0
    emitted: list[tuple[str, bool]] = []
    for index, content in enumerate(deltas):
        message_idx += 1
        if done_at is not None and index == done_at:
            is_final = True
        full_content = full_content + content
        if message_idx % 8 == 0 or is_final:
            if full_content:
                emitted.append((full_content, is_final))
                flushed_content_len = len(full_content)
    # New tail flush.
    if full_content and not is_final and len(full_content) != flushed_content_len:
        emitted.append((full_content, True))
    return emitted


def _render(emitted: list[tuple[str, bool]]) -> str:
    # The platform renders the latest cumulative chunk (replace semantics).
    return emitted[-1][0] if emitted else ''


def test_tail_is_never_lost_for_any_stream_length_and_done_position() -> None:
    # Every stream length 1..40, with the 'done' event at every possible delta
    # or absent entirely, must render the full concatenated content exactly once.
    for length in range(1, 41):
        positions = list(range(length)) + [None]
        for done_at in positions:
            deltas = [chr(ord('a') + i % 26) for i in range(length)]
            emitted = _emulate_stream_chunks(deltas, done_at)
            expected = ''.join(deltas)
            assert _render(emitted) == expected, (length, done_at, emitted, expected)


def test_short_stream_without_done_flushes_tail_as_final() -> None:
    # 5 deltas, no 'done' -> must be emitted once and marked final.
    emitted = _emulate_stream_chunks(list('abcde'), None)
    assert emitted == [('abcde', True)]


def test_stream_ending_exactly_on_a_flush_boundary_is_not_re_sent() -> None:
    # 7 deltas, no 'done': the 7th delta triggers the message_idx==8 boundary,
    # so the tail flush must not duplicate the same cumulative content.
    emitted = _emulate_stream_chunks(['x'] * 7, None)
    assert emitted == [('x' * 7, False)]
