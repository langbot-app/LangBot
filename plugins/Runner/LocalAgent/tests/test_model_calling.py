from __future__ import annotations

import pytest

from pkg.model_calling import ModelCallError, is_context_overflow_error


@pytest.mark.parametrize(
    "message",
    [
        "prompt is too long: 213462 tokens > 200000 maximum",
        '413 {"error":{"type":"request_too_large","message":"Request exceeds the maximum size"}}',
        "Your input exceeds the context window of this model",
        "Requested token count exceeds the model's maximum context length of 131072 tokens.",
        "Input length (265330) exceeds model's maximum context length (262144).",
        "The input token count (1196265) exceeds the maximum number of tokens allowed (1048575)",
        "This model's maximum prompt length is 131072 but the request contains 537812 tokens",
        "Please reduce the length of the messages or completion",
        "This endpoint's maximum context length is 32768 tokens. However, you requested about 50000 tokens",
        "Input length 100000 exceeds the maximum allowed input length of 65536 tokens.",
        "The input (516368 tokens) is longer than the model's context length (262144 tokens).",
        "the request exceeds the available context size, try increasing it",
        "tokens to keep from the initial prompt is greater than the context length",
        "invalid params, context window exceeds limit",
        "Your request exceeded model token limit: 131072 (requested: 220000)",
        "Prompt contains 300000 tokens and is too large for model with 128000 maximum context length",
        "model_context_window_exceeded",
        "prompt too long; exceeded max context length by 100918 tokens",
        "context_length_exceeded",
        "400 status code (no body)",
    ],
)
def test_is_context_overflow_error_detects_provider_patterns(message: str) -> None:
    assert is_context_overflow_error(RuntimeError(message))


@pytest.mark.parametrize(
    "message",
    [
        "Throttling error: Too many tokens, please wait before trying again.",
        "Service unavailable: too many tokens in current quota bucket",
        "rate limit exceeded: too many tokens per minute",
        "429 too many requests: token limit exceeded for the current minute",
    ],
)
def test_is_context_overflow_error_ignores_retryable_non_overflow_errors(message: str) -> None:
    assert not is_context_overflow_error(RuntimeError(message))


def test_model_call_error_uses_context_overflow_detection() -> None:
    error = ModelCallError("All models failed. Last error: context length exceeded", retryable=True)

    assert error.is_context_overflow
