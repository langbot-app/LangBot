"""Dify conversations belong to one end user, while a LangBot conversation may hold many senders."""

from types import SimpleNamespace

import pytest
from components.runner import default as runner_module
from components.runner.default import DefaultRunner
from pkg.dify_client import DifyAPIError

CONV_A = "4f4f8c1b-b1f4-4c9f-9e9f-0f144af69f10"
CONV_B = "9a0e3c51-1d7a-4c11-8a45-6f2e5b0d7c22"
NOT_FOUND = DifyAPIError(
    'Dify API error: 404 - {"code":"not_found","message":"Conversation Not Exists.","status":404}',
    code="dify.http_error",
)


def _ctx(state):
    return SimpleNamespace(run_id="run", state=SimpleNamespace(conversation=state))


def _state(results):
    return {r.data["key"]: r.data["value"] for r in results if r.type == "state.updated"}


def test_group_senders_get_their_own_dify_conversation():
    runner = DefaultRunner.__new__(DefaultRunner)
    state = {}
    state.update(_state(runner._conversation_state_updates(_ctx(state), "user_a", CONV_A)))
    state.update(_state(runner._conversation_state_updates(_ctx(state), "user_b", CONV_B)))

    assert runner._get_external_conversation_id(_ctx(state), "user_a") == CONV_A
    assert runner._get_external_conversation_id(_ctx(state), "user_b") == CONV_B
    assert runner._get_external_conversation_id(_ctx(state), "user_c") == ""
    # Raw provider identities are not persisted as state keys.
    assert "user_a" not in str(state[runner_module.CONVERSATION_IDS_KEY])


def test_legacy_state_is_read_only_until_per_user_map_exists():
    runner = DefaultRunner.__new__(DefaultRunner)
    assert runner._get_external_conversation_id(_ctx({"external.conversation_id": CONV_A}), "user_b") == CONV_A
    state = {"external.conversation_id": CONV_A, runner_module.CONVERSATION_IDS_KEY: {}}
    assert runner._get_external_conversation_id(_ctx(state), "user_b") == ""


def test_per_user_map_is_bounded_and_keeps_recent_users(monkeypatch):
    monkeypatch.setattr(runner_module, "MAX_CONVERSATION_IDS", 2)
    runner = DefaultRunner.__new__(DefaultRunner)
    state = {}
    for user in ("a", "b", "a", "c"):
        state.update(_state(runner._conversation_state_updates(_ctx(state), user, CONV_A)))
    assert runner._get_external_conversation_id(_ctx(state), "a") == CONV_A
    assert runner._get_external_conversation_id(_ctx(state), "c") == CONV_A
    assert runner._get_external_conversation_id(_ctx(state), "b") == ""


class _Client:
    def __init__(self, fail_first):
        self.calls = []
        self.fail_first = fail_first

    async def chat_messages(self, **kwargs):
        self.calls.append(kwargs["conversation_id"])
        if self.fail_first and len(self.calls) == 1:
            raise self.fail_first
        yield {"event": "message", "conversation_id": CONV_B, "answer": "hi"}


async def _events(client, conversation_id):
    runner = DefaultRunner.__new__(DefaultRunner)
    return [e async for e in runner._chat_message_events(client, {}, "q", "user_b", conversation_id, [])]


@pytest.mark.asyncio
async def test_stale_conversation_restarts_once_with_new_conversation():
    client = _Client(NOT_FOUND)
    events = await _events(client, CONV_A)
    assert client.calls == [CONV_A, ""]
    assert events[0]["conversation_id"] == CONV_B


@pytest.mark.asyncio
async def test_other_errors_are_not_retried():
    client = _Client(DifyAPIError("Dify API error: 500 - boom", code="dify.http_error"))
    with pytest.raises(DifyAPIError):
        await _events(client, CONV_A)
    assert client.calls == [CONV_A]


@pytest.mark.asyncio
async def test_new_conversation_404_is_not_retried():
    client = _Client(NOT_FOUND)
    with pytest.raises(DifyAPIError):
        await _events(client, "")
    assert client.calls == [""]


def _identity_ctx(session_id, sender):
    return SimpleNamespace(
        config={},
        actor=SimpleNamespace(actor_type="user", actor_id=sender),
        conversation=SimpleNamespace(session_id=session_id, workspace_id=None, launcher_type=None, launcher_id=None),
    )


def test_shared_group_context_uses_one_provider_user_for_all_members():
    runner = DefaultRunner.__new__(DefaultRunner)
    alice = runner._get_user_tag(_identity_ctx("group_g1", "alice"))
    bob = runner._get_user_tag(_identity_ctx("group_g1", "bob"))
    assert alice == bob == "group_g1"


@pytest.mark.parametrize("session_id", ["groupmember_2_g1_alice", "person_alice", None, "group_"])
def test_isolated_contexts_keep_the_sender_as_provider_user(session_id):
    runner = DefaultRunner.__new__(DefaultRunner)
    assert runner._get_user_tag(_identity_ctx(session_id, "alice")) == "user_alice"
