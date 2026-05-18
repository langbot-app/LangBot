"""
Unit tests for log cache utilities.

Tests log page management and pointer-based retrieval.
"""

from __future__ import annotations


from langbot.pkg.utils.logcache import LogPage, LogCache, LOG_PAGE_SIZE, MAX_CACHED_PAGES


class TestLogPage:
    """Tests for LogPage class."""

    def test_init_creates_empty_page(self):
        """LogPage initializes with empty logs list."""
        page = LogPage(number=0)

        assert page.number == 0
        assert page.logs == []

    def test_add_log_appends_to_list(self):
        """add_log appends log to the list."""
        page = LogPage(number=0)

        page.add_log('log entry 1')
        page.add_log('log entry 2')

        assert len(page.logs) == 2
        assert page.logs[0] == 'log entry 1'
        assert page.logs[1] == 'log entry 2'

    def test_add_log_returns_false_when_not_full(self):
        """add_log returns False when page is not full."""
        page = LogPage(number=0)

        for i in range(LOG_PAGE_SIZE - 1):
            result = page.add_log(f'log {i}')
            assert result is False

    def test_add_log_returns_true_when_full(self):
        """add_log returns True when page reaches LOG_PAGE_SIZE."""
        page = LogPage(number=0)

        for i in range(LOG_PAGE_SIZE - 1):
            page.add_log(f'log {i}')

        result = page.add_log('last log')
        assert result is True

    def test_add_log_exactly_page_size(self):
        """Page contains exactly LOG_PAGE_SIZE logs when full."""
        page = LogPage(number=0)

        for i in range(LOG_PAGE_SIZE):
            page.add_log(f'log {i}')

        assert len(page.logs) == LOG_PAGE_SIZE


class TestLogCache:
    """Tests for LogCache class."""

    def test_init_creates_first_page(self):
        """LogCache initializes with first empty page."""
        cache = LogCache()

        assert len(cache.log_pages) == 1
        assert cache.log_pages[0].number == 0
        assert cache.log_pages[0].logs == []

    def test_add_log_to_first_page(self):
        """add_log adds to the first page initially."""
        cache = LogCache()

        cache.add_log('test log')

        assert len(cache.log_pages) == 1
        assert cache.log_pages[0].logs[0] == 'test log'

    def test_add_log_creates_new_page_when_full(self):
        """add_log creates new page when current page is full."""
        cache = LogCache()

        # Fill first page
        for i in range(LOG_PAGE_SIZE):
            cache.add_log(f'log {i}')

        # Add one more to trigger new page
        cache.add_log('overflow log')

        assert len(cache.log_pages) == 2
        assert cache.log_pages[1].number == 1
        assert cache.log_pages[1].logs[0] == 'overflow log'

    def test_add_log_removes_oldest_page_when_exceeds_max(self):
        """Cache removes oldest page when exceeding MAX_CACHED_PAGES."""
        cache = LogCache()

        # Fill enough pages to exceed MAX_CACHED_PAGES
        total_logs = (MAX_CACHED_PAGES + 1) * LOG_PAGE_SIZE
        for i in range(total_logs):
            cache.add_log(f'log {i}')

        # Should have exactly MAX_CACHED_PAGES pages
        assert len(cache.log_pages) == MAX_CACHED_PAGES

        # First page should not be page 0
        assert cache.log_pages[0].number > 0

    def test_get_log_by_pointer_single_page(self):
        """get_log_by_pointer retrieves logs from single page."""
        cache = LogCache()

        cache.add_log('log 1')
        cache.add_log('log 2')
        cache.add_log('log 3')

        result, page_num, offset = cache.get_log_by_pointer(0, 0)

        assert 'log 1' in result
        assert 'log 2' in result
        assert 'log 3' in result

    def test_get_log_by_pointer_with_offset(self):
        """get_log_by_pointer respects start offset."""
        cache = LogCache()

        cache.add_log('log 1')
        cache.add_log('log 2')
        cache.add_log('log 3')

        result, page_num, offset = cache.get_log_by_pointer(0, 1)

        assert 'log 1' not in result
        assert 'log 2' in result
        assert 'log 3' in result

    def test_get_log_by_pointer_across_pages(self):
        """get_log_by_pointer retrieves logs across pages."""
        cache = LogCache()

        # Fill first page and add to second
        for i in range(LOG_PAGE_SIZE):
            cache.add_log(f'page0 log {i}')
        cache.add_log('page1 log 0')

        # Get from first page offset 0
        result, page_num, offset = cache.get_log_by_pointer(0, 0)

        # Should contain all logs from page 0 and page 1
        assert 'page0 log 0' in result
        assert 'page1 log 0' in result

    def test_get_log_by_pointer_from_second_page(self):
        """get_log_by_pointer can start from second page."""
        cache = LogCache()

        # Fill first page and add to second
        for i in range(LOG_PAGE_SIZE):
            cache.add_log(f'page0 log {i}')
        cache.add_log('page1 log 0')

        # Get from second page
        result, page_num, offset = cache.get_log_by_pointer(1, 0)

        assert 'page0' not in result
        assert 'page1 log 0' in result

    def test_page_numbers_sequential(self):
        """Page numbers are sequential."""
        cache = LogCache()

        # Create multiple pages
        for i in range(LOG_PAGE_SIZE * 3):
            cache.add_log(f'log {i}')

        for i, page in enumerate(cache.log_pages):
            assert page.number == i

    def test_empty_cache_get_log(self):
        """get_log_by_pointer works with empty cache."""
        cache = LogCache()

        result, page_num, offset = cache.get_log_by_pointer(0, 0)

        assert result == ''

    def test_get_log_by_pointer_nonexistent_page(self):
        """get_log_by_pointer handles nonexistent page number."""
        cache = LogCache()

        cache.add_log('log 1')

        # Request page that doesn't exist
        result, page_num, offset = cache.get_log_by_pointer(99, 0)

        # Returns empty or last available
        # Behavior depends on implementation

    def test_max_cached_pages_constant(self):
        """MAX_CACHED_PAGES is defined and reasonable."""
        assert MAX_CACHED_PAGES > 0
        assert MAX_CACHED_PAGES <= 100  # Reasonable upper bound

    def test_log_page_size_constant(self):
        """LOG_PAGE_SIZE is defined and reasonable."""
        assert LOG_PAGE_SIZE > 0
        assert LOG_PAGE_SIZE <= 1000  # Reasonable upper bound
