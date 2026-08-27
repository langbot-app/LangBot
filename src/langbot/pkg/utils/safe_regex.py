from __future__ import annotations

import asyncio
import time
from collections.abc import Sequence

import regex


MAX_PATTERN_COUNT = 64
MAX_PATTERN_CHARS = 1024
MAX_INPUT_CHARS = 1024 * 1024
MAX_REPLACEMENT_CHARS = 64
MAX_MASKED_OUTPUT_CHARS = 2 * 1024 * 1024
DEFAULT_OPERATION_TIMEOUT_SECONDS = 0.05


class SafeRegexError(ValueError):
    """Base class for rejected, invalid, or timed-out tenant regex work."""


class SafeRegexLimitError(SafeRegexError):
    """Raised when a regex operation exceeds a deterministic resource limit."""


class SafeRegexTimeoutError(SafeRegexError):
    """Raised when the regex engine exhausts the operation CPU budget."""


def _validate_patterns(
    patterns: Sequence[str],
    *,
    max_pattern_count: int = MAX_PATTERN_COUNT,
) -> tuple[str, ...]:
    if max_pattern_count < 1:
        raise ValueError('max_pattern_count must be positive')
    if len(patterns) > max_pattern_count:
        raise SafeRegexLimitError(f'At most {max_pattern_count} regex patterns are allowed')
    normalized = tuple(patterns)
    for pattern in normalized:
        if not isinstance(pattern, str):
            raise SafeRegexError('Regex patterns must be strings')
        if len(pattern) > MAX_PATTERN_CHARS:
            raise SafeRegexLimitError(f'Regex patterns may contain at most {MAX_PATTERN_CHARS} characters')
    return normalized


def _validate_input(value: str) -> None:
    if not isinstance(value, str):
        raise SafeRegexError('Regex input must be a string')
    if len(value) > MAX_INPUT_CHARS:
        raise SafeRegexLimitError(f'Regex input may contain at most {MAX_INPUT_CHARS} characters')


def _remaining_seconds(deadline: float) -> float:
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        raise SafeRegexTimeoutError('Regex operation timed out')
    return remaining


def _compile(pattern: str):
    try:
        return regex.compile(pattern)
    except regex.error as exc:
        raise SafeRegexError(f'Invalid regex: {exc}') from exc


def _matches_any_sync(
    patterns: Sequence[str],
    value: str,
    *,
    mode: str,
    timeout_seconds: float,
) -> bool:
    normalized_patterns = _validate_patterns(patterns)
    _validate_input(value)
    if mode not in {'match', 'search'}:
        raise ValueError(f'Unsupported safe regex mode: {mode}')

    deadline = time.monotonic() + timeout_seconds
    try:
        for pattern in normalized_patterns:
            compiled = _compile(pattern)
            matcher = compiled.match if mode == 'match' else compiled.search
            if matcher(
                value,
                timeout=_remaining_seconds(deadline),
                concurrent=True,
            ):
                return True
    except TimeoutError as exc:
        raise SafeRegexTimeoutError('Regex operation timed out') from exc
    return False


async def matches_any(
    patterns: Sequence[str],
    value: str,
    *,
    mode: str = 'search',
    timeout_seconds: float = DEFAULT_OPERATION_TIMEOUT_SECONDS,
) -> bool:
    """Match untrusted patterns without blocking the shared event loop."""

    if timeout_seconds <= 0:
        raise ValueError('timeout_seconds must be positive')
    return await asyncio.to_thread(
        _matches_any_sync,
        patterns,
        value,
        mode=mode,
        timeout_seconds=timeout_seconds,
    )


def _mask_patterns_sync(
    patterns: Sequence[str],
    value: str,
    *,
    mask: str,
    mask_word: str,
    timeout_seconds: float,
    max_pattern_count: int,
) -> tuple[bool, str]:
    normalized_patterns = _validate_patterns(patterns, max_pattern_count=max_pattern_count)
    _validate_input(value)
    if len(mask) > MAX_REPLACEMENT_CHARS or len(mask_word) > MAX_REPLACEMENT_CHARS:
        raise SafeRegexLimitError(f'Regex replacements may contain at most {MAX_REPLACEMENT_CHARS} characters')

    # Reject amplification before invoking a replacement callback. This is
    # deliberately conservative: a hostile replacement must not allocate tens
    # of megabytes before the post-operation output check can run.
    replacement_width = len(mask_word) if mask_word else len(mask)
    if replacement_width * max(1, len(value)) > MAX_MASKED_OUTPUT_CHARS:
        raise SafeRegexLimitError('Regex replacement could exceed the masked output limit')

    deadline = time.monotonic() + timeout_seconds
    found = False
    current = value

    def replace(match) -> str:
        nonlocal found
        found = True
        if mask_word:
            return mask_word
        return mask * len(match.group(0))

    try:
        for pattern in normalized_patterns:
            compiled = _compile(pattern)
            current = compiled.sub(
                replace,
                current,
                timeout=_remaining_seconds(deadline),
                concurrent=True,
            )
            if len(current) > MAX_MASKED_OUTPUT_CHARS:
                raise SafeRegexLimitError('Regex replacement exceeded the masked output limit')
    except TimeoutError as exc:
        raise SafeRegexTimeoutError('Regex operation timed out') from exc
    return found, current


async def mask_patterns(
    patterns: Sequence[str],
    value: str,
    *,
    mask: str,
    mask_word: str,
    timeout_seconds: float = DEFAULT_OPERATION_TIMEOUT_SECONDS,
    max_pattern_count: int = MAX_PATTERN_COUNT,
) -> tuple[bool, str]:
    """Apply untrusted masking patterns with bounded CPU and output growth."""

    if timeout_seconds <= 0:
        raise ValueError('timeout_seconds must be positive')
    return await asyncio.to_thread(
        _mask_patterns_sync,
        patterns,
        value,
        mask=mask,
        mask_word=mask_word,
        timeout_seconds=timeout_seconds,
        max_pattern_count=max_pattern_count,
    )
