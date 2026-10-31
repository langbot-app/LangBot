from __future__ import annotations

import os
import uuid

import pytest

from powercontext_client import PowerContextClient
from scope import LangBotIdentity, binding_key


@pytest.mark.asyncio
async def test_live_powercontext_contract_round_trip() -> None:
    server_url = os.environ.get("POWERCONTEXT_TEST_SERVER_URL")
    if not server_url:
        pytest.skip("POWERCONTEXT_TEST_SERVER_URL is not set")

    client = PowerContextClient(server_url=server_url)
    unique = uuid.uuid4().hex
    created = await client.request(
        "POST",
        "/v1/scopes",
        payload={
            "title": f"LangBot plugin test {unique[:8]}",
            "summary": "Temporary Scope for LangBot PowerContext plugin contract verification.",
            "idempotency_key": f"langbot-plugin-test-{unique}",
        },
        expected_statuses=(201,),
    )
    scope_id = created.data["scope_id"]
    key = binding_key(
        LangBotIdentity(bot_uuid="test-bot", session_name=f"person_{unique}"),
        "session",
    )

    bound = await client.set_scope_binding(key=key, scope_id=scope_id)
    assert bound.data["scope_id"] == scope_id
    resolved = await client.resolve_scope(
        explicit_scope_id=None,
        binding_keys=[key],
        allow_default=False,
    )
    assert resolved.data["scope_id"] == scope_id

    remembered = await client.remember(
        scope_id=scope_id,
        kind="decision",
        text="Validate refund eligibility before offering a refund action.",
        reason="LangBot integration contract test",
    )
    assert remembered.data["entry"]["citation"]["entry_id"]

    searched = await client.search_memory(
        scope_id=scope_id,
        query="refund eligibility",
        limit=5,
        mode="fts",
    )
    assert any("refund eligibility" in hit["text"] for hit in searched.data["hits"])

    prepared = await client.prepare_context(
        scope_id=scope_id,
        query="refund eligibility",
        max_bytes=4000,
    )
    assert prepared.data["status"] == "ready"
    assert "refund eligibility" in prepared.data["content"]

    captured = await client.capture_content(
        scope_id=scope_id,
        source_id=f"langbot-test-{unique}",
        content="LangBot user message from test-user:\nPlease check refund eligibility.",
        metadata={"integration": "langbot", "test": True},
    )
    assert captured.data["status"] == "accepted"
