"""BanWordFilter regression tests for legacy sensitive-word lists.

v4.10.7 introduced a 64-pattern cap in safe_regex. Older installs still carry
the previous default list (~70 patterns). The filter must keep applying those
rules instead of blocking every message.
"""

from __future__ import annotations

from importlib import import_module
from unittest.mock import Mock

import pytest

from tests.factories import FakeApp


def _load_banwords():
    import_module('langbot.pkg.pipeline.pipelinemgr')
    banwords = import_module('langbot.pkg.pipeline.cntfilter.filters.banwords')
    entities = import_module('langbot.pkg.pipeline.cntfilter.entities')
    safe_regex = import_module('langbot.pkg.utils.safe_regex')
    return banwords, entities, safe_regex


def _filter_with_words(words: list[str], *, mask: str = '*', mask_word: str = ''):
    banwords, entities, _ = _load_banwords()
    app = FakeApp()
    app.sensitive_meta = Mock()
    app.sensitive_meta.data = {
        'words': words,
        'mask': mask,
        'mask_word': mask_word,
    }
    return banwords.BanWordFilter(app), entities, app


@pytest.mark.asyncio
async def test_legacy_word_list_over_pattern_cap_does_not_block_clean_message():
    """A pre-v4.10.7 word list must not fail closed on every message."""
    _, _, safe_regex = _load_banwords()
    words = [f'word{i}' for i in range(safe_regex.MAX_PATTERN_COUNT + 6)]
    filt, entities, _ = _filter_with_words(words)

    result = await filt.process(Mock(), 'hello there, nothing banned')

    assert result.level == entities.ResultLevel.PASS
    assert result.replacement == 'hello there, nothing banned'
    assert result.user_notice == ''


@pytest.mark.asyncio
async def test_legacy_word_list_still_masks_match_beyond_first_batch():
    """Words past the first 64-pattern batch must still be applied."""
    _, _, safe_regex = _load_banwords()
    words = [f'word{i}' for i in range(safe_regex.MAX_PATTERN_COUNT)] + ['secret-token']
    filt, entities, _ = _filter_with_words(words, mask_word='[hidden]')

    result = await filt.process(Mock(), 'please hide secret-token now')

    assert result.level == entities.ResultLevel.MASKED
    assert 'secret-token' not in result.replacement
    assert '[hidden]' in result.replacement


@pytest.mark.asyncio
async def test_legacy_word_list_masks_match_in_first_batch():
    _, _, safe_regex = _load_banwords()
    words = ['alpha-secret'] + [f'word{i}' for i in range(safe_regex.MAX_PATTERN_COUNT)]
    filt, entities, _ = _filter_with_words(words, mask_word='[hidden]')

    result = await filt.process(Mock(), 'alpha-secret is here')

    assert result.level == entities.ResultLevel.MASKED
    assert result.replacement == '[hidden] is here'


@pytest.mark.asyncio
async def test_invalid_sensitive_word_regex_still_blocks():
    filt, entities, _ = _filter_with_words(['(unclosed'])

    result = await filt.process(Mock(), 'any message')

    assert result.level == entities.ResultLevel.BLOCK
    assert result.user_notice == '内容检查规则执行失败，请联系管理员'
    assert 'rejected' in result.console_notice.lower() or 'invalid' in result.console_notice.lower()


@pytest.mark.asyncio
async def test_oversized_word_list_is_blocked():
    """Configured rules must never be silently skipped when the list is oversized."""
    banwords, _, _ = _load_banwords()
    words = [f'word{i}' for i in range(banwords._MAX_SENSITIVE_WORD_PATTERNS + 10)]
    filt, entities, _ = _filter_with_words(words)

    result = await filt.process(Mock(), 'hello there, nothing banned')

    assert result.level == entities.ResultLevel.BLOCK
    assert result.replacement == ''
    assert result.user_notice == '内容检查规则执行失败，请联系管理员'
    assert 'at most 256 regex patterns are allowed' in result.console_notice.lower()


@pytest.mark.asyncio
async def test_match_beyond_total_cap_cannot_bypass_filter():
    banwords, _, _ = _load_banwords()
    words = [f'word{i}' for i in range(banwords._MAX_SENSITIVE_WORD_PATTERNS)] + ['late-secret']
    filt, entities, _ = _filter_with_words(words, mask_word='[hidden]')

    result = await filt.process(Mock(), 'please hide late-secret now')

    assert result.level == entities.ResultLevel.BLOCK
    assert result.replacement == ''
