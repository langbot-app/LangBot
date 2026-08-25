from __future__ import annotations

import threading

import pytest

from langbot.pkg.utils import safe_regex
from langbot.pkg.utils.bounded_executor import blocking_work_scope, current_blocking_work_scope


@pytest.mark.asyncio
async def test_matches_any_runs_off_event_loop_and_preserves_workspace_scope(monkeypatch):
    event_loop_thread = threading.get_ident()
    observed: dict[str, object] = {}
    original = safe_regex._matches_any_sync

    def observe(*args, **kwargs):
        observed['thread'] = threading.get_ident()
        observed['scope'] = current_blocking_work_scope()
        return original(*args, **kwargs)

    monkeypatch.setattr(safe_regex, '_matches_any_sync', observe)

    with blocking_work_scope('workspace-a'):
        assert await safe_regex.matches_any(['^hello'], 'hello world') is True

    assert observed['scope'] == 'workspace-a'
    assert observed['thread'] != event_loop_thread


@pytest.mark.asyncio
async def test_matches_any_interrupts_catastrophic_backtracking():
    with pytest.raises(safe_regex.SafeRegexTimeoutError):
        await safe_regex.matches_any(
            [r'(a+)+$'],
            ('a' * 100_000) + '!',
            timeout_seconds=0.001,
        )


@pytest.mark.asyncio
async def test_matches_any_rejects_pattern_and_input_amplification():
    with pytest.raises(safe_regex.SafeRegexLimitError):
        await safe_regex.matches_any(
            ['a'] * (safe_regex.MAX_PATTERN_COUNT + 1),
            'a',
        )

    with pytest.raises(safe_regex.SafeRegexLimitError):
        await safe_regex.matches_any(
            ['a'],
            'a' * (safe_regex.MAX_INPUT_CHARS + 1),
        )


@pytest.mark.asyncio
async def test_mask_patterns_honors_explicit_pattern_count_cap():
    patterns = ['a'] * (safe_regex.MAX_PATTERN_COUNT + 6)
    found, masked = await safe_regex.mask_patterns(
        patterns,
        'hello',
        mask='*',
        mask_word='',
        max_pattern_count=len(patterns),
    )
    assert found is False
    assert masked == 'hello'

    with pytest.raises(safe_regex.SafeRegexLimitError):
        await safe_regex.mask_patterns(
            patterns,
            'hello',
            mask='*',
            mask_word='',
        )


@pytest.mark.asyncio
async def test_mask_patterns_rejects_oversized_sequence_before_copying_it():
    class OversizedPatterns(list):
        def __iter__(self):
            raise AssertionError('oversized patterns must not be materialized')

    patterns = OversizedPatterns(['a'] * (safe_regex.MAX_PATTERN_COUNT + 1))

    with pytest.raises(safe_regex.SafeRegexLimitError):
        await safe_regex.mask_patterns(
            patterns,
            'hello',
            mask='*',
            mask_word='',
        )


@pytest.mark.asyncio
async def test_mask_patterns_bounds_replacement_growth_and_masks_matches():
    found, masked = await safe_regex.mask_patterns(
        [r'secret-\d+'],
        'a secret-42 value',
        mask='*',
        mask_word='[hidden]',
    )
    assert found is True
    assert masked == 'a [hidden] value'

    with pytest.raises(safe_regex.SafeRegexLimitError):
        await safe_regex.mask_patterns(
            ['a'],
            'a' * safe_regex.MAX_INPUT_CHARS,
            mask='0123456789',
            mask_word='',
        )
