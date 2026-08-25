from __future__ import annotations

import json
import threading
from pathlib import Path

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
async def test_bundled_sensitive_words_fit_within_pattern_limit():
    config_path = Path(__file__).parents[3] / 'src/langbot/templates/metadata/sensitive-words.json'
    config = json.loads(config_path.read_text())

    assert len(config['words']) <= safe_regex.MAX_PATTERN_COUNT
    found, masked = await safe_regex.mask_patterns(
        config['words'],
        '普通消息',
        mask=config['mask'],
        mask_word=config['mask_word'],
    )

    assert found is False
    assert masked == '普通消息'


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
