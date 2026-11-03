from __future__ import annotations

import pytest

from components.commands.memory import Memory
from test_memory_management_commands import FakeAPI, FakePlugin, _run


@pytest.mark.asyncio
async def test_semantic_command_requires_review_id_and_forwards_reviewed_proposal(monkeypatch):
    monkeypatch.setattr("components.commands.memory.QueryBasedAPIProxy", lambda **_: FakeAPI())
    command = Memory()
    plugin = FakePlugin()
    command.plugin = plugin
    original_context = plugin.memory_store.resolve_user_context

    async def context(*args, **kwargs):
        values = list(await original_context(*args, **kwargs))
        values[-1] = {**values[-1], "consolidation_model_uuid": "summary-model", "consolidation_enabled": True}
        return tuple(values)

    plugin.memory_store.resolve_user_context = context
    assert "reviewed proposal ID" in await _run(command, "consolidate", ["run"])
    assert plugin.memory_store.apply_calls == []
    calls = []
    original_apply = plugin.memory_store.apply_consolidation

    async def apply(*args, proposal_id, **kwargs):
        calls.append(proposal_id)
        return await original_apply(*args, **kwargs)

    plugin.memory_store.apply_consolidation = apply
    assert "wrote summary" in await _run(command, "consolidate", ["run", "review-id"])
    assert calls == ["review-id"]


def test_semantic_preview_displays_sources_and_review_boundary():
    text = Memory._format_consolidation_preview(
        {
            "proposal_id": "review-id",
            "summary_episode": "Alice selected PostgreSQL",
            "source_records": [
                {"id": "one", "content": "Alice selected SQLite", "timestamp": "2026-01-01", "sender_id": "alice"}
            ],
        }
    )
    assert "Source one" in text and "Alice selected SQLite" in text
    assert "inference" in text and "do not prove correctness" in text
    assert "!memory consolidate run review-id" in text


@pytest.mark.asyncio
@pytest.mark.parametrize("mode", ["preview", "run"])
async def test_semantic_command_reports_invalid_proposal_without_dispatch_traceback(monkeypatch, mode):
    monkeypatch.setattr("components.commands.memory.QueryBasedAPIProxy", lambda **_: FakeAPI())
    command = Memory()
    plugin = FakePlugin()
    command.plugin = plugin
    plugin.memory_store.consolidation_enabled = True

    async def invalid(*args, **kwargs):
        raise ValueError("Sources changed; preview again")

    if mode == "preview":
        plugin.memory_store.preview_consolidation = invalid
        params = [mode]
    else:
        plugin.memory_store.apply_consolidation = invalid
        params = [mode, "review-id"]
    assert "Sources changed; preview again" in await _run(command, "consolidate", params)
