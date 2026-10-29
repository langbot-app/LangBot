"""Output-only reasoning filtering; never treats tool-call markup as thinking."""

from __future__ import annotations

import math


def strict_bool(config: dict, name: str, default: bool = False) -> bool:
    value = config.get(name, default)
    if type(value) is not bool:
        raise ValueError(f"{name} must be a boolean")
    return value


def positive_timeout(config: dict) -> float:
    value = config.get("timeout", 120)
    try:
        timeout = float(value)
    except (TypeError, ValueError, OverflowError):
        raise ValueError("timeout must be a finite positive number") from None
    if isinstance(value, bool) or not math.isfinite(timeout) or timeout <= 0:
        raise ValueError("timeout must be a finite positive number")
    return timeout


class ResponseBudget:
    """Match the native 1 MiB generated-text limit, even for hidden output."""

    def __init__(self, error_type, code: str):
        self.size = 0
        self.error_type = error_type
        self.code = code

    def add(self, *values: str) -> None:
        self.size += sum(len(value or "") for value in values)
        if self.size > 1024 * 1024:
            raise self.error_type("Response exceeds the runtime limit", code=self.code)

    def check_rendered(self, value: str) -> None:
        """Check a snapshot without charging repeated streaming snapshots."""
        if len(value) > 1024 * 1024:
            raise self.error_type("Response exceeds the runtime limit", code=self.code)


class ThinkingFilter:
    """Filter delta text while retaining incomplete delimiters between chunks.

    Only declared reasoning delimiters are recognized. Ordinary text (including
    tool-call markup and whitespace) is not normalized. Unterminated reasoning
    stays hidden; an incomplete opening delimiter outside reasoning is flushed
    as literal text at EOF. Disabled mode is an exact pass-through.
    """

    def __init__(self, enabled: bool, extra_pairs: tuple = ()):
        self.enabled = enabled
        self.pairs = {"<think>": "</think>", "<think/>": "</think>", **dict(extra_pairs)}
        self.pending = ""
        self.closers: list[str] = []

    def feed(self, text: str, *, final: bool = False) -> str:
        if not self.enabled:
            return text
        self.pending += text
        result = []
        while self.pending:
            tokens = list(self.pairs)
            if self.closers:
                tokens.append(self.closers[-1])
            found = [(self.pending.find(token), token) for token in tokens if token in self.pending]
            if found:
                position, token = min(found)
                if not self.closers:
                    result.append(self.pending[:position])
                self.pending = self.pending[position + len(token) :]
                if self.closers and token == self.closers[-1]:
                    self.closers.pop()
                else:
                    self.closers.append(self.pairs[token])
                continue
            keep = 0
            if not final:
                for token in tokens:
                    for size in range(1, min(len(token), len(self.pending) + 1)):
                        if self.pending.endswith(token[:size]):
                            keep = max(keep, size)
            split = len(self.pending) - keep
            if not self.closers:
                result.append(self.pending[:split])
            self.pending = self.pending[split:]
            break
        return "".join(result)
