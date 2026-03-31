import pytest

from langbot.pkg.provider.conversation.dify_store import (
    build_binding_payload,
    is_binding_expired,
    normalize_binding_payload,
)


def test_normalize_binding_payload_with_new_structure():
    payload = {
        "conversation_id": "conv-1",
        "created_at": 100,
        "last_active_at": 120,
        "policy_version": 2,
    }

    normalized = normalize_binding_payload(payload)

    assert normalized == payload


def test_normalize_binding_payload_strips_conversation_id_whitespace():
    payload = {
        "conversation_id": "  conv-1  ",
        "created_at": 100,
        "last_active_at": 120,
        "policy_version": 2,
    }

    normalized = normalize_binding_payload(payload)

    assert normalized == {
        "conversation_id": "conv-1",
        "created_at": 100,
        "last_active_at": 120,
        "policy_version": 2,
    }


@pytest.mark.parametrize(
    "payload",
    [
        {"conversation_id": "conv-x", "created_at": 1, "last_active_at": 2},
        {"conversation_id": "conv-x", "policy_version": 2},
    ],
)
def test_normalize_binding_payload_with_half_new_structure_fails_closed(payload):
    assert normalize_binding_payload(payload) is None


@pytest.mark.parametrize(
    "payload",
    [
        {"conversation_id": "conv-x", "updated_at": 100, "policy_version": 2},
        {"conversation_id": "conv-x", "created_at": 1, "updated_at": 100},
        {"conversation_id": "conv-x", "last_active_at": 2, "updated_at": 100},
    ],
)
def test_normalize_binding_payload_with_mixed_schema_falls_back_to_legacy(payload):
    assert normalize_binding_payload(payload) == {
        "conversation_id": "conv-x",
        "created_at": 100,
        "last_active_at": 100,
        "policy_version": 1,
    }


def test_normalize_binding_payload_with_legacy_structure():
    payload = {"conversation_id": "conv-legacy", "updated_at": 1680000000}

    normalized = normalize_binding_payload(payload)

    assert normalized == {
        "conversation_id": "conv-legacy",
        "created_at": 1680000000,
        "last_active_at": 1680000000,
        "policy_version": 1,
    }


def test_build_binding_payload_keeps_existing_created_at():
    payload = build_binding_payload(
        conversation_id="conv-2",
        now_ts=200,
        existing_created_at=100,
    )

    assert payload == {
        "conversation_id": "conv-2",
        "created_at": 100,
        "last_active_at": 200,
        "policy_version": 2,
    }


def test_is_binding_expired_uses_last_active_at():
    binding = {
        "conversation_id": "conv-3",
        "created_at": 100,
        "last_active_at": 150,
        "policy_version": 2,
    }

    assert is_binding_expired(binding, now_ts=200, idle_timeout_seconds=60) is False
    assert is_binding_expired(binding, now_ts=211, idle_timeout_seconds=60) is True


def test_is_binding_expired_at_timeout_boundary_is_expired():
    binding = {
        "conversation_id": "conv-3",
        "created_at": 100,
        "last_active_at": 150,
        "policy_version": 2,
    }

    assert is_binding_expired(binding, now_ts=210, idle_timeout_seconds=60) is True


@pytest.mark.parametrize("idle_timeout_seconds", [0, -1])
def test_is_binding_expired_when_timeout_non_positive_fails_closed(idle_timeout_seconds):
    binding = {
        "conversation_id": "conv-3",
        "created_at": 100,
        "last_active_at": 150,
        "policy_version": 2,
    }

    assert is_binding_expired(binding, now_ts=200, idle_timeout_seconds=idle_timeout_seconds) is True


@pytest.mark.parametrize(
    "payload",
    [
        None,
        {},
        {"last_active_at": 100},
        {"conversation_id": "", "last_active_at": 100},
        {"conversation_id": "   ", "last_active_at": 100},
        {"conversation_id": "conv-x"},
        {"conversation_id": "conv-x", "last_active_at": "100"},
        {"conversation_id": "conv-x", "created_at": "99", "last_active_at": 100},
        {"conversation_id": "conv-x", "updated_at": "100"},
    ],
)
def test_normalize_binding_payload_with_invalid_data_returns_none(payload):
    assert normalize_binding_payload(payload) is None
