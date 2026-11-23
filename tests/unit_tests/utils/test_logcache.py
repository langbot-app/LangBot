"""Exercise the text and cursors consumed by the instance log viewer."""

from __future__ import annotations

import pytest

from langbot.pkg.utils.logcache import LOG_PAGE_SIZE, MAX_CACHED_PAGES, MAX_LOG_LINE_CHARS, LogCache


def test_empty_poll_resumes_at_origin():
    cache = LogCache()

    assert cache.get_log_by_pointer(0, 0) == ('', 0, 0)


def test_partial_page_resume_yields_only_new_lines():
    cache = LogCache()
    cache.add_log('first')
    logs, page, offset = cache.get_log_by_pointer(0, 0)
    assert (logs, page, offset) == ('first', 0, 1)

    cache.add_log('second')
    cache.add_log('third')

    assert cache.get_log_by_pointer(page, offset) == ('second\nthird', 0, 3)
    assert cache.get_log_by_pointer(0, 3) == ('', 0, 3)


def test_cursor_at_exact_page_boundary_resumes_after_rollover():
    assert 0 < LOG_PAGE_SIZE <= 1000
    cache = LogCache()
    lines = [f'line {i}' for i in range(LOG_PAGE_SIZE)]
    for line in lines:
        cache.add_log(line)

    logs, page, offset = cache.get_log_by_pointer(0, 0)
    assert logs.splitlines() == lines
    assert (page, offset) == (1, 0)

    cache.add_log('next page')
    assert cache.get_log_by_pointer(page, offset) == ('next page', 1, 1)


def test_poll_crosses_multiple_pages_in_order_and_resumes_at_tail():
    cache = LogCache()
    lines = [f'line {i}' for i in range(LOG_PAGE_SIZE * 2 + 1)]
    for line in lines:
        cache.add_log(line)

    logs, page, offset = cache.get_log_by_pointer(0, LOG_PAGE_SIZE - 1)

    assert logs.split('\n') == lines[LOG_PAGE_SIZE - 1 :]
    assert (page, offset) == (2, 1)


def test_evicted_cursor_resumes_at_oldest_retained_line_without_its_old_offset():
    assert 0 < MAX_CACHED_PAGES <= 100
    assert 0 < LOG_PAGE_SIZE <= 1000
    cache = LogCache()
    lines = [f'line {i}' for i in range(MAX_CACHED_PAGES * LOG_PAGE_SIZE + 1)]
    for line in lines:
        cache.add_log(line)

    logs, page, offset = cache.get_log_by_pointer(0, 5)

    assert logs.splitlines() == lines[LOG_PAGE_SIZE:]
    assert (page, offset) == (MAX_CACHED_PAGES, 1)


def test_cursor_beyond_tail_returns_no_lines_and_repairs_cursor():
    cache = LogCache()
    cache.add_log('one')

    assert cache.get_log_by_pointer(99, 0) == ('', 0, 1)


@pytest.mark.parametrize(
    'size',
    [MAX_LOG_LINE_CHARS, MAX_LOG_LINE_CHARS + 1, 2 * MAX_LOG_LINE_CHARS],
    ids=['exact-limit', 'over-by-one', 'double-limit'],
)
def test_single_log_line_is_bounded_without_losing_the_following_line(size):
    cache = LogCache()
    line = 'x' * size
    cache.add_log(line)
    cache.add_log('next line')

    marker = '\n[log truncated]'
    expected = line[: MAX_LOG_LINE_CHARS - len(marker)] + marker if size > MAX_LOG_LINE_CHARS else line

    assert cache.get_log_by_pointer(0, 0) == (expected + '\nnext line', 0, 2)
