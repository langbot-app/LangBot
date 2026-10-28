"""Configuration parsing and validation for local-agent runner."""

from __future__ import annotations

import typing

DEFAULT_MAX_TOOL_ITERATIONS = 100
DEFAULT_MAX_TOOL_RESULT_CHARS = 20000
DEFAULT_RUN_TIMEOUT_SECONDS = 300
DEFAULT_TOOL_EXECUTION_MODE = "parallel"
VALID_TOOL_EXECUTION_MODES = {"parallel", "serial"}


def parse_model_config(
    model_config: typing.Any,
    allowed_model_ids: set[str],
) -> list[str]:
    """Parse model configuration into ordered list of model IDs.

    Supports the Protocol v1 model-fallback-selector shape:
    {"primary": "...", "fallbacks": [...]}

    Filters out models not in allowed_model_ids.

    Args:
        model_config: Model configuration from ctx.config["model"]
        allowed_model_ids: Set of authorized model IDs from ctx.resources

    Returns:
        Ordered list of model IDs to try (primary first, then fallbacks)
        Empty list if no valid models configured.
    """
    candidates: list[str] = []

    if model_config is None:
        return candidates

    if isinstance(model_config, dict):
        # Primary model
        primary = model_config.get("primary")
        if primary:
            primary_id = _normalize_model_id(primary)
            if primary_id and primary_id in allowed_model_ids:
                candidates.append(primary_id)

        # Fallback models
        fallbacks = model_config.get("fallbacks", [])
        if isinstance(fallbacks, list):
            for fb in fallbacks:
                fb_id = _normalize_model_id(fb)
                if fb_id and fb_id in allowed_model_ids and fb_id not in candidates:
                    candidates.append(fb_id)

        return candidates

    # Unknown format
    return candidates


def model_reasoning_levels(config: dict[str, typing.Any]) -> dict[str, str]:
    """Read per-model call options owned by this Runner."""
    selection = config.get("model")
    if not isinstance(selection, dict):
        return {}
    levels = selection.get("reasoning", {})
    if not isinstance(levels, dict):
        raise ValueError("Model reasoning settings must be an object")
    return dict(levels)


def _normalize_model_id(model_id: typing.Any) -> str | None:
    """Normalize model ID, returning None for invalid/empty values."""
    if not isinstance(model_id, str):
        return None
    model_id = model_id.strip()
    if not model_id or model_id == "__none__":
        return None
    return model_id


def get_knowledge_base_ids(
    config: dict[str, typing.Any],
    allowed_kb_ids: set[str],
) -> list[str]:
    """Get knowledge base IDs from config, filtered by allowed set.

    Args:
        config: Runner configuration
        allowed_kb_ids: Set of authorized KB IDs from ctx.resources

    Returns:
        List of KB IDs to use (intersection of config and allowed)
    """
    kb_ids: list[str] = []

    config_kbs = config.get("knowledge-bases", [])
    if not isinstance(config_kbs, list):
        return kb_ids

    for kb_id in config_kbs:
        if isinstance(kb_id, str) and kb_id and kb_id != "__none__":
            if kb_id in allowed_kb_ids and kb_id not in kb_ids:
                kb_ids.append(kb_id)

    return kb_ids


def get_rerank_config(
    config: dict[str, typing.Any],
) -> tuple[str | None, int]:
    """Get rerank model configuration.

    Args:
        config: Runner configuration

    Returns:
        Tuple of (rerank_model_id, rerank_top_k)
        rerank_model_id is None if not configured or set to "__none__"
    """
    rerank_model_id = config.get("rerank-model")
    if not isinstance(rerank_model_id, str) or not rerank_model_id or rerank_model_id == "__none__":
        rerank_model_id = None

    rerank_top_k = config.get("rerank-top-k", 5)
    if not isinstance(rerank_top_k, int) or rerank_top_k < 1:
        rerank_top_k = 5

    return rerank_model_id, rerank_top_k


def get_retrieval_top_k(config: dict[str, typing.Any]) -> int:
    """Get the number of retrieval results requested per knowledge base."""
    return _positive_int(config.get("retrieval-top-k"), default=5)


def get_max_tool_iterations(config: dict[str, typing.Any]) -> int:
    """Get the maximum number of tool-call follow-up iterations."""
    return _positive_int(config.get("max-tool-iterations"), default=DEFAULT_MAX_TOOL_ITERATIONS)


def get_run_timeout_seconds(config: dict[str, typing.Any]) -> int | None:
    """Get local runner timeout seconds, or None when disabled.

    Protocol/README behavior treats timeout=0 and timeout=null as an explicit
    request to rely on Host deadline/cancellation instead of a local wall-clock
    deadline. Missing or invalid positive config keeps the conservative default.
    """
    value = config.get("timeout", DEFAULT_RUN_TIMEOUT_SECONDS)
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int):
        return DEFAULT_RUN_TIMEOUT_SECONDS
    if value == 0:
        return None
    if value < 0:
        return DEFAULT_RUN_TIMEOUT_SECONDS
    return value


def get_tool_execution_mode(config: dict[str, typing.Any]) -> str:
    """Get the same-batch tool execution strategy."""
    raw_mode = config.get("tool-execution-mode", DEFAULT_TOOL_EXECUTION_MODE)
    if not isinstance(raw_mode, str):
        return DEFAULT_TOOL_EXECUTION_MODE
    if raw_mode not in VALID_TOOL_EXECUTION_MODES:
        return DEFAULT_TOOL_EXECUTION_MODE
    return raw_mode


def get_max_tool_result_chars(config: dict[str, typing.Any]) -> int:
    """Get the maximum tool result characters injected into model messages."""
    return _positive_int(config.get("max-tool-result-chars"), default=DEFAULT_MAX_TOOL_RESULT_CHARS)


def get_remove_think(config: dict[str, typing.Any]) -> bool:
    """Whether to ask Host model APIs to strip provider thinking output."""
    return config.get("remove-think") is True


def _positive_int(value: typing.Any, *, default: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        return default
    if value < 1:
        return default
    return value
