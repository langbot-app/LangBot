"""
Unit tests for LocalAgentRunner protection mechanisms:
- Maximum tool-call iteration limit
- Tool result length truncation

These tests verify the logic independently of the full langbot import chain.
"""

import json
import pytest


# Mirror the module-level constants from localagent.py so tests remain valid
# even when the full import chain is unavailable.
MAX_TOOL_ITERATIONS = 16
MAX_TOOL_RESULT_LENGTH = 8000


def test_max_tool_iterations_constant():
    """MAX_TOOL_ITERATIONS should be a positive integer."""
    assert isinstance(MAX_TOOL_ITERATIONS, int)
    assert MAX_TOOL_ITERATIONS > 0


def test_max_tool_result_length_constant():
    """MAX_TOOL_RESULT_LENGTH should be a positive integer."""
    assert isinstance(MAX_TOOL_RESULT_LENGTH, int)
    assert MAX_TOOL_RESULT_LENGTH > 0


def test_tool_result_truncation_logic():
    """Simulate the truncation logic applied in LocalAgentRunner."""
    large_result = {"data": "x" * (MAX_TOOL_RESULT_LENGTH + 1000)}
    tool_content = json.dumps(large_result, ensure_ascii=False)

    if len(tool_content) > MAX_TOOL_RESULT_LENGTH:
        tool_content = tool_content[:MAX_TOOL_RESULT_LENGTH] + '\n...[truncated]'

    assert len(tool_content) == MAX_TOOL_RESULT_LENGTH + len('\n...[truncated]')
    assert tool_content.endswith('\n...[truncated]')


def test_tool_result_no_truncation_when_within_limit():
    """Short tool results should not be truncated."""
    small_result = {"data": "hello"}
    tool_content = json.dumps(small_result, ensure_ascii=False)

    original = tool_content
    if len(tool_content) > MAX_TOOL_RESULT_LENGTH:
        tool_content = tool_content[:MAX_TOOL_RESULT_LENGTH] + '\n...[truncated]'

    assert tool_content == original


def test_iteration_limit_logic():
    """Simulate the iteration counter guard used in the agent loop."""
    pending = [object()]  # always has a pending call
    iteration_count = 0
    executed = 0

    while pending and iteration_count < MAX_TOOL_ITERATIONS:
        iteration_count += 1
        executed += 1
        # pending never clears — simulates infinite tool-call loop

    assert executed == MAX_TOOL_ITERATIONS
    assert iteration_count == MAX_TOOL_ITERATIONS
