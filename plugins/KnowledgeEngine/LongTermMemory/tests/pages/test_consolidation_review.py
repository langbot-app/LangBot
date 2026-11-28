from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from components.pages.memory_console.memory_console import MemoryConsolePage
from langbot_plugin.api.definition.components.page import PageRequest


@pytest.fixture
def page():
    component = MemoryConsolePage()
    config = {
        "isolation": "session", "consolidation_enabled": True,
        "consolidation_model_uuid": "trusted-summary-model", "embedding_model_uuid": "trusted-embedding-model",
        "consolidation_min_age_days": 10, "consolidation_max_candidates": 8,
    }
    source = "<script>alert('untrusted source')</script>\n" + "Complete source fact. " * 500
    store = SimpleNamespace(
        configs={"kb": config},
        get_kb_configs=AsyncMock(return_value={"kb": config}),
        preview_consolidation=AsyncMock(return_value={
            "proposal_id": "proposal-1", "summary_episode": "An inferred summary <b>not HTML</b>",
            "source_records": [{"id": "source-1", "content": source}],
            "risk_notes": ["Review the inference"],
        }),
        apply_consolidation=AsyncMock(return_value={"summary_episode": {"id": "summary-1"}, "archived_episode_ids": []}),
        append_audit_entry=AsyncMock(),
    )
    component.plugin = SimpleNamespace(memory_store=store)
    return component


def body(**changes):
    return {"collection_id": "kb", "scope_key": "bot:group_room", "user_key": "bot:group_room", **changes}


async def request(page, endpoint, payload):
    return await page.handle_api(PageRequest(endpoint=endpoint, method="POST", body=payload))


@pytest.mark.asyncio
async def test_preview_uses_trusted_kb_model_and_preserves_complete_sources(page):
    response = await request(page, "/consolidation/preview", body())
    assert response.error is None
    assert response.data["source_records"][0]["content"].endswith("Complete source fact. " * 500)
    assert response.data["summary_episode"] == "An inferred summary <b>not HTML</b>"
    page._store.preview_consolidation.assert_awaited_once_with(
        collection_id="kb", user_key="bot:group_room", min_age_days=10, max_candidates=8,
        summary_model_uuid="trusted-summary-model",
    )
    page._store.apply_consolidation.assert_not_awaited()


@pytest.mark.asyncio
async def test_preview_is_available_when_run_is_disabled(page):
    page._store.configs["kb"]["consolidation_enabled"] = False
    response = await request(page, "/consolidation/preview", body())
    assert response.error is None
    page._store.preview_consolidation.assert_awaited_once()


@pytest.mark.asyncio
async def test_run_requires_reviewed_proposal_and_trusted_embedding_model(page):
    response = await request(page, "/consolidation/run", body(proposal_id="proposal-1"))
    assert response.error is None
    page._store.apply_consolidation.assert_awaited_once_with(
        collection_id="kb", embedding_model_uuid="trusted-embedding-model",
        user_key="bot:group_room", proposal_id="proposal-1",
    )
    audit = page._store.append_audit_entry.call_args.kwargs
    assert audit["scope_key"] == "bot:group_room"
    assert audit["user_key"] == "bot:group_room"
    assert audit["metadata"] == {"collection_id": "kb", "proposal_id": "proposal-1"}


@pytest.mark.asyncio
@pytest.mark.parametrize("extra", [{"summary_model_uuid": "browser-model"}, {"embedding_model_uuid": "browser-model"}, {"consolidation_enabled": True}, {"min_age_days": 0}])
@pytest.mark.parametrize("endpoint", ["preview", "run"])
async def test_browser_cannot_override_models_or_policy(page, extra, endpoint):
    payload = body(**extra)
    if endpoint == "run":
        payload["proposal_id"] = "proposal-1"
    response = await request(page, "/consolidation/" + endpoint, payload)
    assert response.error is not None
    page._store.preview_consolidation.assert_not_awaited()
    page._store.apply_consolidation.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize("changes", [{"proposal_id": ""}, {"proposal_id": None}, {"proposal_id": 123}, {"proposal_id": "proposal-1", "user_key": "another-space"}, {"proposal_id": "proposal-1", "collection_id": "unknown-kb"}])
async def test_invalid_run_never_reaches_store(page, changes):
    response = await request(page, "/consolidation/run", body(**changes))
    assert response.error is not None
    page._store.apply_consolidation.assert_not_awaited()
    page._store.append_audit_entry.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize("disabled", [False, "false", None])
async def test_run_is_fail_closed_when_not_explicitly_enabled(page, disabled):
    page._store.configs["kb"]["consolidation_enabled"] = disabled
    response = await request(page, "/consolidation/run", body(proposal_id="proposal-1"))
    assert response.error is not None
    page._store.apply_consolidation.assert_not_awaited()


@pytest.mark.asyncio
async def test_run_requires_configured_embedding_model(page):
    page._store.configs["kb"].pop("embedding_model_uuid")
    response = await request(page, "/consolidation/run", body(proposal_id="proposal-1"))
    assert response.error is not None
    page._store.apply_consolidation.assert_not_awaited()


@pytest.mark.asyncio
async def test_preview_scope_is_checked_against_kb_isolation(page):
    page._store.configs["kb"]["isolation"] = "bot"
    response = await request(page, "/consolidation/preview", body(user_key="bot:bot"))
    assert response.error is None
    assert page._store.preview_consolidation.call_args.kwargs["user_key"] == "bot:bot"
    rejected = await request(page, "/consolidation/preview", body())
    assert rejected.error is not None
    assert page._store.preview_consolidation.await_count == 1


@pytest.mark.asyncio
async def test_store_rejects_cross_scope_or_stale_proposal_without_success_audit(page):
    page._store.apply_consolidation.side_effect = ValueError("proposal scope changed; preview again")
    response = await request(page, "/consolidation/run", body(proposal_id="proposal-from-another-space"))
    assert response.error is not None
    assert "preview again" in response.error
    page._store.apply_consolidation.assert_awaited_once()
    page._store.append_audit_entry.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize("payload", [[], "body", 123])
async def test_consolidation_body_must_be_an_object(page, payload):
    response = await request(page, "/consolidation/preview", payload)
    assert response.error is not None
    page._store.preview_consolidation.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize("changes", [{"collection_id": ""}, {"scope_key": ""}, {"user_key": ""}, {"collection_id": 123}, {"user_key": []}])
async def test_preview_requires_string_kb_scope_and_user_identity(page, changes):
    response = await request(page, "/consolidation/preview", body(**changes))
    assert response.error is not None
    page._store.preview_consolidation.assert_not_awaited()


@pytest.mark.asyncio
async def test_unknown_kb_isolation_fails_closed(page):
    page._store.configs["kb"]["isolation"] = "unknown"
    response = await request(page, "/consolidation/preview", body(user_key="bot:bot"))
    assert response.error is not None
    page._store.preview_consolidation.assert_not_awaited()
