"""Streaming and deduplication after a blocking Dify form submission."""

from types import SimpleNamespace

import pytest
from components.runner.default import DefaultRunner


async def _resume(events):
    continuation = {
        "phase": "submit",
        "field_map": {},
        "action_map": {"approve": "approve"},
        "default_inputs": {},
        "form_token": "form",
        "workflow_run_id": "workflow",
        "user": "user",
    }
    runner = SimpleNamespace()

    class Client:
        async def workflow_submit(self, **kwargs):
            for event in events:
                yield event

    submission = SimpleNamespace(interaction_id="interaction", action_id="approve", values={})
    result = [
        item
        async for item in DefaultRunner._resume_workflow_once(
            runner, SimpleNamespace(run_id="run"), Client(), submission, False, continuation
        )
    ]
    return [item.data["chunk"] for item in result if item.type == "message.delta"], result


@pytest.mark.asyncio
async def test_resume_emits_intermediate_snapshots_without_repeating_final_answer():
    events = [{"event": "text_chunk", "data": {"text": char}} for char in "abcdefghij"]
    events += [
        {"event": "node_finished", "data": {"node_type": "answer", "outputs": {"answer": "abcdefghij"}}},
        {"event": "workflow_finished", "data": {"outputs": {"summary": "abcdefghij"}}},
    ]
    chunks, results = await _resume(events)
    assert [(chunk["content"], chunk["is_final"]) for chunk in chunks] == [
        ("abcdefgh", False),
        ("abcdefghij", True),
    ]
    assert results[-1].type == "run.completed"


@pytest.mark.asyncio
async def test_resume_accepts_cumulative_message_snapshots():
    events = [{"event": "message", "answer": "abcdefgh"[:length]} for length in range(1, 9)]
    events.append({"event": "workflow_finished", "data": {"outputs": {}}})
    chunks, _ = await _resume(events)
    assert [chunk["content"] for chunk in chunks] == ["abcdefgh"]
